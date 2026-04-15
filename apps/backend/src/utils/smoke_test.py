import json
import logging
import random
from datetime import datetime, UTC
from typing import Dict, Any

from Kai.apps.backend.src.agents.reflection.reflection_orchestrator import ReflectionOrchestrator
from Kai.apps.backend.src.agents.reflection.obfuscation.payload_transformer import PayloadTransformer
from Kai.apps.backend.src.core.attack_surface_graph import AttackSurfaceGraph, NodeType, EdgeType
from Kai.apps.backend.src.core.experience_engine import ExperienceEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("K1SmokeTest")

class K1SmokeTest:
    def __init__(self):
        self.graph = AttackSurfaceGraph()
        self.engine = ExperienceEngine.get_instance()
        self.reflector = ReflectionOrchestrator()
        self.transformer = PayloadTransformer()

    def run_full_loop(self):
        logger.info("--- Starting K1 Smoke Test Simulation ---")
        
        # 1. Discover a mock service
        self.graph.add_asset_node("target_node", "web")
        self.graph.add_service_node("nginx_service", 80, "tcp", {"service": "nginx", "version": "1.18"})
        self.graph.create_edge("target_node", "nginx_service", EdgeType.HOSTS)
        logger.info("Step 1: Service mapped to DAG.")

        # 2. Map to a CVE Playbook
        playbook = "nginx_path_traversal_cve_2024_0001"
        payload = "GET /etc/passwd"
        logger.info(f"Step 2: Playbook {playbook} selected.")

        # 3. Polymorphic Payload Generation
        polymorphic = self.transformer.generate_polymorphic_variant(payload)
        logger.info("Step 3: Polymorphic payload generated (Ghost pulse trigger).")

        # 4. Simulate a 403 error -> Reflection Loop
        logger.info("Step 4: Simulating WAF Block (403)...")
        mock_result = {"output": "", "error": "403 Forbidden - Cloudflare WAF"}
        
        mutation_strategy = self.reflector.post_execution_reflection(playbook, mock_result, "target_node")
        
        if mutation_strategy:
            logger.info(f"Step 5: Mutation suggested: {mutation_strategy.get('mutation')}")
            # Final verification
            logger.info("--- Simulation Successful: V-RAD sequence verified ---")
            return {"status": "success", "mutation": mutation_strategy}
        
        return {"status": "failed"}

if __name__ == "__main__":
    test = K1SmokeTest()
    report = test.run_full_loop()
    
    with open("artifacts/reports/mission_audit_report.json", "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Audit report saved to artifacts/reports/mission_audit_report.json")
