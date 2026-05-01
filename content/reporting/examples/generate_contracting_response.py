"""
Example: Generate a Government Contracting Response
"""

from decimal import Decimal
from pathlib import Path

from content_engine.models.contracting import (
    ContractingOpportunity,
    ContractingMetadata,
    SolicitationType,
    ContractType
)
from content_engine.generators.contracting import ContractingGenerator


def main():
    # Create metadata
    metadata = ContractingMetadata(
        title="IT Support Services for Federal Agency",
        author="Acme Federal Solutions",
        solicitation_number="FA8675-24-R-1234",
        agency="Department of Defense",
        sub_agency="Air Force",
        naics_codes=["541512", "541519"],
        contract_type=ContractType.IDIQ,
        set_aside="Small Business",
        contract_value=Decimal("25000000.00"),
        place_of_performance="Arlington, VA"
    )
    
    # Create the opportunity
    opportunity = ContractingOpportunity(
        metadata=metadata,
        solicitation_type=SolicitationType.RFP,
        description="Comprehensive IT support services including cybersecurity, cloud migration, and help desk operations.",
        requirements=[
            "Provide 24/7 help desk support",
            "Maintain 99.9% uptime SLA",
            "Comply with NIST 800-171",
            "Hold current CMMC Level 2 certification"
        ],
        evaluation_criteria=[
            {"factor": "Technical Approach", "weight": "40%"},
            {"factor": "Past Performance", "weight": "30%"},
            {"factor": "Price", "weight": "30%"}
        ],
        deliverables=[
            "Monthly status reports",
            "Quarterly security assessments",
            "Annual system architecture reviews"
        ],
        key_personnel=[
            {
                "name": "Jane Smith", 
                "role": "Program Manager", 
                "qualifications": "PMP, CISSP, 15 years experience"
            },
            {
                "name": "John Doe", 
                "role": "Technical Lead", 
                "qualifications": "AWS Solutions Architect, MS Computer Science"
            }
        ],
        past_performance_reqs=[
            "Similar sized contracts within last 3 years",
            "Experience with federal security requirements",
            "Cloud migration projects over $5M"
        ],
        period_of_performance="Base year plus 4 option years",
        clauses=[
            "52.204-21 Basic Safeguarding of Covered Contractor Information Systems",
            "52.204-25 Prohibition on Contracting for Certain Telecommunications and Video Surveillance Services or Equipment"
        ]
    )
    
    # Generate response
    generator = ContractingGenerator(output_dir=Path("./output"))
    output_path = generator.generate(opportunity, output_file="rfp_response.md")
    
    print(f"Contracting response generated: {output_path}")


if __name__ == "__main__":
    main()
