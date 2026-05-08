# KAISON AI - Code Audit Fix Prompts
## Platform-Specific Implementation Guidance with Agent Bidding System

**Generated:** 2026-05-08  
**Audit Base:** Security & Orchestration Review  
**Target:** VS Code Integration with Codex, Claude-Code, and Gemini-CLI

---

## ISSUE #1: CRITICAL - Bootstrap Authentication Backdoor

### Platform: **GitHub Copilot (Codex)**
**Rationale:** Copilot excels at recognizing security patterns and generating defensive code checks within existing frameworks.

**Persona:** Security-First DevSecOps Engineer
**Context Window:** Threat model + pattern recognition

```
PROMPT_ID: SECURITY_001_CODEX

You are a security-hardened DevSecOps engineer reviewing auth mechanisms in a Python 
FastAPI application that handles bug bounty orchestration and tool execution.

THREAT MODEL:
- Attack: Bootstrap auth token left in production environment
- Impact: Full admin access without JWT validation
- Root Cause: K1_ENABLE_BOOTSTRAP_AUTH and K1_DEV_TOKEN env vars in production

CURRENT VULNERABLE CODE PATTERN:
```
def _bootstrap_auth_enabled() -> bool:
    return os.getenv("K1_ENABLE_BOOTSTRAP_AUTH", "false").strip().lower() in {"1", "true", "yes", "on"}

def _bootstrap_user_from_token(token: str) -> Optional[User]:
    expected = _expected_token()
    if not expected or token != expected:
        return None
    if not _bootstrap_auth_enabled() or not _is_non_production():
        return None
    return User(id="dev", roles=[ROLE_ADMIN, ...], ...)
```

REQUIREMENTS:
1. Generate a compile-time feature flag system that COMPLETELY removes bootstrap auth code 
   from production builds (not runtime checks)
2. Create a pre-deployment validation that FAILS the build if K1_ENABLE_BOOTSTRAP_AUTH 
   or K1_DEV_TOKEN are present in ANY environment
3. Implement a secure dev-only authentication that uses temporary signed certificates 
   (not hardcoded tokens)
4. Add a GitHub Actions workflow that scans ALL Docker images for these env vars before push

DELIVERABLES:
- auth.py refactored with conditional compilation directives
- build-time validation script (Python or shell)
- dev certificate generation utility
- GitHub Actions workflow for env var scanning
- Migration guide for developers currently using bootstrap auth

OUTPUT FORMAT:
Generate working code blocks with inline security comments explaining each defensive layer.
```

---

## ISSUE #2: HIGH - Incomplete Subprocess Argument Validation

### Platform: **Claude (Claude-Code)**
**Rationale:** Claude excels at comprehensive validation logic, edge case analysis, and creating production-ready validators with clear documentation.

**Persona:** Principal Security Architect specializing in input validation
**Context Window:** Full OWASP validation guidelines + tool-specific constraints

```
PROMPT_ID: VALIDATION_002_CLAUDE

You are a Principal Security Architect designing a comprehensive input validation 
system for subprocess command execution in a security research platform.

CONTEXT:
The KAISON AI platform executes 51+ security tools via subprocess.Popen(). 
Previous audits found incomplete validation in nuclei_adapter.py where comments 
promise validation but functions are missing.

TOOLS AFFECTED & CONSTRAINTS:
- nuclei: tags (alphanumeric+comma+dash), rate_limit (1-1000), timeout (1-300s), 
          templates (path validation + no traversal)
- nmap: ports (1-65535), rate-limiting, scan-type (specific enum)
- sqlmap: url (HTTP/HTTPS only), technique (specific enum), risk (1-3), level (1-5)
- masscan: rate (1-10000 pps), ports (1-65535), excludes (CIDR notation only)

REQUIREMENTS:
1. Design and implement a validator framework that:
   - Uses type hints for clarity (not stringly-typed)
   - Provides clear error messages (for logging, not user exposure)
   - Has configurable per-tool constraint sets
   - Supports both string and numeric inputs with auto-casting
   - Validates BEFORE command construction (fail-safe)

2. For each tool above, implement validators covering:
   - Type validation (str, int, bool, list)
   - Range validation (numeric bounds)
   - Pattern validation (regex for strings)
   - Path validation (no ../, ~/.ssh, /etc, etc.)
   - Enum validation (known-safe options only)
   - CIDR/IP validation where applicable

3. Create unit tests (pytest) for:
   - Happy path (valid inputs)
   - Boundary conditions (min/max values)
   - Malicious inputs (injection attempts, directory traversal, etc.)
   - Type coercion (string "100" to int 100)

4. Design a registry pattern so new tools can self-register validators without 
   modifying the validation framework

DELIVERABLES:
- validators.py with ToolValidator base class and registry
- tool_constraints.yaml defining per-tool rules
- Per-tool validator implementations (NucleiValidator, NmapValidator, etc.)
- test_validators.py with comprehensive test suite
- Integration guide showing how to wrap executor() calls with validators

EDGE CASES TO HANDLE:
- Unicode/UTF-8 in domain names (IDN)
- Extremely large port ranges that could exhaust memory
- Rate limits that could crash the target or local system
- Timeout values that interact with tool defaults
- Path traversal via symlinks, not just ".." sequences

OUTPUT FORMAT:
Provide validated, production-ready Python code. Include security comments 
explaining the threat each validator mitigates.
```

---

## ISSUE #3: HIGH - Missing Token Revocation on Logout

### Platform: **Google Gemini (Gemini-CLI)**
**Rationale:** Gemini is superior at multi-system integration, understanding session lifecycle, and designing concurrent data structures.

**Persona:** Distributed Systems Engineer with session management expertise
**Context Window:** Session lifecycle + Redis/database integration patterns

```
PROMPT_ID: SESSION_003_GEMINI

You are a Distributed Systems Engineer designing a session revocation system 
for a multi-tenant security platform with concurrent user sessions.

SCENARIO:
KAISON AI users authenticate via JWT. Currently there is NO logout endpoint; 
stolen tokens remain valid until expiration (default 60 minutes). You must 
design and implement an immediate token revocation system.

CONSTRAINTS:
- Multi-tenant architecture (users from different organizations)
- High throughput (100+ concurrent API requests)
- Distributed deployment (3+ API instances)
- Redis and PostgreSQL available as backing stores
- JWT includes 'jti' (JWT ID) and 'exp' (expiration timestamp) claims
- Logout must work within 100ms
- Session data should not persist indefinitely (cleanup needed)

REQUIREMENTS:
1. Design a token blocklist that:
   - Blocks specific JTI values (not entire user sessions)
   - Automatically expires entries when JWT exp timestamp passes
   - Supports checking revocation status in <10ms
   - Survives API instance restarts (persistent storage)
   - Doesn't grow unbounded (old entries must be cleaned)

2. Implement using Redis as primary store:
   - Key format: revoked_token:{jti}
   - TTL: set to (exp - now) so Redis auto-deletes expired entries
   - Backup: Periodic writes to PostgreSQL for persistence across Redis restarts

3. Implement logout() endpoint that:
   - Extracts JTI from the current user's token
   - Adds to Redis blocklist with appropriate TTL
   - Returns immediately (async background writes to PostgreSQL)
   - Handles edge cases (already-logged-out, malformed token, etc.)

4. Modify token validation to:
   - Check Redis blocklist BEFORE JWT signature verification
   - Fall back to DB check if Redis is unavailable
   - Cache blocklist lookups briefly (10-30 seconds) to avoid thundering herd

5. Add lifecycle management:
   - Batch cleanup job that removes expired entries from PostgreSQL
   - Monitor for blocklist growth; alert if > 100K entries
   - Provide admin endpoint to view/revoke all tokens for a user

ARCHITECTURE QUESTIONS TO ANSWER:
- How do you prevent the blocklist from being a bottleneck?
- What happens if Redis is down? (fallback to DB?)
- How do you handle clock skew between API instances?
- Should users be able to have multiple concurrent sessions?

DELIVERABLES:
- TokenBlocklist class (Redis + fallback logic)
- logout() endpoint in routers/auth.py
- PostgreSQL schema for token_revocations table
- Async cleanup job using APScheduler
- Integration test showing revocation works across API instances
- Architecture diagram showing blocklist flow

OUTPUT FORMAT:
Provide code, schema DDL, and architectural decisions with rationale. 
Include Redis/DB interaction patterns and failure scenarios.
```

---

## ISSUE #4: MEDIUM - CSRF Protection Bypass for Bearer Tokens

### Platform: **GitHub Copilot (Codex)**
**Rationale:** Copilot is best for security middleware patterns and quick integration into existing frameworks.

**Persona:** API Security Engineer
**Context Window:** OWASP CSRF + Origin validation patterns

```
PROMPT_ID: CSRF_004_CODEX

You are an API Security Engineer hardening CSRF protections in a FastAPI application.

CURRENT STATE:
```
class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in CSRF_EXEMPT_METHODS:
            return await call_next(request)
        if any(request.url.path.startswith(path) for path in CSRF_EXEMPT_ENDPOINTS):
            return await call_next(request)
        
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return await call_next(request)  # Bearer token exemption
        
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token:
            return JSONResponse(status_code=403, ...)
        
        session_id = request.cookies.get("session_id")
        if not csrf_manager.validate_token(session_id, csrf_token):
            return JSONResponse(status_code=403, ...)
        
        return await call_next(request)
```

SECURITY ISSUES:
- Bearer exemption is correct for API clients
- BUT: httpOnly cookies (k1_token) are still CSRF-vulnerable if accessed by JavaScript
- If CORS misconfigured, XSS→cookie theft→CSRF chain is possible
- No Origin/Referer validation for cookie-based requests
- No SameSite cookie directive visible

REQUIREMENTS:
1. Add Origin and Referer header validation for cookie-based requests
2. Implement SameSite=Strict on session cookies (via response middleware)
3. Add per-endpoint CSRF nonce validation for high-risk operations (approval, tool execution)
4. Create an endpoint configuration system that tags endpoints by risk level
5. Implement challenge-response CSRF for state-changing operations from browser origins
6. Add CSP headers to prevent XSS→cookie theft

DELIVERABLES:
- Enhanced CSRFProtectionMiddleware with Origin validation
- Response middleware that sets secure cookie attributes
- Per-endpoint CSRF configuration system
- Challenge-response implementation for browser requests
- Configuration for CSP headers
- Testing utilities to validate CSRF protection

OUTPUT FORMAT:
Generate ready-to-integrate middleware code with clear decision points for 
cookie-based vs. Bearer token requests. Include test cases.
```

---

## ISSUE #5: MEDIUM - Secret Caching Without Expiration

### Platform: **Claude (Claude-Code)**
**Rationale:** Claude excels at designing secure caching strategies with TTL management and cryptographic considerations.

**Persona:** Security Infrastructure Engineer
**Context Window:** Secret lifecycle management + cryptography standards

```
PROMPT_ID: SECRETS_005_CLAUDE

You are a Security Infrastructure Engineer designing a secrets caching layer 
for a platform that orchestrates security tools requiring various API keys.

CURRENT VULNERABILITY:
Secrets from Vault are cached in memory indefinitely without TTL. 
If Vault is updated, stale secrets are served. Memory dumps expose plaintext secrets.

CONTEXT:
- Vault is the source of truth for secrets (not environment variables)
- Multiple tools (nuclei, nmap, shodan, etc.) require different API keys
- Tool execution happens frequently; each lookup adds 50-100ms latency
- Platform serves 100+ concurrent users across multi-tenant deployments
- Memory is limited; secrets cache could be attacked to exhaust memory

REQUIREMENTS:
1. Design a SecretsCacheManager that:
   - Caches secrets with a configurable TTL (default 300 seconds)
   - Supports different TTLs for different secret types (API keys vs. passwords)
   - Encrypts secrets at rest in the cache (not plaintext in memory)
   - Tracks cache hits/misses for observability
   - Supports per-tenant secret isolation

2. Implement secret-specific encryption:
   - Use NaCl (nacl.secret.SecretBox) for symmetric encryption
   - Encryption key is derived from environment (never stored in code)
   - Decryption only happens immediately before tool execution
   - Encrypt immediately after retrieval from Vault

3. Memory safety:
   - Limit cache size with LRU eviction policy (max 1000 secrets)
   - Overwrite memory after eviction using os.urandom() (not just del)
   - Add monitoring for cache memory growth
   - Implement secrets eviction on platform shutdown

4. Vault integration improvements:
   - Implement exponential backoff for Vault connection failures
   - Support Vault's dynamic secrets (auto-rotate)
   - Handle Vault token refresh gracefully
   - Log all secret access (for audit trail, not to stdout)

5. Testing:
   - Unit tests for cache TTL expiration
   - Tests for secret encryption/decryption
   - Tests for concurrent access (thread-safe)
   - Memory safety tests (verify overwriting)
   - Integration tests with mock Vault

DELIVERABLES:
- SecretsCacheManager class with TTL support
- EncryptedSecretValue wrapper for in-memory encryption
- SecretType enum and per-type configuration
- Integration with existing secret_manager.py
- Monitoring/observability hooks (cache hit rate, eviction events)
- Configuration schema for TTLs and cache limits
- Test suite with memory safety validation

ARCHITECTURAL DECISIONS:
- Why encrypt at rest? (Answer: Defense-in-depth; memory dump protection)
- Why not use built-in functools.lru_cache? (Answer: Need TTL, not just size limit)
- How do you handle secret rotation? (Answer: Pre-expiration invalidation)

OUTPUT FORMAT:
Provide production-grade code with clear security rationale. Include 
cryptography justification and memory safety considerations.
```

---

## ISSUE #6: MEDIUM - Rate Limit Bypass via X-Forwarded-For

### Platform: **Google Gemini (Gemini-CLI)**
**Rationale:** Gemini excels at analyzing network-layer attacks and designing distributed rate limiting.

**Persona:** Cloud Security Architect
**Context Window:** Proxy architecture + distributed rate limiting patterns

```
PROMPT_ID: RATELIMIT_006_GEMINI

You are a Cloud Security Architect securing API rate limiting against distributed 
attacks in a cloud-deployed security platform.

THREAT MODEL:
- Attacker spoofs X-Forwarded-For to bypass rate limits
- Attacker uses compromised proxy IPs in K1_TRUSTED_PROXY_CIDRS
- Attacker distributes load across many spoofed IPs
- Attack goal: Execute unlimited tool scans, DoS the platform

CURRENT VULNERABILITY:
```
def _get_client_ip(self, request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if _is_trusted_proxy(direct_ip):
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            candidate = xff.split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                return candidate  # ← Can be spoofed if proxy IP is compromised
            except ValueError:
                pass
    return direct_ip
```

REQUIREMENTS:
1. Implement multi-layer rate limiting:
   - Layer 1: Per-IP rate limit (existing, but improve)
   - Layer 2: Per-user rate limit (even if same IP)
   - Layer 3: Per-tool rate limit (prevent single tool exhaustion)
   - Layer 4: Per-organization rate limit (multi-tenant fairness)
   - Layer 5: Global platform rate limit (overall protection)

2. Proxy validation hardening:
   - Whitelist ONLY known cloud provider IPs (AWS, GCP, Azure ALB IPs)
   - Validate proxy IP comes from expected source (not arbitrary CIDR)
   - Implement proxy IP pinning if possible (specific ALB instance IPs)
   - Log all X-Forwarded-For rewriting events with source tracking

3. User-based rate limiting:
   - When user is authenticated, rate limit by user_id (not IP)
   - Prevents single user from bypassing via multiple IPs
   - Store user rate limit state in Redis for fast lookup
   - Include user's subscription tier in rate limit calculation

4. Distributed rate limiting:
   - Use token bucket algorithm stored in Redis
   - Support rate limit sharing across API instances
   - Handle Redis failure (fallback to stricter local limits)
   - Implement cache-coherency for distributed state

5. Observability and response:
   - Log rate limit violations with source IP, user, tool, time
   - Alert on suspicious patterns (many 429 responses from single IP)
   - Progressive backoff (first 429 at normal limit, then 50%, then 10%)
   - Provide rate limit headers in responses (X-RateLimit-*)

ADVANCED SCENARIOS:
- How do you handle legitimate traffic spikes? (Answer: Burst allowance + user override)
- What if user is behind shared proxy? (Answer: Graduated limits based on history)
- How do you detect organized attacks? (Answer: Behavioral analytics + IP reputation)

DELIVERABLES:
- Multi-layer RateLimiter class with Redis backend
- Per-user, per-tool, per-org limiters integrated into middleware
- Proxy IP validation with cloud provider support
- Token bucket implementation
- Logging and alerting infrastructure
- Redis schema for distributed state
- Configuration for different tier limits

OUTPUT FORMAT:
Provide architecture diagram, code implementation, and threat model analysis. 
Include distributed systems trade-offs and failure scenarios.
```

---

## ISSUE #7: CRITICAL - Orchestration Agent Tool Selection Logic is Hardcoded

### Platform: **Claude (Claude-Code)**
**Rationale:** Claude is best at designing complex decision systems, agent architectures, and bidding/auction algorithms.

**Persona:** AI/ML Systems Architect - Agent Design Specialist
**Context Window:** Multi-agent systems + LLM-driven reasoning

```
PROMPT_ID: ORCHESTRATION_007_CLAUDE

You are an AI/ML Systems Architect designing an intelligent orchestration system 
where multiple security tools "bid" to solve the current mission phase.

CURRENT STATE (HARDCODED):
The KAISON AI platform claims "autonomous tool selection" but actually uses 
static hardcoded sequences per agent:

```
preferred_sequences = {
    "ReconSpecialist": ["gau", "waybackurls", "katana", "nmap", "nuclei", ...],
}
preferred = preferred_sequences.get(identity.agent_id, list(identity.allowed_tools))
```

This is NOT autonomous; it's hardcoded choreography.

NEW SYSTEM: AGENT BIDDING FOR TOOL EXECUTION

VISION:
Implement a competitive bidding system where each tool agent autonomously evaluates 
the current mission state and "bids" with:
- Confidence score (0.0-1.0): How confident this tool solves the current phase goal
- Cost estimate: API calls, execution time, resource usage
- Output type: What data this tool produces (for downstream tools)
- Dependencies: What prior findings this tool requires
- Priority boost: How urgent this tool's execution is

The orchestrator collects bids, ranks by value (confidence * (1 - cost) * priority), 
and executes top N tools in parallel. Tools get feedback and learn over time.

ARCHITECTURE:

1. TOOLAGENT_BIDDING_INTERFACE:
   ```python
   class ToolBid:
       tool_id: str
       confidence: float  # 0.0-1.0
       estimated_cost: float  # cents or API credits
       execution_time_estimate_ms: int
       output_schema: Dict[str, str]  # What data this produces
       dependencies: List[str]  # Required prior findings
       priority_boost: float  # 1.0 = normal, 2.0 = high priority
       reasoning: str  # Explanation for the bid
       
       @property
       def bid_score(self) -> float:
           """Value score: higher is better"""
           return self.confidence * (100 / (1 + self.estimated_cost)) * self.priority_boost
   
   class IToolAgent(ABC):
       async def evaluate_mission(
           self, 
           mission_context: MissionContext,
           prior_findings: FindingDataset
       ) -> ToolBid:
           """Evaluate if this tool should execute next"""
           pass
   ```

2. MISSION_CONTEXT:
   ```python
   class MissionContext:
       target: str
       phase: int  # 1=Recon, 2=Enumeration, ..., 9=Reporting
       goals: List[str]  # What we're trying to achieve
       findings_so_far: FindingDataset
       budget_remaining_cents: float
       time_budget_remaining_ms: int
       execution_history: List[ToolExecution]  # What's been tried
   ```

3. LLM-DRIVEN TOOL SELECTION:
   Each tool uses Claude/Gemini to answer: "Should I run now?"
   
   Example logic for a tool:
   ```python
   class SubdomainEnumerationAgent(IToolAgent):
       async def evaluate_mission(self, context, findings):
           # Query LLM for reasoning
           prompt = f"""
           Current Mission State:
           - Target: {context.target}
           - Phase: {context.phase}
           - Goals: {context.goals}
           - Prior findings: {findings.summary()}
           
           Should SubdomainEnumeration tool run next? Why?
           
           Return JSON:
           {{
               "should_run": true/false,
               "confidence": 0.0-1.0,
               "reasoning": "explanation"
           }}
           """
           
           response = await llm.query(prompt)
           parsed = json.loads(response)
           
           if not parsed["should_run"]:
               return ToolBid(confidence=0.0, ...)  # Don't bid
           
           return ToolBid(
               tool_id="subfinder",
               confidence=parsed["confidence"],
               estimated_cost=15,  # 15 cents in API calls
               execution_time_estimate_ms=45000,
               output_schema={"subdomains": "list[str]", ...},
               dependencies=["domain_validated"],
               priority_boost=1.5 if "subdomain" in context.goals else 1.0,
               reasoning=parsed["reasoning"]
           )
   ```

4. ORCHESTRATOR_BIDDING_ENGINE:
   ```python
   class BiddingOrchestrator:
       async def select_tools_for_phase(
           self,
           mission_context: MissionContext,
           available_tools: List[IToolAgent]
       ) -> List[IToolAgent]:
           """Collect bids and select best tools"""
           
           # Request bids from all available tools
           bids = await asyncio.gather(*[
               tool.evaluate_mission(mission_context, mission_context.findings_so_far)
               for tool in available_tools
           ])
           
           # Filter out abstentions (confidence=0)
           viable_bids = [b for b in bids if b.confidence > 0.1]
           
           # Rank by bid score
           ranked = sorted(viable_bids, key=lambda b: b.bid_score, reverse=True)
           
           # Select top N that fit within budget and parallelization constraints
           selected_bids = self._select_best_combination(ranked, mission_context)
           
           # Emit reasoning to mission log
           for bid in selected_bids:
               emit_telemetry("tool_selected", {
                   "tool": bid.tool_id,
                   "confidence": bid.confidence,
                   "bid_score": bid.bid_score,
                   "reasoning": bid.reasoning
               })
           
           return [b.tool_agent for b in selected_bids]
   ```

5. LEARNING & FEEDBACK LOOP:
   After tool execution, update tool's "confidence calibration":
   
   ```python
   async def record_tool_execution(
       self,
       tool_id: str,
       bid: ToolBid,
       actual_result: ToolResult
   ):
       """Store execution for future bidding feedback"""
       execution = {
           "tool_id": tool_id,
           "bid_confidence": bid.confidence,
           "estimated_cost": bid.estimated_cost,
           "actual_cost": actual_result.cost,
           "findings_produced": len(actual_result.findings),
           "useful_findings": len(actual_result.findings_accepted),  # From analyst review
           "execution_time": actual_result.execution_time_ms,
       }
       
       # Store for training/analysis
       await db.execute(
           "INSERT INTO tool_execution_history (...) VALUES (...)",
           execution
       )
       
       # Use for future bid calibration
       tool_agent = self.get_tool(tool_id)
       await tool_agent.learn_from_execution(execution)
   ```

6. TOOL-SPECIFIC BIDDING LOGIC:
   
   Each tool implements context-aware bidding:
   
   a) **Nuclei (Vulnerability Scanning):**
      - High confidence if: Port scan results exist, web services detected
      - Low confidence if: No prior recon data, budget exhausted
      - Priority boost if: High-severity goal or time pressure
   
   b) **Nmap (Port Scanning):**
      - High confidence if: Early phase, no open ports known
      - Medium confidence if: Need service version detection (service-scan)
      - Low confidence if: Already have comprehensive port data
   
   c) **Subfinder (Subdomain Enumeration):**
      - High confidence if: Domain target, no subdomains enumerated
      - Medium confidence if: Need expanded scope (recursive enumeration)
      - Low confidence if: Already have subdomain list and deep-diving would be wasteful
   
   d) **SQLMap (SQL Injection Testing):**
      - High confidence if: Parameterized URLs found, target supports SQL injection
      - Dependencies: ["parameterized_urls_found"]
      - Cost: Higher than most tools
      - Priority: Only if SQLi is a mission goal

REQUIREMENTS:

1. Implement IToolAgent interface for all 51+ security tools
2. Build LLM evaluation prompts for each tool (using Claude or Gemini)
3. Create MissionContext and ToolBid data models
4. Implement BiddingOrchestrator with ranking algorithm
5. Store execution history and enable tool learning
6. Build observability: Emit all bidding decisions to mission log
7. Implement fallback: If all tools abstain, use default sequence
8. Add A/B testing framework to compare intelligent vs. hardcoded selection
9. Create bid visualization dashboard for debugging

DELIVERABLES:
- tool_agent_interface.py with IToolAgent base class
- bidding_orchestrator.py with ranking and selection logic
- tool_execution_history.py with learning schema
- Per-tool bidding implementations (50+ files or consolidated)
- LLM evaluation prompt templates
- Observability/telemetry integration
- A/B testing framework
- Dashboard UI for bid visualization
- Documentation on adding new tools

LEARNING FEATURES (Future Phases):
- Tool success rates from historical data
- Budget optimization (favor tools with high findings/cost ratio)
- Temporal patterns (which tools work best in which phases)
- User-specific overrides (analyst can boost confidence for preferred tools)
- Multi-phase orchestration (this phase's output → next phase tool selection)

OUTPUT FORMAT:
Provide end-to-end system design with code skeletons, data models, and 
example bidding scenarios. Include telemetry/observability hooks throughout.
```

---

## ISSUE #8: HIGH - Tool Autonomy Tiers Not Enforced in Execution

### Platform: **GitHub Copilot (Codex)**
**Rationale:** Copilot excels at decorator patterns, middleware, and integrating approvals into existing code flows.

**Persona:** Platform Engineering Lead
**Context Window:** Approval gate + execution flow patterns

```
PROMPT_ID: AUTONOMY_008_CODEX

You are a Platform Engineering Lead tasked with implementing governance enforcement 
for tool execution autonomy tiers in a multi-tenant security platform.

AUTONOMY_TIER_MODEL:
```
TIER_0_AUTO: Execute immediately, no approval needed
TIER_1_NOTIFY: Execute immediately, notify operator, log for audit
TIER_2_APPROVE: Wait for operator approval before executing (blocking)
TIER_3_HARD_STOP: Block execution, require manual override + special approval
```

CURRENT STATE:
Tiers are defined in config/authorized_scope.json but NOT ENFORCED:
- sqlmap, metasploit are TIER_3_HARD_STOP but can execute
- No pre-execution checks exist
- No approval gate integration

PROBLEM:
An unauthorized operator could execute intrusive tools without proper gatekeeping.

REQUIREMENTS:

1. Create an approval gate decorator system:
   ```python
   @require_autonomy_approval(ToolAutonomyTier.TIER_2_APPROVE)
   async def execute(self, target: str, ...):
       # Tool execution code
       pass
   ```

2. Implement approval request system:
   - Create human-readable approval request (tool name, target, estimated impact)
   - Route to operator for review
   - Support approve/reject/defer with reasoning
   - Timeout mechanism (auto-deny after 1 hour)

3. Execution pre-flight checks:
   - Verify user has permissions to execute this tool
   - Verify target is within authorized scope
   - Check tool autonomy tier against execution context
   - Validate tool dependencies (API keys configured, etc.)
   - Block TIER_3 unless explicitly overridden by admin

4. Integration with mission runtime:
   - Link approvals to mission phase/goal
   - Support phase-level vs. tool-level approvals
   - Emit events when approvals are needed/resolved

5. Observability:
   - Audit log: Who approved/denied what, when
   - Metrics: Approval wait times, deny rates by tool
   - Dashboard: Pending approvals, approval history

DELIVERABLES:
- autonomy_tier_enforcement.py with decorator and gate logic
- approval_request.py data model
- hil_approval_gateway.py for operator integration
- pre_flight_checks.py validation functions
- Audit logging integration
- Unit tests for all tier enforcement scenarios

OUTPUT FORMAT:
Provide working decorators, integration points with existing approval system, 
and clear enforcement logic. Include test scenarios for all tiers.
```

---

## ISSUE #9: MEDIUM - Missing Tool Interdependency Graph

### Platform: **Google Gemini (Gemini-CLI)**
**Rationale:** Gemini excels at graph-based reasoning and dependency resolution patterns.

**Persona:** Data Structures & Algorithms Specialist
**Context Window:** DAG (Directed Acyclic Graph) patterns + dependency resolution

```
PROMPT_ID: DEPENDENCIES_009_GEMINI

You are a Data Structures & Algorithms Specialist designing a tool dependency 
management system for a security research platform.

PROBLEM:
Tools have complex interdependencies that the orchestrator doesn't understand:
- DNSDumpster requires API keys; fails without them
- MasscanTool outputs open ports; subsequent tools should consume this
- NucleiTool expects template configurations; orchestrator doesn't validate
- Some tools require prior findings (e.g., Nuclei needs web services from prior scans)

CURRENT STATE: No visible dependency graph management

REQUIREMENTS:

1. Design a ToolDependencyGraph that models:
   - Input requirements: What data this tool needs
   - Output guarantees: What data this tool produces
   - Prerequisites: Conditions that must be true (API keys, target type, etc.)
   - Conflicts: Tools that shouldn't run together
   - Ordering constraints: Tool A must finish before Tool B

2. Define tool metadata (YAML):
   ```yaml
   tools:
     nuclei:
       name: "Nuclei Vulnerability Scanner"
       input_required:
         - urls: "list[str]"
         - templates_dir: "str"
       output_provides:
         - vulnerabilities: "list[Finding]"
         - web_services: "list[WebService]"
       prerequisites:
         - api_keys: ["nuclei_templates_license"]  # Optional, not required
         - environment:
             - K1_NUCLEI_TEMPLATES_HOME: "Path to nuclei templates"
       conflicts:
         - excludes_tools: ["nikto", "burpsuite"]  # Too noisy together
       execution_tier: "TIER_2_APPROVE"
       estimated_cost_cents: 50
       max_execution_time_seconds: 1800
   ```

3. Build graph operations:
   - validate_dependency_chain(tool_sequence): Detect unsatisfiable deps
   - resolve_dependencies(goal): Find minimal tool set to achieve goal
   - find_optimal_order(tools): Topological sort + parallel group detection
   - suggest_next_tools(completed_tools, findings): Recommend next tools
   - detect_cycles(): Prevent infinite loops

4. Prerequisite validation:
   - Check API keys before scheduling tools
   - Validate target type (domain vs. IP vs. URL)
   - Verify required files/configurations exist
   - Check against budget (time, money, rate limits)

5. Output passing:
   - Tools declare outputs they produce
   - Orchestrator matches outputs to next tool's inputs
   - Cache intermediate results
   - Enable tool replay if output cached

6. Testing:
   - Unit tests for graph operations
   - Integration tests with mock tools
   - Scenario tests (common phase chains)

DELIVERABLES:
- ToolMetadata data model (from YAML)
- DependencyGraph class (DAG with validation)
- PrerequisiteValidator class
- OutputMatcher class (input/output schema validation)
- Topological sort + parallel grouping
- Test suite with realistic tool chains

EXAMPLE USAGE:
```python
# Define goals
goal = MissionPhase(
    phase_num=1,
    description="Reconnaissance",
    objectives=["enumerate_subdomains", "identify_web_services"]
)

# Get recommended tools
tools = orchestrator.resolve_dependencies(goal, available_tools)
# Returns: [assetfinder, subfinder, httpx_probe, nuclei]

# Validate chain
issues = dependency_graph.validate_chain(tools)
if issues:
    suggest_fixes(issues)  # Reorder or swap tools

# Execute with dependency-aware parallelization
groups = dependency_graph.find_parallel_groups(tools)
# Returns: [[assetfinder, subfinder], [httpx_probe], [nuclei]]
# Meaning: Run assetfinder+subfinder in parallel, then httpx_probe, then nuclei

# Pass outputs between tools
assetfinder_result = await execute_tool(tools[0])
result_cache[assetfinder.output_id] = assetfinder_result
nuclei_result = await execute_tool(nuclei, input_cache=result_cache)
```

OUTPUT FORMAT:
Provide graph data structure, validation logic, and orchestration integration 
points. Include YAML schema and example tool metadata definitions.
```

---

## ISSUE #10: CRITICAL - Hardcoded Credentials in docker-compose.yml

### Platform: **Claude (Claude-Code)**
**Rationale:** Claude excels at designing secrets management infrastructure and build-time validation.

**Persona:** DevSecOps Infrastructure Architect
**Context Window:** Secrets management + CI/CD pipeline security

```
PROMPT_ID: SECRETS_010_CLAUDE

You are a DevSecOps Infrastructure Architect securing secrets management in a 
cloud-deployed security platform.

VULNERABILITY:
```yaml
environment:
  - DATABASE_URL=postgresql://user:password@postgres:5432/kai_db
  - POSTGRES_USER=user
  - POSTGRES_PASSWORD=password
```
Credentials are hardcoded in version control → exposed on GitHub.

REQUIREMENTS:

1. Design a secrets management architecture:
   - Never commit real secrets to git
   - Support local development without secrets leakage
   - Support CI/CD pipeline with secure secret injection
   - Support production deployments with Vault/AWS Secrets Manager
   - Enable local developers to use test databases without production creds

2. Implement solution:
   a) docker-compose.yml (version control): Use ${VAR} placeholders
   b) .env.example (version control): Template with explanations
   c) .env (local, .gitignore): Developer's actual secrets
   d) Vault/Secrets Manager: Production secrets
   e) CI/CD: Inject secrets at deployment time

3. Local development flow:
   - Developer clones repo
   - Sees .env.example
   - Copies to .env with local test credentials
   - docker-compose up uses .env values
   - No real prod creds needed

4. Production flow:
   - CI/CD pipeline retrieves secrets from Vault
   - Injects as environment variables
   - Never stores secrets in images or compose files
   - Supports secret rotation without redeployment

5. CI/CD integration:
   - GitHub Actions workflow
   - Pre-deployment validation: Scan for hardcoded secrets
   - Reject push if secrets detected
   - Inject Vault secrets at deployment time

6. Validation tools:
   - truffleHog scanning for secret patterns
   - Pre-commit hook to prevent secret commits
   - CI/CD step to block deployments with secrets

DELIVERABLES:
- docker-compose.yml refactored with ${} placeholders
- .env.example with clear documentation
- .gitignore update to exclude .env
- Vault configuration (HCL) for secret storage
- GitHub Actions workflow with secret injection
- Pre-commit hook script (Python)
- CI/CD scanning step using truffleHog
- Developer onboarding guide

OUTPUT FORMAT:
Provide working docker-compose, GitHub Actions workflow, and developer guide. 
Include secrets scanning pipeline.
```

---

## ISSUE #11: MEDIUM - Read-Only Filesystem Blocks Tool Output

### Platform: **GitHub Copilot (Codex)**
**Rationale:** Copilot is best at Docker configuration patterns and volume mounting.

**Persona:** Container DevOps Engineer
**Context Window:** Docker volume management + tool output patterns

```
PROMPT_ID: DOCKER_011_CODEX

You are a Container DevOps Engineer fixing Docker configuration for a 
security tools platform.

CURRENT ISSUE:
docker-compose.yml marks all services as read_only: true, but security tools 
(nmap, nuclei, gitleaks, etc.) MUST write output files. Containers will fail.

```yaml
network-tools-runner:
  read_only: true  # ← Conflict!
  command: ["nmap", "-oX", "/tmp/nmap_output.xml", "target.com"]
  # nmap can't write to /tmp because read_only: true
```

REQUIREMENTS:

1. Fix read_only constraint with writable volumes:
   - Create dedicated output directories
   - Mount as writable volumes
   - Keep rest of filesystem read-only

2. Tool-specific output handling:
   - nmap: /tmp/nmap-output/
   - nuclei: /tmp/nuclei-output/
   - gitleaks: /tmp/gitleaks-output/
   - burpsuite: /tmp/burp-cache/
   - Cache directories: /home/kai/.cache/

3. Implement cleanup strategy:
   - Output files persisted for analysis
   - Cleanup job runs daily, deletes old output
   - Quota enforcement (max 100GB per tool)

4. Add environment variables:
   - K1_ARTIFACTS_ROOT: Where tools write output
   - Tool-specific paths constructed from this root

5. Volume mounting strategy:
   - Host: /var/kai-artifacts/
   - Container: /tmp/kai-artifacts/
   - Mount read-write, rest of FS read-only

DELIVERABLES:
- Updated docker-compose.yml with volume mounts
- Volume initialization scripts
- Cleanup job (cron or systemd timer)
- Tool environment variable setup
- Documentation on artifact storage

OUTPUT FORMAT:
Provide updated docker-compose.yml with all services correctly configured, 
plus volume setup scripts.
```

---

## TOOL BIDDING SYSTEM - IMPLEMENTATION FRAMEWORK

### Agent Bidding Architecture (Integrated with Issues #7-#9)

This framework bridges Issues #7 (Tool Selection), #8 (Autonomy Tiers), and #9 (Dependencies):

```python
# File: apps/backend/src/core/tool_bidding_system.py

"""
Tool Agent Bidding System
========================
Multi-agent competitive bidding for tool execution based on mission context.

Each tool evaluates the current mission state and "bids" to execute:
- Confidence: How confident this tool solves current goal
- Cost: API calls, execution time, resources
- Dependencies: What prior findings required
- Autonomy: Tier requirements (TIER_0 through TIER_3)

Orchestrator collects bids, ranks by value, executes top N with approval gates.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
import json

class ToolAutonomyTier(Enum):
    TIER_0_AUTO = 0          # Execute immediately
    TIER_1_NOTIFY = 1        # Execute immediately, log it
    TIER_2_APPROVE = 2       # Wait for approval
    TIER_3_HARD_STOP = 3     # Block, require admin override

@dataclass
class ToolBid:
    """A tool's bid to execute in the current mission phase"""
    tool_id: str
    tool_name: str
    confidence: float                    # 0.0-1.0: How confident this tool solves goal
    estimated_cost_cents: float          # API calls cost estimate
    execution_time_estimate_ms: int      # How long this tool takes
    output_schema: Dict[str, str]        # What data this tool produces
    dependencies: List[str]              # Required prior findings
    priority_boost: float = 1.0          # 1.0=normal, 2.0=urgent
    autonomy_tier: ToolAutonomyTier = ToolAutonomyTier.TIER_1_NOTIFY
    reasoning: str = ""                  # Explanation for bid
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def bid_score(self) -> float:
        """
        Ranking score: higher is better
        confidence * cost_factor * priority
        """
        if self.confidence < 0.1:
            return 0.0  # Tool abstains
        
        # Cost factor: lower cost = higher factor
        # $0.10 → 0.5 factor, $5.00 → 0.1 factor
        cost_factor = 100.0 / (100.0 + self.estimated_cost_cents)
        
        return self.confidence * cost_factor * self.priority_boost
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "bid_score": self.bid_score,
            "confidence": self.confidence,
            "estimated_cost_cents": self.estimated_cost_cents,
            "execution_time_estimate_ms": self.execution_time_estimate_ms,
            "autonomy_tier": self.autonomy_tier.name,
            "priority_boost": self.priority_boost,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp.isoformat(),
        }

@dataclass
class MissionContext:
    """Current state of a security hunting mission"""
    target: str
    phase: int                           # 1=Recon, ..., 9=Reporting
    phase_name: str                      # "Reconnaissance", "Vulnerability Scanning", etc.
    goals: List[str]                     # Mission objectives
    findings_so_far: Dict[str, Any]      # Prior findings/data
    budget_remaining_cents: float        # Cost budget
    time_budget_remaining_ms: int        # Time budget
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def summary(self) -> str:
        return f"Phase {self.phase} ({self.phase_name}) on {self.target}: {self.goals}"

class IToolAgent:
    """Base interface for tool agents in bidding system"""
    
    async def evaluate_mission(
        self,
        mission_context: MissionContext
    ) -> ToolBid:
        """
        Evaluate if this tool should execute in current mission state.
        
        Returns ToolBid with confidence > 0 if tool should run, 
        confidence = 0 if tool abstains.
        """
        raise NotImplementedError
    
    async def execute(
        self,
        target: str,
        options: Optional[Dict[str, Any]] = None,
        mission_id: str = "mission-001"
    ) -> Dict[str, Any]:
        """Execute the tool"""
        raise NotImplementedError

class BiddingOrchestrator:
    """
    Collects tool bids, ranks by value, selects best execution set.
    Integrates with approval gates and dependency validation.
    """
    
    def __init__(self):
        self.execution_history: List[Dict[str, Any]] = []
        self.bid_history: List[ToolBid] = []
    
    async def select_tools_for_phase(
        self,
        mission_context: MissionContext,
        available_tools: List[IToolAgent]
    ) -> Dict[str, Any]:
        """
        Request bids from tools, rank, validate dependencies, apply approval gates.
        
        Returns:
        {
            "selected_tools": [tool_ids],
            "bids": [ToolBid],
            "pending_approvals": [approval_ids],
            "ready_to_execute": [tool_ids],
            "blocked_tools": [{tool_id, reason}],
            "reasoning": "Summary of selection logic"
        }
        """
        
        # STEP 1: Collect bids from all tools
        bids = await self._collect_bids(available_tools, mission_context)
        self.bid_history.extend(bids)
        
        # STEP 2: Filter abstentions (confidence < 0.1)
        viable_bids = [b for b in bids if b.confidence > 0.1]
        
        if not viable_bids:
            return {
                "selected_tools": [],
                "bids": [],
                "pending_approvals": [],
                "ready_to_execute": [],
                "blocked_tools": [],
                "reasoning": "No tools bid to execute in this phase"
            }
        
        # STEP 3: Rank by bid score
        ranked_bids = sorted(viable_bids, key=lambda b: b.bid_score, reverse=True)
        
        # STEP 4: Validate dependencies for each bid
        dependency_issues = self._validate_dependencies(ranked_bids, mission_context)
        
        # STEP 5: Apply autonomy tier gates
        approval_decisions = await self._apply_autonomy_gates(ranked_bids)
        
        # STEP 6: Select best subset within constraints
        selected = self._select_best_subset(ranked_bids, mission_context, approval_decisions)
        
        return {
            "selected_tools": [b.tool_id for b in selected["ready"]],
            "bids": [b.to_dict() for b in ranked_bids],
            "pending_approvals": selected["pending_approvals"],
            "ready_to_execute": [b.tool_id for b in selected["ready"]],
            "blocked_tools": selected["blocked"],
            "dependency_issues": dependency_issues,
            "reasoning": self._generate_reasoning(ranked_bids, selected)
        }
    
    async def _collect_bids(
        self,
        available_tools: List[IToolAgent],
        mission_context: MissionContext
    ) -> List[ToolBid]:
        """Request bids from all available tools in parallel"""
        import asyncio
        
        bids = await asyncio.gather(*[
            tool.evaluate_mission(mission_context)
            for tool in available_tools
        ], return_exceptions=True)
        
        # Filter out exceptions, keep only valid ToolBids
        return [b for b in bids if isinstance(b, ToolBid)]
    
    def _validate_dependencies(
        self,
        bids: List[ToolBid],
        mission_context: MissionContext
    ) -> List[Dict[str, Any]]:
        """Check if each bid's dependencies are satisfied"""
        issues = []
        
        for bid in bids:
            for dep in bid.dependencies:
                if dep not in mission_context.findings_so_far:
                    issues.append({
                        "tool_id": bid.tool_id,
                        "missing_dependency": dep,
                        "action": "SKIP - dependency unsatisfied"
                    })
        
        return issues
    
    async def _apply_autonomy_gates(
        self,
        bids: List[ToolBid]
    ) -> Dict[str, str]:
        """
        Apply autonomy tier gates:
        - TIER_0: Execute immediately
        - TIER_1: Execute, log it
        - TIER_2: Request approval (blocking)
        - TIER_3: Block unless admin override
        """
        from apps.backend.src.core.approval_gate_service import ApprovalGateService
        
        decisions = {}
        
        for bid in bids:
            if bid.autonomy_tier == ToolAutonomyTier.TIER_0_AUTO:
                decisions[bid.tool_id] = "AUTO_EXECUTE"
            
            elif bid.autonomy_tier == ToolAutonomyTier.TIER_1_NOTIFY:
                decisions[bid.tool_id] = "AUTO_EXECUTE_NOTIFY"
            
            elif bid.autonomy_tier == ToolAutonomyTier.TIER_2_APPROVE:
                # Request approval asynchronously
                approval_id = await ApprovalGateService.request_approval(
                    tool_id=bid.tool_id,
                    reason=f"Execute {bid.tool_name}: {bid.reasoning}",
                    timeout_seconds=3600
                )
                decisions[bid.tool_id] = f"PENDING_APPROVAL:{approval_id}"
            
            elif bid.autonomy_tier == ToolAutonomyTier.TIER_3_HARD_STOP:
                decisions[bid.tool_id] = "BLOCKED_TIER_3"
        
        return decisions
    
    def _select_best_subset(
        self,
        bids: List[ToolBid],
        mission_context: MissionContext,
        approval_decisions: Dict[str, str]
    ) -> Dict[str, Any]:
        """Select best set of tools that fit constraints"""
        
        ready = []
        pending_approvals = []
        blocked = []
        
        total_cost = 0.0
        total_time = 0
        
        for bid in bids:
            decision = approval_decisions.get(bid.tool_id, "UNKNOWN")
            
            if decision.startswith("BLOCKED"):
                blocked.append({
                    "tool_id": bid.tool_id,
                    "reason": decision
                })
                continue
            
            if decision.startswith("PENDING_APPROVAL"):
                pending_approvals.append(decision)
                continue
            
            # Check budget constraints
            if total_cost + bid.estimated_cost_cents > mission_context.budget_remaining_cents:
                blocked.append({
                    "tool_id": bid.tool_id,
                    "reason": f"Over budget: {bid.estimated_cost_cents} cents"
                })
                continue
            
            if total_time + bid.execution_time_estimate_ms > mission_context.time_budget_remaining_ms:
                blocked.append({
                    "tool_id": bid.tool_id,
                    "reason": f"Over time budget: {bid.execution_time_estimate_ms}ms"
                })
                continue
            
            # Tool fits constraints, add to ready list
            ready.append(bid)
            total_cost += bid.estimated_cost_cents
            total_time += bid.execution_time_estimate_ms
        
        return {
            "ready": ready,
            "pending_approvals": pending_approvals,
            "blocked": blocked
        }
    
    def _generate_reasoning(
        self,
        all_bids: List[ToolBid],
        selection: Dict[str, Any]
    ) -> str:
        """Generate human-readable explanation of selection"""
        
        ready = selection["ready"]
        blocked = selection["blocked"]
        
        summary = f"Selected {len(ready)} tools:\n"
        
        for bid in ready:
            summary += f"  - {bid.tool_name} (score={bid.bid_score:.2f}, confidence={bid.confidence:.0%})\n"
        
        if blocked:
            summary += f"\nSkipped {len(blocked)} tools:\n"
            for block in blocked:
                summary += f"  - {block['tool_id']}: {block['reason']}\n"
        
        return summary

# Usage Example:
async def execute_mission_phase(mission_context: MissionContext):
    """Execute a mission phase using intelligent tool bidding"""
    
    from apps.backend.src.agents.tools.all_agents import get_all_tool_agents
    
    orchestrator = BiddingOrchestrator()
    available_tools = get_all_tool_agents()
    
    # Request bids and select tools
    result = await orchestrator.select_tools_for_phase(
        mission_context,
        available_tools
    )
    
    print(f"Decision: {result['reasoning']}")
    
    # Execute ready tools
    for tool_id in result["ready_to_execute"]:
        tool = get_tool_by_id(tool_id)
        result = await tool.execute(mission_context.target)
        
        # Record execution for learning
        await orchestrator.record_execution(
            tool_id=tool_id,
            result=result,
            mission_context=mission_context
        )
    
    # Wait for pending approvals
    if result["pending_approvals"]:
        await orchestrator.wait_for_approvals(result["pending_approvals"])
```

---

## SUMMARY: Prompt Execution Order

Execute prompts in this order within VS Code using respective extensions:

1. **SECURITY_001_CODEX** - Remove bootstrap auth (Copilot)
2. **VALIDATION_002_CLAUDE** - Subprocess validators (Claude-Code)
3. **SESSION_003_GEMINI** - Token revocation (Gemini-CLI)
4. **CSRF_004_CODEX** - CSRF hardening (Copilot)
5. **SECRETS_005_CLAUDE** - Secret caching with TTL (Claude-Code)
6. **RATELIMIT_006_GEMINI** - Distributed rate limiting (Gemini-CLI)
7. **ORCHESTRATION_007_CLAUDE** - Tool bidding system (Claude-Code) ⭐ **CORE**
8. **AUTONOMY_008_CODEX** - Autonomy tier enforcement (Copilot)
9. **DEPENDENCIES_009_GEMINI** - Tool dependency graph (Gemini-CLI)
10. **SECRETS_010_CLAUDE** - Secrets management (Claude-Code)
11. **DOCKER_011_CODEX** - Docker volume fixes (Copilot)

---

## Integration: Tool Bidding System

The Tool Bidding System (Issue #7) acts as the **orchestration core** that integrates:

- **Issue #8** (Autonomy Tiers): Bids include autonomy_tier; orchestrator applies gates
- **Issue #9** (Dependencies): Bids include dependencies; orchestrator validates
- **Issue #7** (Tool Selection): Bids are ranked by confidence * cost_factor * priority

```
Agent 1 (nuclei):  confidence=0.8, cost=50c → bid_score = 0.8 * 0.67 * 1.0 = 0.54
Agent 2 (nmap):    confidence=0.9, cost=20c → bid_score = 0.9 * 0.83 * 1.0 = 0.75  ✓ Selected
Agent 3 (subfind): confidence=0.6, cost=10c → bid_score = 0.6 * 0.91 * 1.5 = 0.82  ✓ Selected
Agent 4 (sqlmap):  confidence=0.3, cost=200c, TIER_3 → blocked, request approval

→ Execute: [nmap, subfinder] in parallel, then wait for sqlmap approval
```

---

End of Prompt Generation
