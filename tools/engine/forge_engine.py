#!/usr/bin/env python3
"""
Forge Engine - Autonomous Security Tool Generator
Main orchestrator for the tool creation pipeline.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any

from architect import Architect
from scaffolder import Scaffolder
from builder import Builder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ForgeEngine:
    """
    Core engine that orchestrates the autonomous tool creation process.
    Implements the Kimi k2.5 architectural design philosophy:
    - Hierarchical planning
    - Modular composition
    - Self-correcting validation
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.architect = Architect()
        self.scaffolder = Scaffolder()
        self.builder = Builder()
        self.project_history = []
        
    def forge(self, description: str, output_dir: str, name: str, 
              standalone: bool = True, verbose: bool = False) -> Dict[str, Any]:
        """
        Main pipeline: Design -> Scaffold -> Build
        
        Args:
            description: High-level natural language description of the tool
            output_dir: Target directory for the project
            name: Project name
            standalone: Whether to compile to binary
            verbose: Debug output
            
        Returns:
            Dict containing project metadata and build artifacts
        """
        logger.info(f"🔥 Initializing Forge Engine for project: {name}")
        logger.info(f"📋 Description: {description}")
        
        # Phase 1: AI-Driven Architecture Design (Kimi k2.5 Logic)
        logger.info("🧠 Phase 1: Architectural Design")
        blueprint = self.architect.design(description, name)
        
        if verbose:
            logger.debug(f"Blueprint: {json.dumps(blueprint, indent=2)}")
            
        # Phase 2: Project Scaffolding
        logger.info("🏗️  Phase 2: Project Scaffolding")
        project_path = self.scaffolder.create_project(
            blueprint=blueprint,
            output_dir=output_dir,
            project_name=name
        )
        
        # Phase 3: Dependency Resolution & Compilation
        if standalone:
            logger.info("📦 Phase 3: Building Standalone Binary")
            build_result = self.builder.compile(
                project_path=project_path,
                project_name=name,
                entry_point="main.py"
            )
        else:
            logger.info("📦 Phase 3: Dependency Installation")
            build_result = self.builder.install_dependencies(project_path)
            
        result = {
            "project_name": name,
            "blueprint": blueprint,
            "project_path": str(project_path),
            "build_success": build_result["success"],
            "artifacts": build_result.get("artifacts", []),
            "dependencies": blueprint.get("dependencies", [])
        }
        
        self.project_history.append(result)
        logger.info(f"✅ Forge complete: {project_path}")
        
        return result
    
    def validate_blueprint(self, blueprint: Dict[str, Any]) -> bool:
        """
        Validates architectural blueprint against security and structural constraints.
        """
        required_keys = ["components", "entry_points", "dependencies", "architecture_type"]
        return all(key in blueprint for key in required_keys)


def main():
    parser = argparse.ArgumentParser(
        description="Forge Engine - Autonomous Security Tool Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --description "TCP port scanner with SYN stealth mode" --name "stealthscan"
  %(prog)s --description "Log analyzer for SSH brute force detection" --name "sshguard" --no-standalone
        """
    )
    
    parser.add_argument(
        "-d", "--description",
        required=True,
        help="High-level description of the tool to build"
    )
    
    parser.add_argument(
        "-n", "--name",
        required=True,
        help="Project name (used for directory and binary)"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="./forged_tools",
        help="Output directory for generated projects (default: ./forged_tools)"
    )
    
    parser.add_argument(
        "--no-standalone",
        action="store_true",
        help="Skip binary compilation, keep as Python package only"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug output"
    )
    
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file"
    )
    
    args = parser.parse_args()
    
    engine = ForgeEngine(config_path=args.config)
    
    try:
        result = engine.forge(
            description=args.description,
            output_dir=args.output,
            name=args.name,
            standalone=not args.no_standalone,
            verbose=args.verbose
        )
        
        if result["build_success"]:
            print(f"\n🎉 Success! Tool generated at: {result['project_path']}")
            if result["artifacts"]:
                print(f"📦 Binary location: {result['artifacts'][0]}")
        else:
            print("\n❌ Build failed. Check logs for details.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Forge failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
