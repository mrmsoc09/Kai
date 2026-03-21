# Kai Platform Simulation

> **Safe execution overlays for dry-runs, agent validation, and historical analysis.**

Kai includes a comprehensive simulation system that allows operators and developers to execute missions without triggering real security tools or models. This is achieved through an "execution mode" overlay that intercepts actions at the `MissionRuntime` and `K1GovernedTool` layers.

---

## 1. Simulation Modes

Kai supports four distinct execution modes, each with specific safety invariants.

| Mode | Live Tools | Live Models | Fixtures | Replay | Use Case |
|------|-----------|-------------|----------|--------|----------|
| **`live`** | Yes | Yes | No | No | Production missions. |
| **`graph_only`** | **No** | **No** | Yes | No | Validate graph topology and agent logic without any cost or external risk. |
| **`tool_mock`** | **No** | Optional | Yes | No | Validate agent reasoning using real models but mock tool outputs. |
| **`replay`** | **No** | **No** | Fallback | Yes | Analyze past missions using stored events and state. |

---

## 2. Safety Barriers

Kai enforces **hard safety invariants** to prevent accidental live execution during simulation.

### Invariants
1.  **Tool Blocking**: All simulation modes (`graph_only`, `tool_mock`, `replay`) block live tool execution via `is_live_tool_blocked()`.
2.  **Model Blocking**: `graph_only` and `replay` modes block live LLM calls.
3.  **Sandbox Blocking**: Sandboxed execution is blocked in all simulation modes unless explicitly enabled for development.
4.  **Provenance Tagging**: Every artifact produced in simulation mode is tagged with `_simulation=True`.

### Verification Logic
The `assert_simulation_safe()` function is called at the start of every mission execution to verify that the environment variables and configuration are consistent with the requested simulation mode.

---

## 3. How it Works

Simulation is implemented as a cross-cutting concern through Kai's multi-layered architecture:

*   **Layer 1 (Governance):** `PraisonGovernor` skips HIL approval requests and returns deterministic outcomes.
*   **Layer 2 (Runtime):** `MissionRuntime` passes `execution_mode` to `K1GraphState`.
*   **Layer 3 (Tool Registry):** `K1GovernedTool` returns structural mock results immediately, bypassing Celery.
*   **Layer 6 (Simulation):** `SimulationController` routes execution and ensures safety.

---

## 4. Fixture System

Simulation modes rely on the **Fixture Registry** (`praison_simulation_fixtures.py`) for deterministic data.

*   **Mock Tool Results**: JSON templates for common tools (nmap, subfinder, httpx).
*   **Agent Reasoning Mocks**: Pre-baked reasoning outputs for `graph_only` mode.
*   **Scenario Packs**: Collections of fixtures representing specific security scenarios.

### Customizing Fixtures
Fixtures are stored as JSON files under `configs/fixtures/`. Developers can register new fixtures in `FixtureRegistry`.

---

## 5. Replay Engine

The Replay Engine (`praison_replay.py`) reconstructs mission timelines from historical data:

1.  **JSONL Events** from `EventBus`.
2.  **LangGraph Checkpoints** from PostgreSQL.
3.  **Artifact Lineage** from storage.
4.  **LangSmith Traces** (if available).

Replay is primarily used for post-mortem analysis and regression testing.

---

## 6. Configuring Simulation

Set the `K1_DEFAULT_EXECUTION_MODE` environment variable:

```bash
# To run everything in graph_only mode
export K1_DEFAULT_EXECUTION_MODE=graph_only
```

Or pass it at runtime via the API/CLI:

```bash
./scripts/run_workflow_local.py --mode tool_mock
```

---

## 7. Monitoring & Observability

Simulation runs are tagged in **LangSmith**:
*   `mode:graph_only` / `mode:tool_mock` / `mode:replay`
*   `simulation:true`

This allows filtering simulation data from production evaluation datasets.
