from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import timedelta

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.get('/healthz')
async def healthz():
    return {'ok': True}

from .routers import agent0
app.include_router(agent0.router)

# Import and include EPSS router
try:
    from ..routers import epss
    app.include_router(epss.router)
    print("[✓] EPSS router loaded")
except ImportError as e:
    print(f"[!] EPSS router not available: {str(e)}")

# Import and include Discovery Optimizer router
try:
    from ..routers import discovery
    app.include_router(discovery.router)
    print("[✓] Discovery Optimizer router loaded")
except ImportError as e:
    print(f"[!] Discovery Optimizer router not available: {str(e)}")

# Import and include orchestrator router
try:
    from ..routers import orchestrator
    app.include_router(orchestrator.router)
    print("[✓] KaiOrchestrator router loaded")
except ImportError as e:
    print(f"[!] KaiOrchestrator router not available: {str(e)}")

# Import and include log watchdog router
try:
    from ..routers import watchdog
    app.include_router(watchdog.router)
except ImportError:
    print("[!] Log watchdog router not available")

# Import and include notifications router
try:
    from ..routers import notifications
    app.include_router(notifications.router)
    print("[✓] Notifications router loaded")
except ImportError as e:
    print(f"[!] Notifications router not available: {str(e)}")

# Import and include intelligence router
try:
    from ..routers import intelligence
    app.include_router(intelligence.router)
    print("[✓] Intelligence router loaded")
except ImportError as e:
    print(f"[!] Intelligence router not available: {str(e)}")

# Import and include ollama router
try:
    from ..routers import ollama
    app.include_router(ollama.router)
    print("[✓] Ollama router loaded")
except ImportError as e:
    print(f"[!] Ollama router not available: {str(e)}")

# Import and include graph router
try:
    from ..routers import graph
    app.include_router(graph.router)
    print("[✓] Graph router loaded")
except ImportError as e:
    print(f"[!] Graph router not available: {str(e)}")

# Import and include budget router
try:
    from ..routers import budget
    app.include_router(budget.router)
    print("[✓] Budget router loaded")
except ImportError as e:
    print(f"[!] Budget router not available: {str(e)}")

# Import and include code router
try:
    from ..routers import code
    app.include_router(code.router)
    print("[✓] Code tasks router loaded")
except ImportError as e:
    print(f"[!] Code tasks router not available: {str(e)}")

# Import and include Celery task enqueue router (Phase 1 tools)
try:
    from ..routers import tasks
    app.include_router(tasks.router)
    print("[✓] Tasks router loaded")
except ImportError as e:
    print(f"[!] Tasks router not available: {str(e)}")

# Import and include approval router (tool gating)
try:
    from ..routers import approvals
    app.include_router(approvals.router)
    print("[✓] Approvals router loaded")
except ImportError as e:
    print(f"[!] Approvals router not available: {str(e)}")

# Import and include Autonomous Scanning router
try:
    from ..routers import autonomous_scan
    app.include_router(autonomous_scan.router)
    print("[✓] Autonomous Scanning router loaded")
except ImportError as e:
    print(f"[!] Autonomous Scanning router not available: {str(e)}")

# Application startup event - initialize orchestrator and watchdog
@app.on_event("startup")
async def startup_event():
    """Initialize KaiOrchestrator and all platform services on startup"""

    # Initialize Budget Tracker
    try:
        import os
        from ..core.budget_tracker import initialize_budget_tracker

        # Read from environment with sensible defaults
        session_budget = int(os.getenv("KAI_SESSION_BUDGET_CENTS", "1000"))  # $10 default
        daily_budget = int(os.getenv("KAI_DAILY_BUDGET_CENTS", "10000"))     # $100 default

        budget_tracker = initialize_budget_tracker(
            session_budget_cents=session_budget,
            daily_budget_cents=daily_budget
        )

        print(f"[✓] BudgetTracker initialized: ${session_budget/100:.2f}/session, ${daily_budget/100:.2f}/day")
    except Exception as e:
        print(f"[!] BudgetTracker startup error: {str(e)}")

    # Initialize Hybrid Model Router
    try:
        from ..core.hybrid_model_router import initialize_hybrid_router
        from ..core.model_bidding import initialize_model_factory

        # Initialize model factory first
        model_factory = initialize_model_factory()
        await model_factory.discover_models()

        # Initialize hybrid router with budget tracker and model factory
        hybrid_router = initialize_hybrid_router(
            budget_tracker=budget_tracker if 'budget_tracker' in locals() else None,
            model_factory=model_factory
        )

        print("[✓] HybridModelRouter initialized with cost optimization")
    except Exception as e:
        print(f"[!] HybridModelRouter startup error: {str(e)}")

    # Initialize Cost Controller
    try:
        from ..core.cost_controller import initialize_cost_controller

        cost_controller = initialize_cost_controller(
            budget_tracker=budget_tracker if 'budget_tracker' in locals() else None,
            model_factory=model_factory if 'model_factory' in locals() else None
        )

        print("[✓] CostController initialized")
    except Exception as e:
        print(f"[!] CostController startup error: {str(e)}")

    # Initialize CLI Tool Clients (Claude Code, Codex, Gemini)
    try:
        from ..integrations.claude_code_client import initialize_claude_code_client
        from ..integrations.codex_client import initialize_codex_client
        from ..integrations.gemini_cli_client import initialize_gemini_client

        # Verify and initialize CLI tools
        cli_status = {}

        # Claude Code
        try:
            claude_code = initialize_claude_code_client()
            cli_status['claude_code'] = claude_code.available
            if claude_code.available:
                print("[✓] Claude Code CLI initialized")
            else:
                print("[!] Claude Code CLI not available (install: npm install -g @anthropic-ai/claude-code)")
        except Exception as e:
            print(f"[!] Claude Code initialization error: {str(e)}")
            cli_status['claude_code'] = False

        # Codex (OpenAI)
        try:
            codex = initialize_codex_client()
            cli_status['codex'] = codex.available
            if codex.available:
                print("[✓] Codex (OpenAI) initialized")
            else:
                print("[!] Codex not available (set OPENAI_API_KEY)")
        except Exception as e:
            print(f"[!] Codex initialization error: {str(e)}")
            cli_status['codex'] = False

        # Gemini CLI
        try:
            gemini = initialize_gemini_client()
            cli_status['gemini'] = gemini.available
            if gemini.available:
                print("[✓] Gemini CLI initialized")
            else:
                print("[!] Gemini not available (install CLI or set GOOGLE_API_KEY)")
        except Exception as e:
            print(f"[!] Gemini initialization error: {str(e)}")
            cli_status['gemini'] = False

        available_count = sum(1 for v in cli_status.values() if v)
        print(f"[✓] CLI Tools initialized: {available_count}/3 available")

    except Exception as e:
        print(f"[!] CLI Tools startup error: {str(e)}")

    # Initialize KaiOrchestrator
    try:
        from ..core.kai_orchestrator import initialize_kai_orchestrator

        orchestrator = initialize_kai_orchestrator(
            scope_config_path="config/authorized_scope.json",
            permission_slips_vault_path="vault/permission_slips"
        )

        print("[✓] KaiOrchestrator initialized on startup")
    except Exception as e:
        print(f"[!] KaiOrchestrator startup error: {str(e)}")

    # Initialize Watchdog
    try:
        from ..routers import watchdog
        # Watchdog will auto-initialize on first request if needed
        print("[✓] Log watchdog initialized on startup")
    except Exception as e:
        print(f"[!] Watchdog startup: {str(e)}")

    # Initialize NotificationService
    try:
        from ..integrations.notification_service import get_notification_service
        service = get_notification_service()
        await service.initialize()
        print("[✓] NotificationService initialized")
    except Exception as e:
        print(f"[!] NotificationService startup error: {str(e)}")

    # Initialize LlamaIndex RAG System
    try:
        from ..integrations.llamaindex_rag import initialize_rag
        await initialize_rag()
        print("[✓] LlamaIndex RAG system initialized")
    except Exception as e:
        print(f"[!] LlamaIndex RAG startup error: {str(e)}")

    # Initialize Intelligence Engine and start background scanner
    try:
        from ..core.intelligence_engine import start_intelligence_scanner
        await start_intelligence_scanner(interval_minutes=60)
        print("[✓] Intelligence Engine started (scanning every 60 minutes)")
    except Exception as e:
        print(f"[!] Intelligence Engine startup error: {str(e)}")

    # Initialize Repair Pipeline
    try:
        from ..core.repair_pipeline import get_repair_pipeline
        pipeline = get_repair_pipeline()
        print("[✓] Vulnerability Repair Pipeline initialized")
    except Exception as e:
        print(f"[!] Repair Pipeline startup error: {str(e)}")

    # Initialize Autonomous BBP Selector
    try:
        from ..core.autonomous_bbp_selector import get_bbp_selector
        selector = get_bbp_selector()
        print("[✓] Autonomous BBP Selector initialized")
    except Exception as e:
        print(f"[!] BBP Selector startup error: {str(e)}")

    # Initialize Full Scan Orchestrator
    try:
        from ..core.full_scan_orchestrator import get_scan_orchestrator
        orchestrator = get_scan_orchestrator()
        print("[✓] Full Scan Orchestrator initialized")
    except Exception as e:
        print(f"[!] Scan Orchestrator startup error: {str(e)}")

    # Initialize Neo4j Graph Database (optional - may not be configured)
    try:
        import os
        from ..integrations.neo4j_client import initialize_neo4j

        neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        neo4j_password = os.getenv("NEO4J_PASSWORD")

        if neo4j_password:
            await initialize_neo4j(uri=neo4j_uri, user=neo4j_user, password=neo4j_password)
            print("[✓] Neo4j Graph Database initialized")
        else:
            print("[!] Neo4j not configured (missing NEO4J_PASSWORD env var)")
    except Exception as e:
        print(f"[!] Neo4j startup error (optional): {str(e)}")

    # Schedule daily budget reset (runs at midnight UTC)
    try:
        import asyncio
        from datetime import datetime, time

        async def daily_budget_reset_task():
            """Background task to reset daily budget at midnight"""
            while True:
                # Calculate time until next midnight UTC
                now = datetime.utcnow()
                tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                seconds_until_midnight = (tomorrow - now).total_seconds()

                # Wait until midnight
                await asyncio.sleep(seconds_until_midnight)

                # Reset daily budget
                try:
                    from ..core.budget_tracker import get_budget_tracker
                    tracker = get_budget_tracker()
                    await tracker.reset_daily_budget()
                    print(f"[✓] Daily budget reset completed at {datetime.utcnow().isoformat()}")
                except Exception as e:
                    print(f"[!] Daily budget reset error: {str(e)}")

        # Start background task
        asyncio.create_task(daily_budget_reset_task())
        print("[✓] Daily budget reset scheduler started")
    except Exception as e:
        print(f"[!] Budget reset scheduler error: {str(e)}")

    print("[✓] Kaison K1 Platform v7.6 startup complete")
