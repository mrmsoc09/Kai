"""
Generator for Threat Intelligence Reports.
"""

import json
from pathlib import Path
from typing import Union, Optional

from content_engine.generators.base import BaseGenerator
from content_engine.models.threat_intel import ThreatIntelReport


class ThreatIntelGenerator(BaseGenerator):
    """Generator for threat intelligence reports and IOC exports."""
    
    def __init__(
        self, 
        template_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None
    ):
        super().__init__(
            template_dir=template_dir,
            output_dir=output_dir,
            template_name="threat_intel/indicator_report.md.j2"
        )
    
    def generate(
        self,
        report: ThreatIntelReport,
        output_file: Optional[str] = None,
        include_iocs: bool = True,
        include_ttps: bool = True
    ) -> Union[str, Path]:
        """
        Generate threat intelligence report.
        
        Args:
            report: ThreatIntelReport model
            output_file: Optional output filename
            include_iocs: Include indicators section
            include_ttps: Include TTPs section
            
        Returns:
            Rendered content or file path
        """
        context = report.get_template_context()
        context['include_iocs'] = include_iocs
        context['include_ttps'] = include_ttps
        
        if output_file:
            return self.render_to_file(report, output_file, "threat_intel/full_report.md.j2")
        
        return self.render(report, "threat_intel/full_report.md.j2")
    
    def generate_stix_bundle(self, report: ThreatIntelReport) -> dict:
        """Generate STIX 2.1 compatible bundle."""
        bundle = {
            "type": "bundle",
            "id": f"bundle--{report.id}",
            "spec_version": "2.1",
            "objects": []
        }
        
        # Add indicators
        for indicator in report.indicators:
            bundle["objects"].append({
                "type": "indicator",
                "spec_version": "2.1",
                "id": f"indicator--{indicator.value}",
                "created": report.metadata.created_at.isoformat(),
                "modified": report.metadata.updated_at.isoformat() if report.metadata.updated_at else report.metadata.created_at.isoformat(),
                "name": indicator.description or indicator.value,
                "pattern": f"[{indicator.type.value} = '{indicator.value}']",
                "valid_from": indicator.first_seen.isoformat() if indicator.first_seen else report.metadata.created_at.isoformat(),
                "labels": ["malicious-activity"] if indicator.malicious else ["benign"]
            })
        
        return bundle
    
    def export_iocs(
        self, 
        report: ThreatIntelReport, 
        format: str = "csv"
    ) -> str:
        """Export IOCs in various formats (csv, json, stix)."""
        if format == "json":
            return json.dumps([i.model_dump() for i in report.indicators], indent=2)
        elif format == "stix":
            return json.dumps(self.generate_stix_bundle(report), indent=2)
        else:
            # CSV format
            lines = ["value,type,description,confidence"]
            for ioc in report.indicators:
                lines.append(f"{ioc.value},{ioc.type.value},{ioc.description or ''},{ioc.confidence}")
            return "\n".join(lines)
