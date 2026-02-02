from __future__ import annotations

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import security configurations and middleware
from apps.backend.src.config.cors_config import get_cors_config, print_cors_config
from apps.backend.src.middleware.rate_limit import RateLimitMiddleware
from apps.backend.src.middleware.csrf import CSRFProtectionMiddleware
from apps.backend.src.middleware.security_headers import SecurityHeadersMiddleware

# Import routers exactly once
from apps.backend.src.routers import (
    agent0,
    agent_training,
    auth,
    autonomous,
    chains,
    docs,
    dorks,
    embeddings,
    evidence,
    export,
    finding_validation,
    findings,
    graph,
    intel,
    kai_authorized_scanning,
    knowledge,
    logs,
    mailer,
    mcp,
    metrics,
    model_bidding,
    orchestration,
    orchestrator,
    persona,
    planner,
    programs,
    programs_discovery,
    realtime,
    recordings,
    reports,
    runs,
    scope,
    state,
    tools,
)
from apps.backend.src.routers import triage


app = FastAPI(title="K1 Backend")

# ==================== SECURITY MIDDLEWARE ====================
# Order matters: innermost middleware is applied last to responses

# 1. Security Headers (should be last, applied to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# 2. CSRF Protection (before rate limiting)
app.add_middleware(CSRFProtectionMiddleware)

# 3. Rate Limiting (before CORS)
app.add_middleware(RateLimitMiddleware)

# 4. CORS (outermost, handles preflight requests)
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)

# Print CORS configuration for debugging
if os.getenv("DEBUG_MODE", "false").lower() == "true":
    print_cors_config()

# Health
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

# Register routers (logical groups)
# Public/low-priv status endpoints first
app.include_router(state.router)
app.include_router(metrics.router)

# Auth and scope
app.include_router(auth.router)
app.include_router(scope.router)

# Knowledge / OSINT utilities
app.include_router(dorks.router)
app.include_router(knowledge.router)
app.include_router(graph.router)

# Core operations (Tools and orchestration)
app.include_router(tools.router)
app.include_router(orchestrator.router)
app.include_router(planner.router)
app.include_router(chains.router)
app.include_router(embeddings.router)
app.include_router(intel.router)
app.include_router(mcp.router)

# Model Bidding and Orchestration (v7.4)
app.include_router(model_bidding.router)
app.include_router(orchestration.router)

# Autonomous Multi-Agent Systems (NEW)
app.include_router(autonomous.router)

# Agent Training and Skill Management (NEW)
app.include_router(agent_training.router)

# Finding Validation Workflow (NEW)
app.include_router(finding_validation.router)

# Evidence and findings lifecycle
app.include_router(evidence.router)
app.include_router(findings.router)
app.include_router(recordings.router)
app.include_router(reports.router)
app.include_router(export.router)
app.include_router(programs.router)
app.include_router(programs_discovery.router)
app.include_router(runs.router)

# Communications and logs
app.include_router(mailer.router)
app.include_router(logs.router)
app.include_router(agent0.router)
app.include_router(docs.router)
app.include_router(triage.router)

# Kai Security - Authorized scanning with guardrails
app.include_router(kai_authorized_scanning.router)

# Optional: dynamic vector router (pgvector) if present
try:
    import importlib
    _vector_mod = importlib.import_module('apps.backend.src.routers.vector')
    app.include_router(_vector_mod.router)

except Exception:
    pass

# Optional: Agent Zero integration
try:
    agent_zero_router = importlib.import_module('apps.backend.src.routers.agent_zero')
    app.include_router(agent_zero_router.router)
except Exception:
    pass

# Optional: Real-time WebSocket
try:
    ws_router = importlib.import_module('apps.backend.src.routers.websocket')
    app.include_router(ws_router.router)
except Exception:
    pass


# ==================== INITIALIZE K1 SYSTEMS ====================

# Multi-LLM Provider Initialization
from apps.backend.src.core.llm_providers import llm_factory
import asyncio

# Initialize from environment variables
@app.on_event("startup")
async def initialize_llm_providers():
    """Initialize multi-LLM provider system"""
    print("\n" + "="*60)
    print("INITIALIZING K1 LLM PROVIDERS")
    print("="*60)

    try:
        llm_factory.initialize_from_env()
        print("✓ LLM providers initialized")
        print(f"  Primary provider: {llm_factory.primary_provider.value if llm_factory.primary_provider else 'Not set'}")
        print(f"  Fallback providers: {', '.join([p.value for p in llm_factory.fallback_chain])}")
    except Exception as e:
        print(f"✗ LLM initialization error: {str(e)}")

    # MCP Server Initialization
    print("\n" + "-"*60)
    print("INITIALIZING MCP SERVERS")
    print("-"*60)

    try:
        from apps.backend.src.mcp_base import mcp_manager
        from apps.backend.src.mcp_servers.validator_mcp import validator_server
        from apps.backend.src.mcp_servers.analysis_mcp import analysis_server
        from apps.backend.src.mcp_servers.osint_mcp import osint_server
        from apps.backend.src.mcp_servers.graph_mcp import graph_server

        # Register servers
        mcp_manager.register_server(validator_server)
        mcp_manager.register_server(analysis_server)
        mcp_manager.register_server(osint_server)
        mcp_manager.register_server(graph_server)

        # Start all servers
        await mcp_manager.start_all_servers()
        print("✓ All MCP servers started")

    except Exception as e:
        print(f"✗ MCP initialization error: {str(e)}")

    # A2A Communication System Initialization
    print("\n" + "-"*60)
    print("INITIALIZING AGENT-TO-AGENT COMMUNICATION")
    print("-"*60)

    try:
        from apps.backend.src.core.agent_a2a import initialize_a2a

        agent_registry, a2a_bus, workflow_orchestrator = initialize_a2a()
        print("✓ A2A communication system ready")
        print(f"  Agents registered: {len(agent_registry.agents)}")

    except Exception as e:
        print(f"✗ A2A initialization error: {str(e)}")

    # Agent Zero Integration Initialization
    print("\n" + "-"*60)
    print("INITIALIZING AGENT ZERO INTEGRATION")
    print("-"*60)

    try:
        from apps.backend.src.core.agent_zero_integration import (
            initialize_agent_zero_integration,
            AgentZeroCommandProcessor
        )
        from apps.backend.src.core.agent_zero_k1_customization import (
            initialize_k1_orchestrator
        )

        agent_zero_bridge = initialize_agent_zero_integration()

        # Initialize K1-specific orchestrator
        k1_orchestrator = initialize_k1_orchestrator(agent_registry, a2a_bus, mcp_manager)
        print("✓ K1-customized Agent Zero orchestrator ready")

        # Register with Agent Zero
        if await agent_zero_bridge.register_with_agent_zero():
            print("✓ Registered with Agent Zero")
        else:
            print("⚠ Agent Zero not available (running in standalone mode)")

        # Start command processor
        command_processor = AgentZeroCommandProcessor(agent_zero_bridge, workflow_orchestrator)
        asyncio.create_task(command_processor.start())
        print("✓ Agent Zero command processor running")

    except Exception as e:
        print(f"⚠ Agent Zero initialization (optional): {str(e)}")

    # Autonomous Multi-Agent Systems Initialization
    print("\n" + "-"*60)
    print("INITIALIZING AUTONOMOUS MULTI-AGENT SYSTEMS")
    print("-"*60)

    try:
        from apps.backend.src.core.autonomous_agent_system import (
            initialize_autonomous_system
        )
        from apps.backend.src.core.autonomous_reasoning import (
            initialize_reasoning_engine
        )
        from apps.backend.src.core.swarm_coordination import (
            initialize_swarm_coordinator
        )

        # Initialize reasoning engine
        reasoning_engine = initialize_reasoning_engine(llm_factory.complete)
        print("✓ Autonomous reasoning engine initialized")

        # Initialize swarm coordinator
        swarm_coordinator = initialize_swarm_coordinator(llm_factory.complete)
        print("✓ Swarm coordination system initialized")

        # Initialize autonomous multi-agent system
        autonomous_system = initialize_autonomous_system(
            llm_factory.complete,
            agent_registry=agent_registry if 'agent_registry' in locals() else None,
            reasoning_engine=reasoning_engine,
            swarm_coordinator=swarm_coordinator
        )
        print("✓ Autonomous multi-agent system initialized")
        print(f"  Autonomous agents created: {len(autonomous_system.agents) if hasattr(autonomous_system, 'agents') else 0}")

        # Store globally for API access
        import apps.backend.src.core.autonomous_agent_system as autonomous_module
        autonomous_module.autonomous_system = autonomous_system
        autonomous_module.reasoning_engine = reasoning_engine
        autonomous_module.swarm_coordinator = swarm_coordinator

        # Also set in router for API endpoints
        from apps.backend.src.routers.autonomous import set_systems
        set_systems(autonomous_system, reasoning_engine, swarm_coordinator)

    except Exception as e:
        print(f"⚠ Autonomous systems initialization (optional): {str(e)}")

    # Agent Training System with HiL Approval
    print("\n" + "-"*60)
    print("INITIALIZING AGENT TRAINING SYSTEM")
    print("-"*60)

    try:
        from apps.backend.src.core.agent_training import (
            initialize_training_system,
            TrainingType
        )

        # Initialize training system
        training_system = initialize_training_system(llm_factory.complete)

        # Create some default curriculums
        for skill in ["reconnaissance", "validation", "analysis", "exploitation", "reporting"]:
            curriculum = await training_system.create_curriculum(
                skill_name=skill,
                target_proficiency=0.8,
                training_type=TrainingType.PRACTICE,
                description=f"Standard curriculum for {skill} skill development"
            )
            print(f"  ✓ Created curriculum: {skill}")

        # Store globally for API access
        import apps.backend.src.core.agent_training as training_module
        training_module.training_system = training_system

        # Also set in router
        from apps.backend.src.routers.agent_training import router as training_router
        # Note: Router will access via get_systems() function

        print("✓ Agent training system initialized with default curriculums")

    except Exception as e:
        print(f"⚠ Training system initialization (optional): {str(e)}")

    # Finding Validation & Exploit Chaining Systems
    print("\n" + "-"*60)
    print("INITIALIZING FINDING VALIDATION & ROUTING SYSTEMS")
    print("-"*60)

    try:
        from apps.backend.src.core.duplicate_detection import initialize_duplicate_detection
        from apps.backend.src.core.exploit_chaining import initialize_chaining_engine
        from apps.backend.src.core.finding_router import initialize_finding_router
        from apps.backend.src.core.episodic_memory import initialize_episodic_memory

        # Initialize duplicate detection
        dup_detection = initialize_duplicate_detection()
        print("✓ Duplicate detection system initialized")

        # Initialize exploit chaining
        chaining = initialize_chaining_engine(llm_factory.complete)
        print("✓ Exploit chaining engine initialized")

        # Initialize finding router
        router = initialize_finding_router()
        print("✓ Finding router initialized")

        # Initialize episodic memory
        memory = initialize_episodic_memory()
        print("✓ Episodic memory system initialized")

        # Store globally for API access
        import apps.backend.src.core.duplicate_detection as dup_module
        import apps.backend.src.core.exploit_chaining as chain_module
        import apps.backend.src.core.finding_router as router_module
        import apps.backend.src.core.episodic_memory as memory_module

        dup_module.duplicate_detection_system = dup_detection
        chain_module.chaining_engine = chaining
        router_module.finding_router = router
        memory_module.episodic_memory = memory

        print("✓ All finding validation systems ready")

    except Exception as e:
        print(f"⚠ Finding systems initialization (optional): {str(e)}")

    # Model Bidding & Intelligent Routing (v7.4)
    print("\n" + "-"*60)
    print("INITIALIZING INTELLIGENT MODEL BIDDING SYSTEM")
    print("-"*60)

    try:
        from apps.backend.src.core.model_bidding import UniversalModelFactory

        model_factory = UniversalModelFactory()
        print("✓ Model factory initialized")

        # Discover available models
        discovery = await asyncio.to_thread(model_factory.discover_models)
        print(f"✓ Model discovery complete")
        print(f"  Local models found: {len(discovery['local_models'])}")
        print(f"  Cloud APIs available: {len(discovery['cloud_models'])}")
        print(f"  Active providers: {', '.join(discovery['available_providers'])}")

        # Set system reference in router
        from apps.backend.src.routers import model_bidding as mb_router
        mb_router.set_systems(model_factory, None)

    except Exception as e:
        print(f"⚠ Model bidding initialization (optional): {str(e)}")

    # Orchestration Graph & State Machine (v7.4)
    print("\n" + "-"*60)
    print("INITIALIZING HUNTING ORCHESTRATION GRAPH")
    print("-"*60)

    try:
        from apps.backend.src.core.orchestration_graph import (
            initialize_orchestration_graph
        )

        # Initialize with default session for testing
        orchestration_graph = initialize_orchestration_graph(
            session_id="default-session",
            target_domain="default.local",
            mission="Initialization test session"
        )
        print("✓ Orchestration graph initialized")
        print(f"  Starting phase: {orchestration_graph.session.current_phase.value}")
        print(f"  Audit trail enabled: True")

        # Set system references in routers
        from apps.backend.src.routers import orchestration as orch_router
        orch_router.set_orchestration_graph(orchestration_graph)

        # Update model bidding router with orchestration graph reference
        if 'model_factory' in locals():
            from apps.backend.src.routers import model_bidding as mb_router
            mb_router.set_systems(model_factory, orchestration_graph)

    except Exception as e:
        print(f"⚠ Orchestration graph initialization (optional): {str(e)}")

    print("\n" + "="*60)
    print("K1 SYSTEMS INITIALIZED SUCCESSFULLY")
    print("="*60 + "\n")


@app.on_event("shutdown")
async def shutdown_systems():
    """Clean shutdown of all K1 systems"""
    print("\nShutting down K1 systems...")

    try:
        from apps.backend.src.mcp_base import mcp_manager

        await mcp_manager.stop_all_servers()
        print("✓ MCP servers stopped")

    except Exception as e:
        print(f"✗ MCP shutdown error: {str(e)}")

    try:
        from apps.backend.src.core.agent_a2a import a2a_bus

        if a2a_bus:
            a2a_bus.clear_messages("all")
            print("✓ A2A bus cleaned up")

    except Exception as e:
        print(f"✗ A2A shutdown error: {str(e)}")

    print("K1 shutdown complete\n")
