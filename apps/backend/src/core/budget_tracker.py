"""
Budget Tracking System for Kaison K1 Platform
Session-level and daily-level budget management with alert thresholds
"""

import json
import os
import fcntl
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class BudgetStatus(str, Enum):
    """Budget utilization status"""
    NORMAL = "normal"  # < 80%
    WARNING = "warning"  # 80-95%
    CRITICAL = "critical"  # 95-100%
    EXHAUSTED = "exhausted"  # >= 100%


class BudgetDecision(str, Enum):
    """Budget enforcement decision"""
    APPROVED = "approved"  # Proceed with paid API
    DOWNGRADE = "downgrade"  # Use cheaper model
    FALLBACK_LOCAL = "fallback_local"  # Use local only
    BLOCK = "block"  # Budget exhausted


@dataclass
class BudgetAlert:
    """Budget alert notification"""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None
    alert_type: str = "warning"  # "warning", "critical", "exhausted"
    current_spent_cents: float = 0.0
    budget_limit_cents: int = 0
    utilization_percent: float = 0.0
    message: str = ""
    scope: str = "session"  # "session" or "daily"


@dataclass
class SessionBudget:
    """Budget tracking for a single session"""
    session_id: str
    initial_budget_cents: int = 1000  # $10 default
    spent_cents: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transaction_count: int = 0
    alerts_sent: List[BudgetAlert] = field(default_factory=list)

    @property
    def remaining_cents(self) -> float:
        """Calculate remaining budget"""
        return max(0, self.initial_budget_cents - self.spent_cents)

    @property
    def utilization_percent(self) -> float:
        """Calculate budget utilization percentage"""
        if self.initial_budget_cents == 0:
            return 0.0
        return (self.spent_cents / self.initial_budget_cents) * 100

    @property
    def status(self) -> BudgetStatus:
        """Get current budget status"""
        util = self.utilization_percent
        if util >= 100:
            return BudgetStatus.EXHAUSTED
        elif util >= 95:
            return BudgetStatus.CRITICAL
        elif util >= 80:
            return BudgetStatus.WARNING
        return BudgetStatus.NORMAL


@dataclass
class DailyBudget:
    """Daily aggregate budget tracking"""
    date: str  # YYYY-MM-DD
    total_budget_cents: int = 10000  # $100 default
    spent_cents: float = 0.0
    transaction_count: int = 0
    session_count: int = 0
    alerts_sent: List[BudgetAlert] = field(default_factory=list)

    @property
    def remaining_cents(self) -> float:
        """Calculate remaining budget"""
        return max(0, self.total_budget_cents - self.spent_cents)

    @property
    def utilization_percent(self) -> float:
        """Calculate budget utilization percentage"""
        if self.total_budget_cents == 0:
            return 0.0
        return (self.spent_cents / self.total_budget_cents) * 100

    @property
    def status(self) -> BudgetStatus:
        """Get current budget status"""
        util = self.utilization_percent
        if util >= 100:
            return BudgetStatus.EXHAUSTED
        elif util >= 95:
            return BudgetStatus.CRITICAL
        elif util >= 80:
            return BudgetStatus.WARNING
        return BudgetStatus.NORMAL


@dataclass
class BudgetTransaction:
    """Individual cost transaction"""
    transaction_id: str
    session_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    task_id: str = ""
    model_id: str = ""
    cost_cents: float = 0.0
    estimated_cost_cents: float = 0.0
    task_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class BudgetTracker:
    """
    Track and enforce budget constraints per session and daily.

    Features:
    - Per-session budget tracking ($10 default)
    - Daily aggregate tracking ($100 limit)
    - Alert thresholds at 80% and 95%
    - Emergency budget approval workflow
    - Persistent storage for budget state
    """

    def __init__(
        self,
        default_session_budget_cents: int = 1000,  # $10
        default_daily_budget_cents: int = 10000,  # $100
        storage_dir: str = "var/lib/kai/budgets",
        alerts_enabled: bool = True
    ):
        """Initialize budget tracker"""
        self.default_session_budget = default_session_budget_cents
        self.default_daily_budget = default_daily_budget_cents
        self.alerts_enabled = alerts_enabled

        # Storage
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory state
        self.session_budgets: Dict[str, SessionBudget] = {}
        self.daily_budgets: Dict[str, DailyBudget] = {}
        self.transactions: List[BudgetTransaction] = []

        # Load persisted state
        self._load_state()

        logger.info(f"✓ BudgetTracker initialized: ${default_session_budget_cents/100}/session, "
                   f"${default_daily_budget_cents/100}/day")

    def get_remaining(self, session_id: str) -> float:
        """
        Get remaining budget for a session in cents.
        Returns minimum of session remaining and daily remaining.
        """
        session_budget = self._get_or_create_session(session_id)
        daily_budget = self._get_or_create_daily()

        # Return the more restrictive limit
        return min(session_budget.remaining_cents, daily_budget.remaining_cents)

    def get_session_budget(self, session_id: str) -> SessionBudget:
        """Get full session budget details"""
        return self._get_or_create_session(session_id)

    def get_daily_budget(self) -> DailyBudget:
        """Get daily budget details"""
        return self._get_or_create_daily()

    async def check_budget_approval(
        self,
        session_id: str,
        estimated_cost_cents: float,
        task_id: str = ""
    ) -> tuple[bool, BudgetDecision, str]:
        """
        Check if a task can be approved based on budget.

        Returns:
            (approved, decision, message)
        """
        session_budget = self._get_or_create_session(session_id)
        daily_budget = self._get_or_create_daily()

        session_remaining = session_budget.remaining_cents
        daily_remaining = daily_budget.remaining_cents

        # Check if budget exhausted
        if session_remaining <= 0:
            return False, BudgetDecision.BLOCK, "Session budget exhausted"

        if daily_remaining <= 0:
            return False, BudgetDecision.BLOCK, "Daily budget exhausted"

        # Check if estimated cost exceeds remaining
        if estimated_cost_cents > session_remaining:
            msg = f"Estimated cost ${estimated_cost_cents/100:.2f} exceeds session remaining ${session_remaining/100:.2f}"
            return False, BudgetDecision.FALLBACK_LOCAL, msg

        if estimated_cost_cents > daily_remaining:
            msg = f"Estimated cost ${estimated_cost_cents/100:.2f} exceeds daily remaining ${daily_remaining/100:.2f}"
            return False, BudgetDecision.FALLBACK_LOCAL, msg

        # Check if near limits (suggest downgrade)
        session_util_after = ((session_budget.spent_cents + estimated_cost_cents) /
                              session_budget.initial_budget_cents * 100)
        daily_util_after = ((daily_budget.spent_cents + estimated_cost_cents) /
                           daily_budget.total_budget_cents * 100)

        if session_util_after > 95 or daily_util_after > 95:
            msg = f"Budget critical after this task (session: {session_util_after:.1f}%, daily: {daily_util_after:.1f}%)"
            return True, BudgetDecision.DOWNGRADE, msg

        return True, BudgetDecision.APPROVED, "Budget approved"

    async def reserve_budget(
        self,
        session_id: str,
        estimated_cost_cents: float,
        task_id: str = "",
        model_id: str = "",
        task_type: str = ""
    ) -> tuple[bool, str]:
        """
        Reserve budget for a task (optimistic locking).
        Returns (success, message)
        """
        approved, decision, message = await self.check_budget_approval(
            session_id, estimated_cost_cents, task_id
        )

        if not approved or decision == BudgetDecision.BLOCK:
            return False, message

        # Note: We don't actually deduct here, just validate
        # Actual deduction happens in record_actual_cost
        logger.info(f"Budget reserved for {task_id}: ${estimated_cost_cents/100:.4f} ({decision.value})")
        return True, message

    async def record_actual_cost(
        self,
        task_id: str,
        cost_cents: float,
        session_id: str,
        model_id: str = "",
        task_type: str = "",
        estimated_cost_cents: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, str]:
        """
        Record actual cost after task execution.
        Updates session and daily budgets.
        """
        try:
            session_budget = self._get_or_create_session(session_id)
            daily_budget = self._get_or_create_daily()

            # Update spending
            old_session_spent = session_budget.spent_cents
            old_daily_spent = daily_budget.spent_cents

            session_budget.spent_cents += cost_cents
            session_budget.last_updated = datetime.now(timezone.utc)
            session_budget.transaction_count += 1

            daily_budget.spent_cents += cost_cents
            daily_budget.transaction_count += 1

            # Record transaction
            transaction = BudgetTransaction(
                transaction_id=f"txn_{len(self.transactions)}",
                session_id=session_id,
                task_id=task_id,
                model_id=model_id,
                cost_cents=cost_cents,
                estimated_cost_cents=estimated_cost_cents,
                task_type=task_type,
                metadata=metadata or {}
            )
            self.transactions.append(transaction)

            # Check for alerts
            await self._check_and_send_alerts(session_budget, daily_budget)

            # Persist state
            self._save_state()

            logger.info(f"✓ Cost recorded: ${cost_cents/100:.4f} for {task_id} "
                       f"(session: ${session_budget.spent_cents/100:.2f}/{session_budget.initial_budget_cents/100}, "
                       f"daily: ${daily_budget.spent_cents/100:.2f}/{daily_budget.total_budget_cents/100})")

            return True, f"Cost recorded: ${cost_cents/100:.4f}"

        except Exception as e:
            logger.error(f"Failed to record cost: {str(e)}")
            return False, f"Error recording cost: {str(e)}"

    async def increase_session_budget(
        self,
        session_id: str,
        additional_cents: int,
        approved_by: str = "system"
    ) -> tuple[bool, str]:
        """Emergency budget increase (requires approval)"""
        session_budget = self._get_or_create_session(session_id)

        old_budget = session_budget.initial_budget_cents
        session_budget.initial_budget_cents += additional_cents

        logger.warning(f"⚠️ Session budget increased by ${additional_cents/100:.2f} "
                      f"(${old_budget/100} -> ${session_budget.initial_budget_cents/100}) "
                      f"approved by {approved_by}")

        self._save_state()
        return True, f"Budget increased by ${additional_cents/100:.2f}"

    async def reset_daily_budget(self) -> tuple[bool, str]:
        """Reset daily budget (called at midnight)"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if today in self.daily_budgets:
            old_daily = self.daily_budgets[today]
            logger.info(f"Daily budget reset. Previous: ${old_daily.spent_cents/100:.2f} "
                       f"spent from ${old_daily.total_budget_cents/100}")

        # Create fresh daily budget
        self.daily_budgets[today] = DailyBudget(
            date=today,
            total_budget_cents=self.default_daily_budget
        )

        self._save_state()
        logger.info(f"✓ Daily budget reset: ${self.default_daily_budget/100}/day")
        return True, "Daily budget reset"

    async def get_budget_analytics(self) -> Dict[str, Any]:
        """Get comprehensive budget analytics"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_budget = self._get_or_create_daily()

        # Calculate aggregates
        total_sessions = len(self.session_budgets)
        active_sessions = sum(1 for s in self.session_budgets.values()
                            if s.transaction_count > 0)

        total_spent_all_time = sum(s.spent_cents for s in self.session_budgets.values())

        # Model breakdown
        model_spending = {}
        for txn in self.transactions:
            model_spending[txn.model_id] = model_spending.get(txn.model_id, 0.0) + txn.cost_cents

        return {
            "daily": {
                "date": today,
                "budget_cents": daily_budget.total_budget_cents,
                "spent_cents": daily_budget.spent_cents,
                "remaining_cents": daily_budget.remaining_cents,
                "utilization_percent": daily_budget.utilization_percent,
                "status": daily_budget.status.value,
                "transaction_count": daily_budget.transaction_count,
                "session_count": daily_budget.session_count
            },
            "sessions": {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "default_budget_cents": self.default_session_budget,
                "sessions_over_budget": sum(1 for s in self.session_budgets.values()
                                          if s.status == BudgetStatus.EXHAUSTED)
            },
            "spending": {
                "total_spent_all_time_cents": total_spent_all_time,
                "total_transactions": len(self.transactions),
                "by_model": {model: f"${cost/100:.4f}" for model, cost in model_spending.items()},
                "avg_cost_per_transaction_cents": (
                    total_spent_all_time / len(self.transactions) if self.transactions else 0
                )
            }
        }

    # ========================================================================
    # Internal Methods
    # ========================================================================

    def _get_or_create_session(self, session_id: str) -> SessionBudget:
        """Get or create session budget"""
        if session_id not in self.session_budgets:
            self.session_budgets[session_id] = SessionBudget(
                session_id=session_id,
                initial_budget_cents=self.default_session_budget
            )

            # Update daily session count
            daily = self._get_or_create_daily()
            daily.session_count += 1

            logger.info(f"Created new session budget: {session_id} (${self.default_session_budget/100})")

        return self.session_budgets[session_id]

    def _get_or_create_daily(self) -> DailyBudget:
        """Get or create daily budget"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if today not in self.daily_budgets:
            self.daily_budgets[today] = DailyBudget(
                date=today,
                total_budget_cents=self.default_daily_budget
            )
            logger.info(f"Created new daily budget: {today} (${self.default_daily_budget/100})")

        return self.daily_budgets[today]

    async def _check_and_send_alerts(
        self,
        session_budget: SessionBudget,
        daily_budget: DailyBudget
    ):
        """Check budget thresholds and send alerts"""
        if not self.alerts_enabled:
            return

        # Session alerts
        if session_budget.status == BudgetStatus.WARNING:
            if not any(a.alert_type == "warning" for a in session_budget.alerts_sent):
                alert = BudgetAlert(
                    session_id=session_budget.session_id,
                    alert_type="warning",
                    current_spent_cents=session_budget.spent_cents,
                    budget_limit_cents=session_budget.initial_budget_cents,
                    utilization_percent=session_budget.utilization_percent,
                    message=f"Session budget at {session_budget.utilization_percent:.1f}% utilization",
                    scope="session"
                )
                session_budget.alerts_sent.append(alert)
                logger.warning(f"⚠️ SESSION BUDGET WARNING: {alert.message}")

        elif session_budget.status == BudgetStatus.CRITICAL:
            if not any(a.alert_type == "critical" for a in session_budget.alerts_sent):
                alert = BudgetAlert(
                    session_id=session_budget.session_id,
                    alert_type="critical",
                    current_spent_cents=session_budget.spent_cents,
                    budget_limit_cents=session_budget.initial_budget_cents,
                    utilization_percent=session_budget.utilization_percent,
                    message=f"Session budget CRITICAL: {session_budget.utilization_percent:.1f}% utilization",
                    scope="session"
                )
                session_budget.alerts_sent.append(alert)
                logger.critical(f"🚨 SESSION BUDGET CRITICAL: {alert.message}")

        # Daily alerts
        if daily_budget.status == BudgetStatus.WARNING:
            if not any(a.alert_type == "warning" for a in daily_budget.alerts_sent):
                alert = BudgetAlert(
                    alert_type="warning",
                    current_spent_cents=daily_budget.spent_cents,
                    budget_limit_cents=daily_budget.total_budget_cents,
                    utilization_percent=daily_budget.utilization_percent,
                    message=f"Daily budget at {daily_budget.utilization_percent:.1f}% utilization",
                    scope="daily"
                )
                daily_budget.alerts_sent.append(alert)
                logger.warning(f"⚠️ DAILY BUDGET WARNING: {alert.message}")

        elif daily_budget.status == BudgetStatus.CRITICAL:
            if not any(a.alert_type == "critical" for a in daily_budget.alerts_sent):
                alert = BudgetAlert(
                    alert_type="critical",
                    current_spent_cents=daily_budget.spent_cents,
                    budget_limit_cents=daily_budget.total_budget_cents,
                    utilization_percent=daily_budget.utilization_percent,
                    message=f"Daily budget CRITICAL: {daily_budget.utilization_percent:.1f}% utilization",
                    scope="daily"
                )
                daily_budget.alerts_sent.append(alert)
                logger.critical(f"🚨 DAILY BUDGET CRITICAL: {alert.message}")

    def _save_state(self):
        """Persist budget state to disk with file locking for thread safety"""
        try:
            state = {
                "sessions": {sid: asdict(budget) for sid, budget in self.session_budgets.items()},
                "daily": {date: asdict(budget) for date, budget in self.daily_budgets.items()},
                "transactions": [asdict(txn) for txn in self.transactions[-1000:]],  # Keep last 1000
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

            state_file = self.storage_dir / "budget_state.json"

            # Use exclusive file lock to prevent race conditions
            with open(state_file, 'w') as f:
                try:
                    # Acquire exclusive lock (LOCK_EX) with blocking
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    json.dump(state, f, indent=2, default=str)
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        except Exception as e:
            logger.error(f"Failed to save budget state: {str(e)}")

    def _load_state(self):
        """Load persisted budget state with file locking"""
        try:
            state_file = self.storage_dir / "budget_state.json"
            if not state_file.exists():
                return

            with open(state_file, 'r') as f:
                try:
                    # Acquire shared lock (LOCK_SH) for reading
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    state = json.load(f)
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            # Restore sessions
            for sid, data in state.get("sessions", {}).items():
                # Convert datetime strings back
                data['created_at'] = datetime.fromisoformat(data['created_at'])
                data['last_updated'] = datetime.fromisoformat(data['last_updated'])
                data['alerts_sent'] = []  # Don't restore alerts
                self.session_budgets[sid] = SessionBudget(**data)

            # Restore daily budgets
            for date, data in state.get("daily", {}).items():
                data['alerts_sent'] = []  # Don't restore alerts
                self.daily_budgets[date] = DailyBudget(**data)

            logger.info(f"✓ Loaded budget state: {len(self.session_budgets)} sessions, "
                       f"{len(self.daily_budgets)} daily records")

        except Exception as e:
            logger.error(f"Failed to load budget state: {str(e)}")


# Global instance
_budget_tracker: Optional[BudgetTracker] = None


def get_budget_tracker() -> BudgetTracker:
    """Get global budget tracker instance"""
    global _budget_tracker
    if _budget_tracker is None:
        _budget_tracker = BudgetTracker()
    return _budget_tracker


def initialize_budget_tracker(
    session_budget_cents: int = 1000,
    daily_budget_cents: int = 10000
) -> BudgetTracker:
    """Initialize global budget tracker"""
    global _budget_tracker
    _budget_tracker = BudgetTracker(
        default_session_budget_cents=session_budget_cents,
        default_daily_budget_cents=daily_budget_cents
    )
    logger.info("✓ Global budget tracker initialized")
    return _budget_tracker
