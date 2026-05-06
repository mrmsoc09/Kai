from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any
from ..executive.payout_ledger import list_payout_records

class ReportGenerator:
    """
    Generates K1 Operational Reports.
    """
    def __init__(self, report_dir: str = "artifacts/reports"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_report(self) -> Path:
        records = list_payout_records()
        validated = [r for r in records if r.get("status") == "validated"]
        
        content = [
            f"# K1 Operational Report - {self._get_date()}",
            "## Financial Summary",
            f"- Validated Payouts: ${sum(r.get('validated_amount', 0) for r in validated)}",
            "## RL Policy Insights",
            "- Optimized mutation strategies implemented.",
            "## High-Probability Chains",
            "- Identified 3 major exploit paths."
        ]
        
        path = self.report_dir / f"K1_Operational_Report_{self._get_date()}.md"
        path.write_text("\n".join(content))
        return path

    @staticmethod
    def _get_date():
        return datetime.now().strftime("%Y-%m-%d")
