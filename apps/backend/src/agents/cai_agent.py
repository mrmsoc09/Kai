"""Cybersecurity AI (CAI) Agent Wrapper for KaisonOne."""
import os, sys, json, logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

sys.path.insert(0, '/a0/usr/projects/kaisonone/vendor/cai')

from core.agent_base import KaisonAgent, AgentConfig, AgentContext
from core.governance import GovernanceController
from core.llm_budget_router import LLMBudgetRouter

logger = logging.getLogger(__name__)

@dataclass
class CAIResult:
    success: bool
    vulnerabilities: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    evidence: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

class CAIAgent(KaisonAgent):
    """Wrapper for Alias Robotics CAI framework."""

    def __init__(self, config=None):
        super().__init__(config or self._default_config())
        self.cai_available = self._check_cai_installation()
        self.llm_router = LLMBudgetRouter()

    def _default_config(self):
        return AgentConfig(
            name="cai_agent",
            description="Cybersecurity AI agent",
            execution_mode="native",
            category="orchestration",
            requires_approval=True
        )

    def _check_cai_installation(self):
        cai_path = '/a0/usr/projects/kaisonone/vendor/cai'
        return os.path.exists(cai_path)

    async def execute(self, target: str, context: AgentContext) -> CAIResult:
        if not self.cai_available:
            return CAIResult(success=False, errors=["CAI not installed"])

        gov = GovernanceController()
        if not await gov.check_agent_execution(self.config.name, context):
            return CAIResult(success=False, errors=["Governance approval required"])

        try:
            from cai.core import CyberAI
            cai = CyberAI(llm_router=self.llm_router, target=target)
            results = await cai.analyze()

            vulns = self._transform_findings(results.get('findings', []))
            critical = sum(1 for v in vulns if v.get('severity') == 'critical')
            if critical > 0:
                await gov.submit_for_approval(self.config.name, target, vulns, context)

            return CAIResult(
                success=True, vulnerabilities=vulns,
                recommendations=results.get('recommendations', []),
                risk_score=results.get('risk_score', 0.0),
                evidence=results.get('evidence', {})
            )
        except Exception as e:
            return CAIResult(success=False, errors=[str(e)])

    def _transform_findings(self, findings):
        severity_map = {'critical': 'critical', 'high': 'high', 'medium': 'medium', 'low': 'low', 'info': 'low'}
        return [{
            'title': f.get('name', 'Unnamed'),
            'severity': severity_map.get(f.get('severity', 'medium'), 'medium'),
            'description': f.get('description', ''),
            'remediation': f.get('fix', 'No remediation'),
            'tool_source': 'cai'
        } for f in findings]
