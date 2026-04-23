# Developer Guide

> How to extend Kai's governed mission orchestration platform.

This guide explains how to add new capabilities to Kai — new agent personas, graph nodes, governed tools, structured schemas, specialist roles, simulation fixtures, evaluation datasets, and telemetry events — while preserving architecture boundaries and security invariants.

**Prerequisite**: Read [Architecture](architecture.md) and [Security Architecture](security-architecture.md) first.

---

## 1. Local Setup

### Prerequisites

- **Python 3.11+** — `python3 --version`
- **Node.js 18+** and npm — `node --version`
- **Docker Engine + Compose plugin** — for PostgreSQL and Redis — `docker compose version`
- At least one LLM API key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`)

On Ubuntu/Debian, `bootstrap.sh` installs system packages (curl, git, pango/cairo libs, build-essential) and all Python/Node deps automatically.

### Installation

```bash
git clone https://github.com/mrmsoc09/Kai.git
cd Kai

./bootstrap.sh    # installs all deps, creates .env, runs migrations, verifies tools
nano .env         # set ANTHROPIC_API_KEY, JWT_SECRET_KEY, K1_DEV_TOKEN
./k1-start        # start backend (8080) + celery worker + operator UI (8081)
```

Stop services:

```bash
./k1-stop
```

Full-stack Docker orchestration (legacy) remains available via `./k1 start`.

### Manual Development Mode

```bash
# API Server (with reload)
python3 -m uvicorn apps.backend.src.main:app --host 0.0.0.0 --port 8080 --reload

# Celery Worker
celery -A apps.backend.src.worker.celery_app worker -Q tools,intrusive -l info

# Frontend
cd ui && npm run dev
```

### Running Tests

```bash
# Self-contained tests (no external services)
python -m pytest tests/test_scope_guardrails.py tests/test_tool_registry_catalog.py \
  tests/test_bugbounty_workflow_engine.py tests/test_tool_adapters_bugbounty.py -q

# Full suite (requires PostgreSQL, Redis, Vault)
pytest

# Quality checks
black --check --line-length 100 .
ruff check .
mypy .
isort --check-only --profile black .
```

### Dev Auth

```bash
curl -sS -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$K1_DEV_TOKEN\"}"
```

Use the returned `access_token` as `Authorization: Bearer <token>`.

---

## 2. Adding a New Agent Persona

Agent personas are defined in `orchestration/praison/agents.yaml` — the single source of truth consumed by `PraisonAgentRegistry`.

### 2.1 Define the Agent

Add a new entry under the `agents:` key:

```yaml
agents:
  MyNewSpecialist:
    persona: "Descriptive Role Name"
    description: >
      What this agent does, what expertise it brings,
      and when it is activated in the mission graph.
    system_prompt: >
      You are K1's [role] — [expertise background].
      [Behavioral constraints]. [Output expectations].
    allowed_tools:
      - tool_id_1
      - tool_id_2
    risk_profile: standard       # governance | analysis | orchestration | recon | reporting | standard
    llm_pin: anthropic           # optional: per-agent provider override
    memory_scope: session        # session | phase | workflow | mission | persistent
    review_policy: standard      # strict | moderate | standard
    agent_class: specialist      # governor | director | coordinator | specialist
    delegation_scope: none       # none | phase | global (specialists MUST be "none")
    allowed_peer_targets: []     # agent_ids this agent can hand off to
    handoff_policy: coordinator_visible
    interrupt_policy: none       # none | before_sensitive_tools | before_phase_exit
    escalation_policy: hil_for_band2
```

### 2.2 Policy Constraints (Enforced at Load Time)

These rules are validated by `PraisonAgentRegistry.validate_agent_policy()`:

| Rule | Enforcement |
|------|-------------|
| `persona`, `description`, `system_prompt` required | `ValueError` if missing |
| `specialist` agents must have `delegation_scope: none` | `ValueError` if violated |
| `governor` agents must have `delegation_scope != none` | `ValueError` if violated |
| `allowed_tools` must be a list | `ValueError` if wrong type |
| All policy fields must be from valid sets | `ValueError` with allowed values listed |

### 2.3 Verification

The registry auto-loads on startup. Verify:

```python
from apps.backend.src.core.praison_registry import get_agent_registry

registry = get_agent_registry()
identity = registry.get_agent("MyNewSpecialist")
assert identity.agent_class == "specialist"
assert identity.delegation_scope == "none"
```

### 2.4 Where Identity Flows

```
agents.yaml
  → PraisonAgentRegistry.load_agents()
    → AgentIdentity (frozen dataclass)
      → Framework adapters (crewai_adapter, langgraph_adapter, deepagents_adapter)
      → PraisonGovernor (governance validation)
      → MissionRuntime (graph compilation)
```

**Source files**:
- `orchestration/praison/agents.yaml` — definition
- `apps/backend/src/core/praison_agent.py` — `AgentIdentity` model
- `apps/backend/src/core/praison_registry.py` — `PraisonAgentRegistry`

---

## 3. Adding a New LangGraph Node

Nodes are the execution units in the mission DAG. Each node wraps an agent callable with event emission, governance checks, and error handling.

### 3.1 Define the NodeSpec

In `apps/backend/src/core/praison_topology.py`, add to your topology builder:

```python
NodeSpec(
    node_id="MyNewNode",
    agent_id="MyNewSpecialist",       # must exist in agents.yaml
    node_type="agent",                 # governance | coordinator | reporter | agent
    cluster_id="recon_cluster",        # cluster membership (if any)
    agent_class="specialist",
    risk_profile="standard",
    review_policy="standard",
    memory_scope="session",
    allowed_tools=["subfinder", "dnsx"],
    interrupt_before=False,            # True = pause before execution
    interrupt_after=False,             # True = pause after execution
    is_entry=False,
    is_exit=False,
)
```

### 3.2 Create the Node Executor

In `apps/backend/src/core/praison_node_executors.py`:

```python
def make_my_new_node_executor(
    agent_callable: Callable | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Node executor for MyNewNode."""
    return make_node_executor(
        node_id="MyNewNode",
        agent_callable=agent_callable,
        node_type="agent",
    )
```

The `make_node_executor` wrapper automatically provides:
- `node_entered` / `node_completed` / `node_failed` event emission
- Execution mode check (`graph_only` returns stub data)
- State update construction with `node_history` tracking
- Error accumulation in `errors` list

### 3.3 Add Edges

In your topology builder, define edges connecting the new node:

```python
EdgeSpec(
    source="PhaseCoordinator",
    target="MyNewNode",
    condition=EdgeCondition.ON_SUCCESS,
)
EdgeSpec(
    source="MyNewNode",
    target="EvidenceAnalyst",
    condition=EdgeCondition.ON_ARTIFACT,
)
```

### 3.4 Conditional Routing

For conditional edges, the LangGraph builder uses routing functions based on state fields:

| State Field | Routing Pattern |
|-------------|----------------|
| `governance_decision` | `approved` → continue, `blocked` → terminal |
| `last_artifact_type` | Route to different analysis nodes |
| `phase_complete` | Exit cluster, advance to next phase |

### 3.5 Register the Callable

In `MissionRuntime.create_mission()`, the topology's node specs are mapped to callables via `node_callables`:

```python
node_callables = {
    "MyNewNode": make_my_new_node_executor(my_agent_callable),
    # ... other nodes
}
```

**Source files**:
- `apps/backend/src/core/praison_topology.py` — `NodeSpec`, `EdgeSpec`, `MissionGraphSpec`
- `apps/backend/src/core/praison_node_executors.py` — executor factories
- `apps/backend/src/core/praison_langgraph_builder.py` — graph compilation

---

## 4. Adding a New Governed Tool

Tools execute in Celery workers, never in the API process. Every tool call passes through the governance pipeline.

### 4.1 Define in Tool Registry

Add to `tools/registry/tool_registry.yaml`:

```yaml
  - name: my_new_tool
    category: recon_asset_discovery    # determines phase availability
    execution_mode: native             # native | docker | python
    binary_path: my_new_tool
    install_verification_cmd: ["my_new_tool", "--version"]
    input_schema: {"target": "domain"}
    output_schema: {"results": "list[json]"}
    timeout_seconds: 300
    retry_policy: {max_attempts: 1, backoff_seconds: 0}
    safety_classification: passive     # passive | active | intrusive | manual_only
    tags: ["recon"]
    dependencies: []
    api_keys_required: []              # credentials fetched from Vault
    enabled_by_default: true
```

### 4.2 Safety Classification → Band Mapping

| Classification | Band | Behavior |
|---------------|------|----------|
| `passive` | Band 0 | Always allowed |
| `active` | Band 1 | Allowed within scope |
| `intrusive` | Band 2 | Requires operator approval |
| `manual_only` | Band 3 | **Unconditionally denied** |

### 4.3 Add Tool Adapter (if needed)

If the tool requires custom input/output parsing, add an adapter in `apps/backend/src/core/tool_adapters_bugbounty.py`:

```python
class MyNewToolAdapter(BaseTool):
    tool_name = "my_new_tool"

    def _run_once(self, target: str, params: dict) -> dict:
        cmd = [self.binary_path, "-d", target]
        result = subprocess.run(cmd, capture_output=True, timeout=self.timeout)
        # Parse stdout (enforce 25 MB cap)
        return {"results": self._parse_output(result.stdout)}
```

### 4.4 LangChain Wrapper

The tool is automatically wrapped as a `K1GovernedTool` by `K1LangChainToolRegistry`:

```python
registry = K1LangChainToolRegistry()
tools = registry.get_tools_for_phase("recon")  # includes your new tool
```

The governance pipeline runs on every call:
1. Execution-mode fast-path (simulation → fixture/stub)
2. Allowed-tool-ids allowlist check
3. Safety band enforcement (Band 3 always denied)
4. Scope validation
5. Telemetry emission
6. Dispatch signal (real execution via Celery)

### 4.5 Grant Tool to Agents

Add the tool name to an agent's `allowed_tools` in `agents.yaml`:

```yaml
  MyNewSpecialist:
    allowed_tools:
      - my_new_tool
```

**Source files**:
- `tools/registry/tool_registry.yaml` — tool definitions
- `apps/backend/src/core/tool_registry_catalog.py` — `ToolCatalogEntry`, `get_tool_catalog()`
- `apps/backend/src/core/tool_adapters_bugbounty.py` — custom adapters
- `apps/backend/src/core/langchain_tool_registry.py` — `K1GovernedTool`, `K1LangChainToolRegistry`

### 4.6 Manual-Only Backlog Entries (Custom Script Pending)

For tools that are intentionally cataloged before wrappers exist:

- set `safety_classification: manual_only`
- set `enabled_by_default: false`
- use `execution_mode: optional` with empty `binary_path` (`""`)
- set dependency markers like `wrapper_pending`, `custom_script_required`, and any required credentials

This keeps tooling discoverable for planning/training while preventing autonomous execution.

---

## 5. Adding a New Structured Schema

Structured output schemas control LLM response format with Pydantic v2 validation.

### 5.1 Define the Schema

In `apps/backend/src/core/langchain_schemas.py`:

```python
class MyAnalysisResult(BaseModel):
    """Structured output for my analysis step."""

    model_config = ConfigDict(extra="forbid")  # REQUIRED: rejects undeclared fields

    category: str = Field(description="Classification category")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    evidence: list[str] = Field(description="Supporting evidence items")
    recommendation: str = Field(description="Recommended next action")
```

### 5.2 Register in Schema Registry

Add to `SCHEMA_REGISTRY` at the bottom of the file:

```python
SCHEMA_REGISTRY["my_analysis"] = MyAnalysisResult
```

### 5.3 Use with Reasoning Engine

```python
from apps.backend.src.core.langchain_reasoning import K1ReasoningEngine

engine = K1ReasoningEngine(model_factory=factory)
result = await engine.structured_call(
    schema=MyAnalysisResult,
    prompt="Analyze the following evidence...",
    context={"findings": findings},
)
```

### 5.4 Security Rules

- **Always** use `ConfigDict(extra="forbid")` — prevents prompt injection via unexpected keys
- Use Pydantic field constraints (`ge`, `le`, `min_length`) instead of custom validators
- All fields must have `Field(description=...)` for LLM schema introspection

**Source file**: `apps/backend/src/core/langchain_schemas.py`

---

## 6. Adding a DeepAgents Specialist Role

Specialists handle deep analysis tasks with bounded iteration and optional subagent delegation.

### 6.1 Define Specialist Type

In `apps/backend/src/core/praison_deepagents_bridge.py`, add to the specialist type registry:

```python
SPECIALIST_TYPES = {
    # ... existing types
    "my_analyst": {
        "max_iterations": 15,
        "max_subagents": 1,
        "max_tokens": 40_000,
    },
}
```

### 6.2 Create Agent Identity

Add the specialist to `agents.yaml` (see Section 2). The specialist type maps to the `description` field's intent — the bridge uses the specialist type string from the calling context.

### 6.3 Invocation via Bridge

```python
from apps.backend.src.core.praison_deepagents_bridge import DeepAgentsBridge

bridge = DeepAgentsBridge()
result = bridge.execute_specialist(
    identity=registry.get_agent("MyNewSpecialist"),
    task="Analyze the following evidence bundle...",
    context={"findings": findings, "artifacts": artifacts},
    specialist_type="my_analyst",
)
# result: DeepAgentResult → converted to K1GraphState update
```

### 6.4 Dual-Path Execution

- **With `deepagents` installed**: Uses real compiled graph with iteration bounds
- **Without `deepagents`**: Uses Kai's native LLM invoke path
- Both produce the same `DeepAgentResult` type

### 6.5 Backend Policy

Specialists execute within sandbox restrictions:

| Backend | Storage | Cleanup | Use Case |
|---------|---------|---------|----------|
| `EPHEMERAL` | In-memory | Immediate | Default, always safe |
| `SCRATCH` | Temp filesystem | Auto on TTL | Intermediate artifacts |
| `DURABLE` | Persistent FS | No auto | Requires explicit enable |

**Source files**:
- `apps/backend/src/core/praison_deepagents_bridge.py` — `DeepAgentsBridge`
- `apps/backend/src/core/praison_deepagents_backends.py` — backend policy
- `apps/backend/src/core/praison_sandbox_manager.py` — sandbox isolation

---

## 7. Adding a New Simulation Fixture

Fixtures provide deterministic test data for `graph_only` and `tool_mock` execution modes.

### 7.1 Node Fixture

In `apps/backend/src/core/praison_simulation_fixtures.py`:

```python
def _fixture_my_new_node(
    profile: str,
    scenario_pack: str,
    seed: int | None,
) -> dict[str, Any]:
    """Fixture for MyNewNode output."""
    provenance = FixtureProvenance(
        fixture_id=_make_fixture_id(seed, "node", "MyNewNode"),
        fixture_type="node_output",
        profile=profile,
        scenario_pack=scenario_pack,
        node_id="MyNewNode",
        deterministic_seed=seed,
    )

    base = {
        "active_node": "MyNewNode",
        "node_history": [{"node_id": "MyNewNode", "status": "completed"}],
        "_fixture_provenance": provenance.to_dict(),
    }

    if scenario_pack == "high_signal":
        base["findings"] = [{"severity": "high", "confidence": 0.9}]
    else:
        base["findings"] = [{"severity": "info", "confidence": 0.5}]

    return base
```

### 7.2 Tool Fixture

```python
def _fixture_tool_my_new_tool(
    profile: str,
    scenario_pack: str,
    seed: int | None,
) -> dict[str, Any]:
    """Mock result for my_new_tool."""
    provenance = FixtureProvenance(
        fixture_id=_make_fixture_id(seed, "tool", "my_new_tool"),
        fixture_type="tool_result",
        profile=profile,
        tool_name="my_new_tool",
        deterministic_seed=seed,
    )
    return {
        "tool_name": "my_new_tool",
        "status": "success",
        "output": {"results": [{"finding": "test-data"}]},
        "_fixture_provenance": provenance.to_dict(),
    }
```

### 7.3 Register Fixtures

Add to the `FixtureRegistry` dispatch:

```python
_NODE_FIXTURE_MAP["MyNewNode"] = _fixture_my_new_node
_TOOL_FIXTURE_MAP["my_new_tool"] = _fixture_tool_my_new_tool
```

### 7.4 Scenario Packs

Scenario packs modify fixture behavior by name. Existing packs:

| Scenario | Effect |
|----------|--------|
| `default` | Standard low-signal results |
| `high_signal` | Critical/high severity findings |
| `noisy_false_positive` | Many results, mostly info/low |
| `approval_heavy` | Multiple approval gates triggered |
| `blocked_mission` | Governance admission block |

Your fixture should check `scenario_pack` and vary output accordingly.

### 7.5 Fixture Provenance

Every fixture **must** include `_fixture_provenance` metadata via `FixtureProvenance`. This is how simulation artifacts are distinguished from live data.

**Source file**: `apps/backend/src/core/praison_simulation_fixtures.py`

---

## 8. Adding a New Evaluation Dataset / Evaluator

LangSmith evaluations measure the quality of agent outputs.

### 8.1 Create a Dataset Builder

In `apps/backend/src/core/langsmith_evaluations.py`:

```python
def build_my_analysis_example(
    analysis_output: dict[str, Any],
    reference: dict[str, Any],
) -> dict[str, Any]:
    """Build a LangSmith dataset example from analysis output."""
    return {
        "inputs": {
            "evidence": analysis_output.get("evidence", []),
            "context": analysis_output.get("context", ""),
        },
        "outputs": {
            "category": analysis_output.get("category", ""),
            "confidence": analysis_output.get("confidence", 0.0),
        },
        "reference": reference,
    }
```

### 8.2 Create an Evaluator

```python
def my_analysis_accuracy_evaluator(
    run_output: dict[str, Any],
    reference: dict[str, Any],
) -> list[EvalResult]:
    """Evaluate analysis accuracy against reference data."""
    results = []

    # Category match
    cat_match = run_output.get("category") == reference.get("expected_category")
    results.append(EvalResult(
        key="category_accuracy",
        score=1.0 if cat_match else 0.0,
        comment=f"Category: {run_output.get('category')} vs expected: {reference.get('expected_category')}",
    ))

    # Confidence calibration
    conf = run_output.get("confidence", 0.0)
    expected_conf = reference.get("expected_confidence", 0.5)
    calibration = 1.0 - abs(conf - expected_conf)
    results.append(EvalResult(
        key="confidence_calibration",
        score=max(0.0, calibration),
    ))

    return results
```

### 8.3 Register the Dataset

Use `K1DatasetManager` to create and populate:

```python
manager = K1DatasetManager(bridge=langsmith_bridge)
manager.ensure_dataset("kai-my-analysis-accuracy")
manager.add_example(
    dataset_name="kai-my-analysis-accuracy",
    example=build_my_analysis_example(output, reference),
)
```

### 8.4 Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Dataset | `kai-{category}-{qualifier}` | `kai-my-analysis-accuracy` |
| Experiment | `kai-exp-{what}-{timestamp}` | `kai-exp-analysis-v2-20260318` |

**Source file**: `apps/backend/src/core/langsmith_evaluations.py`

---

## 9. Adding a New Telemetry Event

Events are emitted at every execution boundary and flow to EventBus subscribers (WebSocket, JSONL, LangSmith).

### 9.1 Add the Event Type

In `apps/backend/src/core/praison_execution_events.py`:

```python
class EventType(str, Enum):
    # ... existing types
    MY_NEW_EVENT = "my_new_event"
```

### 9.2 Create an Event Builder

```python
def my_new_event(
    mission_id: str,
    workflow_id: str,
    program_id: str,
    node_id: str,
    phase: str,
    detail: dict[str, Any],
) -> MissionEvent:
    """Build a my_new_event MissionEvent."""
    return MissionEvent(
        event_type=EventType.MY_NEW_EVENT,
        mission_id=mission_id,
        workflow_id=workflow_id,
        program_id=program_id,
        node_id=node_id,
        phase=phase,
        detail=detail,
    )
```

### 9.3 Emit from Node Executor

```python
emit(my_new_event(
    mission_id=state["mission_id"],
    workflow_id=state["workflow_id"],
    program_id=state["program_id"],
    node_id="MyNewNode",
    phase=state.get("phase", ""),
    detail={"key": "value"},
))
```

### 9.4 Event Structure

Every `MissionEvent` carries:

| Field | Source |
|-------|--------|
| `event_id` | Auto-generated UUID |
| `event_type` | Your `EventType` enum value |
| `timestamp` | ISO 8601 UTC |
| `mission_id` | From graph state |
| `workflow_id` | From graph state |
| `program_id` | From graph state |
| `node_id` | Current node |
| `phase` | Current phase |
| `detail` | Arbitrary dict (your event data) |

### 9.5 Subscriber Flow

Events are delivered to all registered subscribers:

```
emit(event)
  → EventBus.publish()
    → WebSocket subscriber (real-time UI)
    → JSONL subscriber (artifacts/telemetry/mission_events.jsonl)
    → LangSmith subscriber (trace spans)
```

### 9.6 Simulation Events

If your event is simulation-specific, add it to the `SIMULATION_EVENT_TYPES` frozenset in `praison_simulation.py` so it is correctly tagged in LangSmith traces.

**Source file**: `apps/backend/src/core/praison_execution_events.py`

---

## 10. Architecture Boundaries

When extending Kai, respect these layer boundaries:

### 10.1 Authority Map

| Concern | Authoritative Layer | Source |
|---------|-------------------|--------|
| Agent identities | PraisonAI registry | `praison_registry.py` |
| Governance policy | PraisonGovernor | `praison_governor.py` |
| Mission state | K1GraphState | `praison_state.py` |
| Graph execution | LangGraph / MissionRuntime | `praison_mission_runtime.py` |
| Model abstraction | LangChain / K1ChatModel | `langchain_model_factory.py` |
| Tool wrapping | LangChain / K1GovernedTool | `langchain_tool_registry.py` |
| Specialist deep work | DeepAgents / Bridge | `praison_deepagents_bridge.py` |
| Observability | LangSmith / Bridge | `langsmith_integration.py` |
| Simulation overlay | SimulationController | `praison_simulation.py` |

### 10.2 Rules for Extension

1. **Never bypass governance**. All tool calls go through `K1GovernedTool` or the Celery worker pipeline. Direct tool execution in the API process is forbidden.

2. **Never define agents outside `agents.yaml`**. All framework adapters derive from `PraisonAgentRegistry`. If an adapter creates agents independently, it is a bug.

3. **Never mutate `AgentIdentity`**. It is a frozen dataclass. Use `identity.with_runtime()` to produce annotated copies.

4. **Never mutate `DelegationContract`**. Contracts are frozen. State transitions create new records.

5. **LangSmith is read-only**. It receives events but never drives execution. EventBus and LangSmith subscribers must never depend on each other.

6. **Simulation never escalates to live**. `graph_only` = zero live calls. `tool_mock` = fixture data only. No execution mode can accidentally produce live effects.

7. **Secrets stay in Vault**. Credentials are fetched by the Celery worker at execution time. Never pass credentials through graph state, LLM context, or sandbox environments.

8. **Use accumulative reducers correctly**. Fields using `Annotated[list, operator.add]` (like `findings`, `artifacts`, `errors`) are append-only. Return new items only — the reducer handles concatenation.

### 10.3 Common Mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Adding tools directly to an agent without `agents.yaml` | Tool calls bypass governance | Add to `allowed_tools` in agents.yaml |
| Returning full list in an accumulative field | Duplicated entries in state | Return only new items |
| Calling LLM directly instead of through `K1ChatModel` | Bypasses provider routing and cost tracking | Use `K1ModelFactory` or `K1ReasoningEngine` |
| Writing simulation fixtures without provenance | Cannot distinguish simulation from live data | Always include `FixtureProvenance` |
| Emitting events without correlation IDs | Broken trace hierarchy in LangSmith | Always include `mission_id`, `workflow_id`, `program_id` |

---

## 11. Development Rules

- **Database first**: Canonical execution state lives in PostgreSQL, not memory-only structures.
- **Audit everything**: Emit events for significant state transitions via EventBus.
- **Immutability**: Prefer frozen dataclasses for internal state transfer.
- **No module-level side effects**: No `mkdir` or file creation at import time.
- **Modern type hints**: `dict[str, Any]` not `Dict[str, Any]`, `list[str]` not `List[str]`.
- **`from __future__ import annotations`** at the top of every new file.

### Code Style

```bash
# Formatting
black --line-length 100 .
isort --profile black .

# Linting
ruff check .
mypy .
```

### Test Conventions

- `pytest` pythonpath is `apps/backend/src` — imports resolve from there
- Self-contained tests should not require external services
- Use `tool_mock` execution mode for tests that exercise the graph
- Test file naming: `tests/test_{module_name}.py`

---

## 12. Key Source Files

| File | Purpose |
|------|---------|
| `orchestration/praison/agents.yaml` | Agent persona definitions |
| `tools/registry/tool_registry.yaml` | Tool catalog |
| `apps/backend/src/core/praison_agent.py` | `AgentIdentity` frozen dataclass |
| `apps/backend/src/core/praison_registry.py` | `PraisonAgentRegistry` |
| `apps/backend/src/core/praison_governor.py` | `PraisonGovernor` governance engine |
| `apps/backend/src/core/praison_topology.py` | `NodeSpec`, `EdgeSpec`, `MissionGraphSpec` |
| `apps/backend/src/core/praison_node_executors.py` | Node executor factories |
| `apps/backend/src/core/praison_langgraph_builder.py` | `PraisonLangGraphBuilder` |
| `apps/backend/src/core/praison_state.py` | `K1GraphState`, `merge_state()` |
| `apps/backend/src/core/praison_mission_runtime.py` | `MissionRuntime` lifecycle manager |
| `apps/backend/src/core/langchain_model_factory.py` | `K1ChatModel`, `K1ModelFactory` |
| `apps/backend/src/core/langchain_tool_registry.py` | `K1GovernedTool`, `K1LangChainToolRegistry` |
| `apps/backend/src/core/langchain_schemas.py` | Structured output Pydantic models |
| `apps/backend/src/core/langchain_reasoning.py` | `K1ReasoningEngine` |
| `apps/backend/src/core/praison_deepagents_bridge.py` | `DeepAgentsBridge` |
| `apps/backend/src/core/praison_simulation.py` | `SimulationController` |
| `apps/backend/src/core/praison_simulation_fixtures.py` | `FixtureRegistry` |
| `apps/backend/src/core/praison_execution_events.py` | `MissionEvent`, `EventBus` |
| `apps/backend/src/core/langsmith_integration.py` | `LangSmithBridge` |
| `apps/backend/src/core/langsmith_evaluations.py` | Evaluators, datasets |
