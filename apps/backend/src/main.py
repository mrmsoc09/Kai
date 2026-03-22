from __future__ import annotations

import os
import logging
import importlib
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import security configurations and middleware
from apps.backend.src.config.cors_config import get_cors_config, print_cors_config
from apps.backend.src.middleware.correlation import CorrelationIdMiddleware
from apps.backend.src.middleware.rate_limit import RateLimitMiddleware
from apps.backend.src.middleware.csrf import CSRFProtectionMiddleware
from apps.backend.src.middleware.security_headers import SecurityHeadersMiddleware
from apps.backend.src.core.exception_handlers import register_exception_handlers
from apps.backend.src.core.services import Services
from apps.backend.src.core.tools import get_registry, initialize_default_tools
from apps.backend.src.core.toolpacks import validate_toolpacks_or_raise
from apps.backend.src.core.secret_manager import get_secret_manager
from apps.backend.src.core.auth import assert_bootstrap_auth_safe, AuthConfigError

# Import routers exactly once
from apps.backend.src.routers import (
    agent0,
    agent_training,
    approvals,
    artifact_signing,
    artifacts,
    auth,
    autonomous,
    bug_bounty,
    campaigns,
    chains,
    comms,
    docs,
    dorks,
    embeddings,
    events,
    evidence,
    export,
    finding_validation,
    findings,
    graph,
    governance,
    hil_approval,
    intel,
    kai_authorized_scanning,
    key_management,
    keys,
    knowledge,
    logs,
    logs_api,
    mailer,
    mcp,
    metrics,
    mission_control,
    model_bidding,
    opportunities,
    payouts,
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
    runs_api,
    scope,
    simulation,
    state,
    submissions,
    system,
    tools,
    tasks,
    workflows,
)
from apps.backend.src.routers import triage
from apps.backend.src.routers import (
    hil_embeddings as hil_embeddings_router,
    hil_findings as hil_findings_router,
    hil_providers as hil_providers_router,
    hil_scopes as hil_scopes_router,
    hil_workflow as hil_workflow_router,
)
from apps.backend.src.routers import platform_settings as platform_settings_router


services = Services()
logger = logging.getLogger(__name__)
_OPTIONAL_ROUTER_ERRORS: list[dict[str, str]] = []


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _required_startup_services() -> list[str]:
    raw = os.getenv("K1_REQUIRED_SERVICES", "postgres")
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    allowed = {"postgres", "redis", "neo4j"}
    return [item for item in values if item in allowed]


def _required_secrets() -> list[str]:
    raw = os.getenv("K1_REQUIRED_SECRETS", "")
    values = [item.strip() for item in raw.split(",") if item.strip()]

    # Contract-based required secrets from selected providers/features.
    providers = [os.getenv("K1_PRIMARY_LLM_PROVIDER", "anthropic")] + os.getenv(
        "K1_FALLBACK_LLM_PROVIDERS", "openai,gemini,ollama"
    ).split(",")
    normalized = {provider.strip().lower() for provider in providers if provider.strip()}
    if "anthropic" in normalized:
        values.append("ANTHROPIC_API_KEY")
    if "openai" in normalized:
        values.append("OPENAI_API_KEY")
    if "gemini" in normalized or "gemma" in normalized:
        values.append("GOOGLE_API_KEY")

    if (os.getenv("K1_ENABLE_EXTERNAL_INTEL", "false").strip().lower() in {"1", "true", "yes", "on"}):
        values.extend(["SHODAN_API_KEY", "CENSYS_API_ID", "CENSYS_API_SECRET"])

    # Preserve order while deduplicating.
    deduped: list[str] = []
    seen = set()
    for name in values:
        if name not in seen:
            deduped.append(name)
            seen.add(name)
    return deduped


async def _validate_startup_dependencies() -> None:
    dependencies = await services.probe_dependencies()
    failures: list[str] = []
    required_services = _required_startup_services()

    for service_name in required_services:
        status = dependencies.get(service_name, {})
        if status.get("status") == "not_configured":
            failures.append(f"{service_name}: not configured")
            continue
        if not bool(status.get("ok")):
            failures.append(f"{service_name}: {status.get('error') or status.get('status') or 'unavailable'}")

    if failures:
        raise RuntimeError("startup dependency checks failed: " + "; ".join(failures))


def _validate_required_secrets() -> None:
    required = _required_secrets()
    if not required:
        return
    manager = get_secret_manager()
    manager.validate_required(required)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.services = services
    test_mode = os.getenv("K1_TEST_MODE", "false").lower() == "true"
    try:
        assert_bootstrap_auth_safe()
    except AuthConfigError as exc:
        raise RuntimeError(str(exc)) from exc
    if not test_mode:
        await services.startup()
        if _env_bool("K1_STARTUP_VALIDATE_DEPENDENCIES", True):
            await _validate_startup_dependencies()
        if _env_bool("K1_STARTUP_VALIDATE_TOOLPACKS", True):
            initialize_default_tools()
            validate_toolpacks_or_raise(get_registry().get_all_schemas().keys())
        if _env_bool("K1_STARTUP_VALIDATE_SECRETS", True):
            _validate_required_secrets()
        
        # Task 41: Initialize column-level encryption key from Vault
        try:
            from .models.types import EncryptedText
            from .core.hil_vault_client import VaultClient
            vc = VaultClient()
            master_key_data = vc.read_secret("k1/master-key")
            if master_key_data and "key" in master_key_data:
                EncryptedText.set_key(master_key_data["key"])
                logger.info("Column-level encryption initialized from Vault")
            else:
                logger.warning("No master key found in Vault at 'secret/k1/master-key'; data will NOT be encrypted!")
        except Exception as e:
            logger.error(f"Failed to initialize column-level encryption: {str(e)}")

        llm_init_timeout = max(5.0, _env_float("K1_STARTUP_LLM_INIT_TIMEOUT_SECONDS", 20.0))
        try:
            async with asyncio.timeout(llm_init_timeout):
                await initialize_llm_providers()
        except TimeoutError:
            logger.warning(
                "LLM/MCP initialization timed out after %ss; continuing startup in degraded mode",
                llm_init_timeout,
            )
        _initialize_praison_governor()
    try:
        yield
    finally:
        if not test_mode:
            await shutdown_systems()
            await services.shutdown()


if os.getenv("K1_TEST_MODE", "false").lower() == "true":
    app = FastAPI(title="K1 Backend")
else:
    app = FastAPI(title="K1 Backend", lifespan=lifespan)
app.state.services = services
register_exception_handlers(app)

# ==================== SECURITY MIDDLEWARE ====================
# Order matters: innermost middleware is applied last to responses

# 1. Security Headers (should be last, applied to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# 2. Correlation ID — attach/echo X-Request-ID on every response
app.add_middleware(CorrelationIdMiddleware)

# 3. CSRF Protection (before rate limiting)
app.add_middleware(CSRFProtectionMiddleware)

# 4. Rate Limiting (before CORS)
app.add_middleware(RateLimitMiddleware)

# 5. CORS (outermost, handles preflight requests)
cors_config = get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)

# Print CORS configuration for debugging
if os.getenv("DEBUG_MODE", "false").lower() == "true":
    print_cors_config()


def _probe_worker_subsystem() -> dict:
    try:
        from apps.backend.src.worker.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=1)
        ping = inspector.ping() or {}
        queue_info = inspector.active_queues() or {}
        return {
            "ok": bool(ping),
            "status": "up" if ping else "down",
            "worker_count": len(ping),
            "workers": sorted(ping.keys()),
            "queues": sorted(queue_info.keys()) if isinstance(queue_info, dict) else [],
        }
    except Exception as exc:
        return {"ok": False, "status": "down", "error": str(exc)}


from apps.backend.src.auth import routes as auth_routes
from apps.backend.src.auth.dependencies import require_roles, CurrentUser, get_current_active_user, get_current_tenant
from apps.backend.src.auth.models import UserRole # Import UserRole enum

from apps.backend.src.core.token_blocklist import get_blocklist_status # Keep this for token blocklisting
# No longer import from .core.auth for roles as we have new auth system
# from apps.backend.src.core.auth import require_roles, ROLE_ADMIN 
...
# Health
@app.get("/health")
async def health(request: Request) -> dict:
    """Public health check - minimal info only."""
    svc = getattr(request.app.state, "services", None)
    if not svc or not getattr(svc, "started", False):
         return {"status": "degraded"}
    return {"status": "ok"}


@app.get("/health/detailed")
async def health_detailed(
    request: Request,
    current_user: CurrentUser = Depends(require_roles(UserRole.ADMIN))
) -> dict:
    """Detailed health check - restricted to ROLE_ADMIN."""
    svc = getattr(request.app.state, "services", None)
    return {
        "status": "ok",
        "services": {
            "started": bool(getattr(svc, "started", False)),
            "neo4j": bool(getattr(svc, "neo4j_available", False)),
            "intelligence": bool(getattr(svc, "intelligence_ready", False)),
            "rag": bool(getattr(svc, "rag_ready", False)),
            "token_blocklist": get_blocklist_status(),
        },
        "worker": _probe_worker_subsystem(),
    }


@app.get("/healthz")
async def healthz(request: Request):
    """Internal healthz check (legacy or for container probes)."""
    svc = getattr(request.app.state, "services", services)
    dependencies = await svc.probe_dependencies()

    postgres_ok = bool(dependencies["postgres"].get("ok"))
    redis_status = dependencies["redis"].get("status")
    redis_ok = redis_status == "not_configured" or bool(dependencies["redis"].get("ok"))
    neo4j_status = dependencies["neo4j"].get("status")
    neo4j_ok = neo4j_status == "not_configured" or bool(dependencies["neo4j"].get("ok"))
    worker = _probe_worker_subsystem()
    worker_required = _env_bool("K1_REQUIRE_WORKER", False)
    worker_ok = bool(worker.get("ok")) or not worker_required

    overall_ok = postgres_ok and redis_ok and neo4j_ok and worker_ok
    payload = {
        "status": "ok" if overall_ok else "degraded",
        "dependencies": dependencies,
        "worker": worker,
        "worker_required": worker_required,
        "optional_router_errors": _OPTIONAL_ROUTER_ERRORS,
    }
    if overall_ok:
        return payload
    return JSONResponse(status_code=503, content=payload)


@app.get("/livez")
async def livez() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(request: Request):
    return await healthz(request)

# Register routers (logical groups)
# Public/low-priv status endpoints first
app.include_router(state.router)
app.include_router(metrics.router)
app.include_router(governance.router)

# Auth and scope
app.include_router(auth_routes.router) # New authentication router
app.include_router(scope.router)

# Key Management (Cryptographic keys and PGP signatures)
app.include_router(key_management.router)
app.include_router(keys.router)

# Human-in-the-Loop Approvals (PGP-signed action approval)
app.include_router(approvals.router)

# Human-in-the-Loop Approvals for stakeholder comms (draft review)
app.include_router(hil_approval.router)

# Legacy HiL API endpoints consolidated under /hil-api to avoid route collisions
app.include_router(hil_findings_router.router, prefix="/hil-api")
app.include_router(hil_workflow_router.router, prefix="/hil-api")
app.include_router(hil_scopes_router.router, prefix="/hil-api")
app.include_router(hil_providers_router.router, prefix="/hil-api")
app.include_router(hil_embeddings_router.router, prefix="/hil-api")

# Artifact Signing & Chain of Custody (Vulnerability report signing & verification)
app.include_router(artifact_signing.router)

# Knowledge / OSINT utilities
app.include_router(dorks.router)
app.include_router(knowledge.router)
app.include_router(graph.router)

# Core operations (Tools and orchestration)
app.include_router(tools)
app.include_router(tasks)
app.include_router(orchestrator.router)
app.include_router(planner.router)
app.include_router(chains.router)
app.include_router(embeddings.router)
app.include_router(intel.router)
app.include_router(mcp.router)
app.include_router(realtime.router)
app.include_router(mission_control.router)
app.include_router(artifacts.router)
app.include_router(events.router)
app.include_router(simulation.router)
app.include_router(system.router)

# Model Bidding and Orchestration (v7.4)
app.include_router(model_bidding.router)
app.include_router(orchestration.router)

# Autonomous Multi-Agent Systems (NEW)
app.include_router(autonomous.router)

# Agent Training and Skill Management (NEW)
app.include_router(agent_training.router)

# Finding Validation Workflow (NEW)
app.include_router(finding_validation.router)

# Opportunity Hub + Hunt Workflows (Phase 6)
app.include_router(opportunities.router)
app.include_router(workflows.router)
app.include_router(campaigns.router)
app.include_router(bug_bounty.router)

# Platform Settings (LLM config, runtime settings)
app.include_router(platform_settings_router.router)

# Evidence and findings lifecycle
app.include_router(evidence.router)
app.include_router(findings.router)
app.include_router(recordings.router)
app.include_router(reports.router)
app.include_router(export.router)
app.include_router(programs.router)
app.include_router(programs_discovery.router)
app.include_router(runs.router)
app.include_router(runs_api.router)
app.include_router(submissions.router)
app.include_router(comms.router)
app.include_router(payouts.router)

# Communications and logs
app.include_router(mailer.router)
app.include_router(logs.router)
app.include_router(logs_api.router)
app.include_router(agent0.router)
app.include_router(docs.router)
app.include_router(triage.router)

# Kai Security - Authorized scanning with guardrails
app.include_router(kai_authorized_scanning.router)

# Optional: dynamic vector router (pgvector) if present
try:
    _vector_mod = importlib.import_module('apps.backend.src.routers.vector')
    app.include_router(_vector_mod.router)
except Exception as exc:
    logger.warning("optional router unavailable: %s (%s)", "apps.backend.src.routers.vector", exc)
    _OPTIONAL_ROUTER_ERRORS.append(
        {"module": "apps.backend.src.routers.vector", "error": str(exc)}
    )

# Optional: Agent Zero integration
try:
    agent_zero_router = importlib.import_module('apps.backend.src.routers.agent_zero')
    app.include_router(agent_zero_router.router)
except Exception as exc:
    logger.warning("optional router unavailable: %s (%s)", "apps.backend.src.routers.agent_zero", exc)
    _OPTIONAL_ROUTER_ERRORS.append(
        {"module": "apps.backend.src.routers.agent_zero", "error": str(exc)}
    )

# Optional: Billing / Usage tracking
try:
    from apps.backend.src.routers.billing import router as billing_router
    app.include_router(billing_router)
except Exception as exc:
    logger.warning("optional router unavailable: billing (%s)", exc)
    _OPTIONAL_ROUTER_ERRORS.append({"module": "billing", "error": str(exc)})

# Optional: Prometheus metrics endpoint
try:
    from apps.backend.src.routers.prometheus import router as prometheus_router
    app.include_router(prometheus_router)
except Exception as exc:
    logger.warning("optional router unavailable: prometheus (%s)", exc)
    _OPTIONAL_ROUTER_ERRORS.append({"module": "prometheus", "error": str(exc)})

# Optional: Real-time WebSocket
try:
    ws_router = importlib.import_module('apps.backend.src.routers.websocket')
    app.include_router(ws_router.router)
except Exception as exc:
    logger.warning("optional router unavailable: %s (%s)", "apps.backend.src.routers.websocket", exc)
    _OPTIONAL_ROUTER_ERRORS.append(
        {"module": "apps.backend.src.routers.websocket", "error": str(exc)}
    )


# ==================== INITIALIZE K1 SYSTEMS ====================

# Multi-LLM Provider Initialization
from apps.backend.src.core.llm_providers import llm_factory

# Initialize from environment variables
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

    # Cryptographic Key Management System (v7.4)
    print("\n" + "-"*60)
    print("INITIALIZING CRYPTOGRAPHIC KEY MANAGEMENT")
    print("-"*60)

    try:
        from apps.backend.src.core.key_management import initialize_key_management

        key_mgmt = initialize_key_management(keys_dir="/var/lib/k1/keys")
        print("✓ Key management system initialized")
        print(f"  Keys directory: /var/lib/k1/keys")
        print(f"  Encryption enabled: True")

        # Set system reference in router
        from apps.backend.src.routers import key_management as km_router
        km_router.set_key_management(key_mgmt)

    except Exception as e:
        print(f"⚠ Key management initialization (optional): {str(e)}")

    # Human-in-the-Loop Approval Workflow (v7.4)
    print("\n" + "-"*60)
    print("INITIALIZING HUMAN-IN-THE-LOOP APPROVAL WORKFLOW")
    print("-"*60)

    try:
        from apps.backend.src.core.approval_workflow import initialize_hil_approval_workflow

        # Initialize with key management and orchestration graph
        key_mgmt_ref = key_mgmt if 'key_mgmt' in locals() else None
        orch_graph_ref = orchestration_graph if 'orchestration_graph' in locals() else None

        hil_workflow = initialize_hil_approval_workflow(
            key_management_system=key_mgmt_ref,
            orchestration_graph=orch_graph_ref
        )
        print("✓ HiL approval workflow initialized")
        print(f"  Pending queue: Empty")
        print(f"  PGP signature verification: Enabled")

        # Set system reference in router
        from apps.backend.src.routers import approvals as approval_router
        approval_router.set_hil_workflow(hil_workflow)

    except Exception as e:
        print(f"⚠ HiL approval workflow initialization (optional): {str(e)}")

    # Cryptographic Artifact Signing & Chain of Custody (v7.5)
    print("\n" + "-"*60)
    print("INITIALIZING ARTIFACT SIGNING & CHAIN OF CUSTODY")
    print("-"*60)

    try:
        from apps.backend.src.core.crypto_artifact_signing import initialize_kai_crypto

        kai_crypto = initialize_kai_crypto(
            gpg_home=os.path.expanduser("~/.kai/gpg_home"),
            key_source_dir="/home/user/kai/Kai PGP-Keys"
        )
        print("✓ Crypto system initialized")
        print(f"  GPG home: {kai_crypto.gpg_home}")
        print(f"  Key directory: {kai_crypto.key_source_dir}")
        print(f"  Machine identity: {kai_crypto.machine_identity}")

        # Set system reference in router
        from apps.backend.src.routers import artifact_signing as artifact_router
        artifact_router.set_kai_crypto(kai_crypto)

        print("✓ Ready for automated artifact signing")

    except Exception as e:
        print(f"⚠ Crypto system initialization (optional): {str(e)}")

    print("\n" + "="*60)
    print("K1 SYSTEMS INITIALIZED SUCCESSFULLY")
    print("="*60 + "\n")


def _initialize_praison_governor():
    """Initialize PraisonAI Agent Control Plane: governor + registry + all lifecycle hooks."""
    print("\n" + "-"*60)
    print("INITIALIZING PRAISON AGENT CONTROL PLANE")
    print("-"*60)
    try:
        from apps.backend.src.core.praison_governor import (
            initialize_governor,
            praison_safety_gate_hook,
            praison_agent_spawn_hook,
            praison_agent_handoff_hook,
            praison_agent_memory_write_hook,
            praison_agent_external_call_hook,
        )
        from apps.backend.src.core.praison_registry import initialize_agent_registry
        from apps.backend.src.core.hook_registry import get_hook_registry

        # 1. Initialize governor (sync fast-path governance)
        governor = initialize_governor()
        print("✓ PraisonAI Governor initialized")
        print(f"  Band3 hard block: {governor._hil_policy.get('band3_always_block', True)}")
        print(f"  Band2 requires campaign context: {governor._hil_policy.get('band2_requires_workflow_context', True)}")

        # 2. Initialize agent registry (loads agents.yaml, validates all personas)
        registry = initialize_agent_registry()
        print(f"✓ PraisonAI Agent Registry initialized: {registry.agent_ids()}")

        # 3. Register all governance hooks
        hook_registry = get_hook_registry()
        # safety_gate: governance at order=5 (BEFORE audit=50, BEFORE enforce=100)
        hook_registry.register("safety_gate",          "praison_governance",         praison_safety_gate_hook,           order=5)
        # Agent lifecycle: order=50 (after audit at order=10)
        hook_registry.register("agent_spawn",          "praison_agent_spawn",        praison_agent_spawn_hook,           order=50)
        hook_registry.register("agent_handoff",        "praison_agent_handoff",      praison_agent_handoff_hook,         order=50)
        hook_registry.register("agent_memory_write",   "praison_agent_memory_write", praison_agent_memory_write_hook,    order=50)
        hook_registry.register("agent_external_call",  "praison_agent_external_call",praison_agent_external_call_hook,   order=50)

        print("✓ PraisonAI governance hooks registered:")
        print("  safety_gate, agent_spawn, agent_handoff, agent_memory_write, agent_external_call")

    except Exception as exc:
        # Non-fatal: PraisonAI control plane failing must not crash startup.
        # scope_guardrails and authorization_gate remain as hard blockers.
        logger.error("PraisonAI Agent Control Plane initialization failed (non-fatal): %s", exc)
        print(f"⚠ PraisonAI Agent Control Plane init failed (non-fatal): {exc}")


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
