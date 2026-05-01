"""
Tool Batch Execution Helper
Provides scan_batch() mixin for all tool wrappers.
"""
from typing import List, Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

class BatchScanMixin:
    """
    Mixin class adding batch scan capability to any tool.
    Enables parallel execution across multiple targets.
    """

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def scan_batch(
        self,
        targets: List[str],
        ports: Optional[List[int]] = None,
        options: Optional[Dict] = None,
        **kwargs
    ) -> List[Dict]:
        """
        Scan multiple targets in parallel.

        Args:
            targets: List of target IPs/URLs/hostnames
            ports: Optional port list (for port scanners)
            options: Additional scan options
            **kwargs: Extra parameters for specific tools

        Returns:
            List of scan results for each target
        """
        import concurrent.futures

        options = options or {}
        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all scans
            future_to_target = {
                executor.submit(self.scan_single, target, ports, options, **kwargs): target
                for target in targets
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_target):
                target = future_to_target[future]
                try:
                    result = future.result(timeout=300)  # 5 min timeout per target
                    results.append({
                        'target': target,
                        'success': True,
                        'results': result,
                        'timestamp': self._get_timestamp()
                    })
                except Exception as e:
                    results.append({
                        'target': target,
                        'success': False,
                        'error': str(e),
                        'timestamp': self._get_timestamp()
                    })

        return sorted(results, key=lambda x: targets.index(x['target']))

    def scan_single(self, target: str, ports, options, **kwargs):
        """
        Single target scan - override in tool class.
        This is the method that gets parallelized.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement scan_single()"
        )

    def _get_timestamp(self):
        """Get current ISO timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()

    def scan_batch_fast(
        self,
        targets: List[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fast batch scan optimized for many targets.
        Returns aggregated results instead of individual details.
        """
        all_results = self.scan_batch(targets, **kwargs)

        successful = [r for r in all_results if r['success']]
        failed = [r for r in all_results if not r['success']]

        return {
            'summary': {
                'total_targets': len(targets),
                'successful': len(successful),
                'failed': len(failed),
                'success_rate': len(successful) / len(targets) if targets else 0
            },
            'successful_scans': successful,
            'failed_scans': failed,
            'aggregated_findings': self._aggregate_findings(successful)
        }

    def _aggregate_findings(self, results: List[Dict]) -> Dict:
        """
        Aggregate findings across all targets.
        Override for tool-specific aggregation.
        """
        return {
            'total_findings': sum(
                len(r.get('results', {}).get('findings', []))
                for r in results
            ),
            'by_severity': self._count_by_severity(results)
        }

    def _count_by_severity(self, results: List[Dict]) -> Dict:
        """
        Count findings by severity.
        """
        counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}

        for result in results:
            findings = result.get('results', {}).get('findings', [])
            for finding in findings:
                sev = finding.get('severity', 'info').lower()
                if sev in counts:
                    counts[sev] += 1
                else:
                    counts['info'] += 1

        return counts

# Export convenience function for batch execution
def batch_execute(tools: List[Any], targets: List[str]) -> Dict[str, List]:
    """
    Execute multiple tools against multiple targets.
    Returns tool-specific results for each target.
    """
    results_by_tool = {}

    for tool in tools:
        tool_name = tool.__class__.__name__
        if hasattr(tool, 'scan_batch'):
            results_by_tool[tool_name] = tool.scan_batch(targets)
        else:
            results_by_tool[tool_name] = [
                {'error': f'{tool_name} does not support batch scanning'}
            ]

    return results_by_tool
