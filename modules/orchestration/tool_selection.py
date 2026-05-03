"""
ToolSelectionEngine
Intelligently selects tools based on target characteristics.
"""
import re
from typing import Dict, List, Any, Optional

class ToolSelectionEngine:
    """
    Determines which tools to run based on asset discovery.
    Implements trigger conditions for Tier 2 and Tier 3 tools.
    """

    TRIGGER_PATTERNS = {
        'api_endpoint_detected': [
            r'/api/v',
            r'/graphql',
            r'/rest/',
            r'/swagger',
            r'/openapi',
            r'application/json',
        ],
        'graphql_detected': [
            r'/graphql',
            r'__typename',
            r'query.*mutation',
        ],
        'cloud_assets_detected': [
            r'amazonaws.com',
            r'cloudapp.azure.com',
            r'cloud.google.com',
            r'AC[0-9A-Z]{10}',  # AWS account IDs
        ],
        'jwt_detected': [
            r'eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*',
            r'Header.*Payload.*Signature',
        ],
        'git_repository_detected': [
            r'/.git/',
            r'github.com/',
            r'gitlab.com/',
        ],
        'mobile_application_detected': [
            r'\.apk$',
            r'\.ipa$',
            r'/api/v[0-9]+/mobile',
        ],
        'container_detected': [
            r'docker',
            r'containers',
            r'kubernetes',
            r'k8s',
        ]
    }

    def __init__(self):
        self.trigger_cache = {}

    def analyze_target(self, target: str, recon_data: Dict) -> Dict[str, List[str]]:
        """
        Analyze target and determine which tools to trigger.

        Args:
            target: Target URL/domain
            recon_data: Data from reconnaissance phase

        Returns:
            Dictionary of trigger conditions with matching tools
        """
        triggers = {
            'tier_1_always': [],
            'tier_2_conditional': [],
            'tier_3_manual': []
        }

        # Tier 1 always runs
        triggers['tier_1_always'] = self._get_tier1_tools()

        # Check Tier 2 triggers
        if self._check_trigger('api_endpoint_detected', target, recon_data):
            triggers['tier_2_conditional'].extend(['kiterunner', 'restler'])

        if self._check_trigger('graphql_detected', target, recon_data):
            triggers['tier_2_conditional'].append('graphqlmap')

        if self._check_trigger('cloud_assets_detected', target, recon_data):
            triggers['tier_2_conditional'].extend(['prowler', 'scoutsuite', 'trivy'])

        if self._check_trigger('jwt_detected', target, recon_data):
            triggers['tier_2_conditional'].extend(['jwt_tool', 'authmatrix'])

        if self._check_trigger('git_repository_detected', target, recon_data):
            triggers['tier_2_conditional'].extend(['trufflehog', 'gitleaks'])

        if self._check_trigger('container_detected', target, recon_data):
            triggers['tier_2_conditional'].append('trivy')

        # Tier 3 manual (requires explicit trigger or high-value target)
        triggers['tier_3_manual'] = [
            'domdig', 'csp_evaluator',
            'bloodhound', 'crackmapexec',
            'mobsf', 'racetheweb', 'fuxploider'
        ]

        return triggers

    def _get_tier1_tools(self) -> List[str]:
        """Get list of Tier 1 tools that always run."""
        return [
            'amass', 'subfinder', 'spiderfoot', 'theharvester',
            'masscan', 'nmap', 'naabu', 'httpx',
            'gau', 'katana', 'arjun', 'ffuf',
            'nuclei', 'dalfox', 'sqlmap', 'ghauri', 'ssrfmap', 'xsstrike'
        ]

    def _check_trigger(self, trigger_name: str, target: str, recon_data: Dict) -> bool:
        """Check if a trigger condition is met."""
        patterns = self.TRIGGER_PATTERNS.get(trigger_name, [])

        # Check target URL
        for pattern in patterns:
            if re.search(pattern, target, re.IGNORECASE):
                return True

        # Check recon data
        for pattern in patterns:
            if re.search(pattern, str(recon_data), re.IGNORECASE):
                return True

        return False

    def get_redundancy_pair(self, tool_name: str) -> Optional[str]:
        """Get secondary tool for double redundancy."""
        redundancy_map = {
            'dalfox': 'xsstrike',
            'sqlmap': 'ghauri',
            'nuclei': 'nikto',
            'trufflehog': 'gitleaks'
        }
        return redundancy_map.get(tool_name)
