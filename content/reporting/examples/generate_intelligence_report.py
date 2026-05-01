"""
Example: Generate an Intelligence Report
"""

from datetime import datetime
from pathlib import Path

from content_engine.models.intelligence import (
    IntelligenceReport,
    IntelligenceMetadata,
    IntelligenceType,
    Source,
    Classification
)
from content_engine.generators.intelligence import IntelligenceReportGenerator


def main():
    # Create report metadata
    metadata = IntelligenceMetadata(
        title="Analysis of Cyber Threat Activity in Sector 7",
        author="Analyst Team Alpha",
        classification=Classification.CONFIDENTIAL,
        intel_type=IntelligenceType.CYBERINT,
        report_date=datetime.utcnow(),
        distribution="Distribution Statement B",
        countries_mentioned=["Eastern Europe", "Asia Pacific"],
        topics=["Cyber Espionage", "Critical Infrastructure"],
        tags=["cyber", "apt", "infrastructure"]
    )
    
    # Create sources
    sources = [
        Source(
            name="SIGINT Collection X-47",
            reliability="A",
            credibility="1",
            description="Intercepted communications"
        ),
        Source(
            name="HUMINT Asset BRAVO",
            reliability="B",
            credibility="2",
            description="Human intelligence source"
        )
    ]
    
    # Create the report
    report = IntelligenceReport(
        metadata=metadata,
        sources=sources,
        key_findings=[
            "Advanced persistent threat group targeting energy sector",
            "Use of zero-day vulnerabilities in industrial control systems",
            "Command and control infrastructure identified in three countries"
        ],
        assessment="High confidence assessment indicates state-sponsored activity with intent to establish long-term access to critical infrastructure networks.",
        confidence_level="High",
        handling_instructions="Handle via secure channels only. Not releasable to foreign nationals.",
        summary="Comprehensive analysis of cyber threat activity targeting critical infrastructure."
    )
    
    # Generate the report
    generator = IntelligenceReportGenerator(output_dir=Path("./output"))
    output_path = generator.generate(report, output_file="cyber_threat_report.md")
    
    print(f"Report generated: {output_path}")
    
    # Also generate just the executive summary
    summary = generator.generate_executive_summary(report)
    print("\nExecutive Summary:")
    print(summary)


if __name__ == "__main__":
    main()
