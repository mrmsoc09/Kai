# Skill: Recon Orchestration

Objective: coordinate authorized recon (dnsx, httpx, naabu, gau, ffuf, trivy) via adapters.

When to use: opportunity engagement and recon phases.

Inputs: scoped target list, program_id, method, rate/OPSEC profile.

Outputs: Evidence Objects with artifacts hashed under `artifacts/<run_id>/<tool_id>/`.

Workflow:
- Validate scope/authorization.
- Select tools via capability registry and routing policy.
- Dispatch through wrappers in `ai-kernel/wrappers/security`.
- Normalize outputs and store evidence.

Boundaries:
- No intrusive actions beyond declared methods.
- No credential brute force or DoS.

Failure handling:
- Mark degraded, record missing binaries, avoid retries beyond policy.
