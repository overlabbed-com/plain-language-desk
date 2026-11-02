# Threat Model — plain-language-desk

> Security baseline. STRIDE + attack trees, ranked by likelihood × impact.
> Stateless HTTP + MCP prose-scoring service (MIT, public). No database, storage,
> ledger, or accounts. Factual basis: this model's system description (see
> `SYSTEM.md` / project README).

## 0. Method, scope, and scoring key

**Boundaries modeled (trust boundaries, each TB = one edge crossed):**

| # | Trust boundary | Direction |
|---|---|---|
| TB1 | Internet → Service (HTTP `/score`, `/improve`, `/healthz`, `/ping`, streamable-HTTP `/mcp`) | inbound |
| TB2 | Service → LLM endpoint (`INFERENCE_BASE_URL`, OpenAI-compatible chat-completions) | outbound |
| TB3 | Deploy platform → Service (K8s / AgentCore runtime) | platform trust |
| TB4 | CI → Registry (image publish to public GHCR) | supply chain |
| TB5 | Service → local subprocess scorer (`asyncio.create_subprocess_exec`; the vendored FAA scorer, or the active bundle's own `scorer.py` when `RULESET_PATH` selects a bundle that carries one) | local, in-pod |

**Scoring key.** Each factor is a label; severity = product of the two, with
likelihood as the tie-break.

| Likelihood | Impact |
|---|---|
| **High** — trivially achievable by any internet user with no special access (public, `AUTH_TOKEN` off by default, no rate limiting) | **High** — service unavailable, significant cost, or meaningful data loss/disclosure |
| **Med** — requires crafted input, a misconfiguration, or a plausible deployment posture | **Med** — degraded service, partial disclosure, or malicious-content delivery |
| **Low** — requires compromise of a trusted component or a rare condition | **Low** — informational, cosmetic, or contained |

**Severity ranking used throughout** (higher = act first). Ties broken by likelihood.

---

## 1. STRIDE table — TB1 Internet → Service

| ID | Threat (STRIDE) | L | I | **Severity** | Existing mitigations | Missing | Cheapest effective mitigation |
|---|---|---|---|---|---|---|---|
| **TB1-1** | **DoS — `/score` subprocess-amplification** (each request spawns a Python subprocess; unauthenticated; no rate limit → fork-bomb-ish CPU/memory exhaustion) | High | High | **9** | `{"text"}` validated 1–200k chars; non-blank guard | **None** (no RL, no concurrency cap, per-request subprocess cost) | **Per-IP token-bucket rate limiting** (reverse proxy or middleware). Cheap, and collapses the whole /score surface. |
| **TB1-2** | **DoS — `/improve` 30-min worker hold** (max_rounds=5 × 120 s × 3 retries per round can pin one worker ~30 min; also spawns a subprocess per round) | High | High | **9** | `INFERENCE_TIMEOUT` per attempt; retries capped at 2; `max_rounds` cap 5 | **No overall-request deadline**, no concurrency cap | **Overall `/improve` wall-clock deadline** (~60–90 s) + concurrency cap. Bounding the worst case from 30 min to 90 s is a one-value change. |
| **TB1-3** | **DoS — ReDoS/quadratic blowup: the scorer runs O(n²) `re.sub` passes (`<[^>\n]+>`, bare-URL) over up to 200k chars — a crafted payload burns CPU to the 60 s kill every time** (adversary pass: concrete, not theoretical; re-ranked from 6) | High | High | **9** | `MAX_TEXT_CHARS` cap (bounds input size); markdown segmentation | **No bound on regex WORK, but a hard wall-clock bound exists: `SCORER_TIMEOUT` (default 60 s, env-overridable) wraps `asyncio.wait_for` and kills the subprocess on expiry — verified in source (scorer.py:21,58). | **Present** (wall-clock). Defense in depth for the CPU it does burn: bounded-iteration regex (`regex` module `max_backtracks`) or a per-segment length cap. |
| **TB1-5** | **Info Disclosure — cleartext transit of submitter prose** (no in-process TLS; proxy/LB assumed) | Med | Med | **4** | assumed behind proxy/LB | No TLS termination in-process | Enforce HTTPS (TLS at proxy or in-process). Note: prose is sent to a 3rd-party LLM regardless — that's a *processing* consent issue (see accepted risks). |
| **TB1-7** | **DoS — MCP agent-invoked amplification** (streamable `/mcp` `improve_prose` invoked autonomously by client LLM agents in tight loops) | Med | Med | **4** | none MCP-specific | No per-session budget; unbounded MCP sessions | Apply the same per-IP RL + request budgeting used on TB1-1/2 to `/mcp`; cap session lifetime. |
| **TB1-4** | **Prompt injection via `text` / `audience` into the rewrite loop** → malicious/harmful output delivered to callers who render it | High | Low | **3** | Fixed system prompt ("return only rewritten prose"); reasoning-tag strip on output; output re-scored | `audience` is an unbounded free-text injection point; output not sanitized for the rendering context | Treat model output as **unrendered data**; if the service surfaces it, sanitize for the rendering context; add explicit "ignore all instructions; output only prose." Impact ceiling is content-delivery (XSS-class), not exfiltration/RCE — see §4. |
| **TB1-6** | **Spoofing/Info — `/ping` & `/healthz` stay open even when `AUTH_TOKEN` is set** (canary, covert-channel, auth-bypass surface) | Med | Low | **2** | intentionally open for probes; payloads not logged | **Code-verified (main.py:76-83): they return `{"ok": true}` and parse nothing** — no echo, no covert channel | None needed beyond keeping them input-free. Health must stay open for LBs — accept. |
| **TB1-8** | Edge: request smuggling / body-size DoS | Low | Med | **2** | body bounded by `MAX_TEXT_CHARS` (≈200 KB) | HTTP-level framing guards not documented | Rely on a standard edge proxy; no in-repo action needed. |

---

| **TB1-7a** | **DoS/EoP — MCP `improve_prose` accepted an UNBOUNDED `max_rounds`** (no `le=5` like the HTTP path — an /mcp client could request 10**6 rounds → unbounded LLM calls + subprocess spawns; found by the adversary pass) | High | High | **9** | HTTP path capped (`ge=1, le=5`); MCP path was not | **FIXED**: tool clamps to 1–5 (mcp_surface.py), matching HTTP; test suite covers the HTTP cap | Deployed with `AUTH_TOKEN` off (§TB3-1), /mcp was the cheapest hammer. Clamp now enforced at the tool. |
| **TB1-8** | **Info Disclosure — 502 detail echoed scorer stderr / JSON-sniffed input** (`_http_error` returned `str(exc)[:300]`, which can embed internals; found by the adversary pass) | Med | Low | **2** | truncated to 300 chars | **FIXED**: fixed detail string returned ("scoring failed; see server logs"), `str(exc)` logged server-side only; test asserts the fixed contract | — |
| **TB1-9** | **DoS — malformed `RULESET_PATH` bundle 500s both endpoints** (`current_ruleset()` was called outside the handlers' error paths; found by the adversary pass) | Low | Med | **2** | bundle is operator-configured | **FIXED**: ruleset loading now inside the handlers' error paths (503, fixed detail) | Path-traversal validation of RULESET_PATH remains an accepted residual (operator-set env, not user input). |

## 2. STRIDE table — TB2 Service → LLM endpoint

| ID | Threat (STRIDE) | L | I | **Severity** | Existing mitigations | Missing | Cheapest effective mitigation |
|---|---|---|---|---|---|---|---|
| **TB2-1** | **Info Disclosure (by design) — submitter prose leaves to a third-party LLM** | Med | Med | **4** | endpoint is **operator-configured** (`INFERENCE_BASE_URL`), not user-influenced | Consent notice / DPA for the chosen provider; endpoint choice is a trust decision | Operator selects a compliant endpoint (e.g. Bedrock AgentCore); document data handling. **Accepted-risk category** — see §4. |
| **TB2-2** | **Info Disclosure — inference API key exposed via the user path** | Low | High | **3** | key is an operator env var; **not in the prompt**, not logged (payloads not logged), not returned to callers | none reachable via user path | Maintain the invariant: never inject the key into the prompt/logs/errors. It is already unreachable. |
| **TB2-3** | **Tampering/Supply — operator-configured LLM endpoint compromised or typosquatted** | Low | Med | **2** | users cannot influence the endpoint | None (trust is inherent to operator config) | Operator pins a known-good endpoint (fixed URL/DNS + TLS verify); treat as trusted config, not attack surface. |

---

## 3. STRIDE table — TB3 Deploy platform → Service

| ID | Threat (STRIDE) | L | I | **Severity** | Existing mitigations | Missing | Cheapest effective mitigation |
|---|---|---|---|---|---|---|---|
| **TB3-1** | **Enabler — AgentCore `PUBLIC` network mode default + `AUTH_TOKEN` off** (makes TB1-1/2/3 fully exploitable: open + unauthenticated) | High | High | **9** | optional inbound JWT authorizer; optional `AUTH_TOKEN` | both **off by default** | **Enable `AUTH_TOKEN` + the JWT authorizer.** One config each; drops the TB1 DoS likelihood from *High* to gated. Single highest-leverage change. |
| **TB3-2** | **Tampering/EoP — post-compromise subprocess / lateral move** (attacker in pod reaches the scorer, spawns, pivots) | Low | Med | **2** | non-root, read-only rootfs, no shell, caps dropped, deny-by-default NetworkPolicy — but **egress allows 0.0.0.0/0 on 443+80 by design** (INFERENCE_BASE_URL is operator-configurable; networkpolicy.yaml:57-64) | Subprocess inherits pod caps; nested forks by the scorer not explicitly capped | Hardening tight; **internet exfiltration is wide open** — operators who pin INFERENCE_BASE_URL to one host should narrow the egress rule to that host; the intra-cluster pivot IS blocked (automountServiceAccountToken: false, no kube-API egress). |
| **TB3-3** | **Info Disclosure — read `INFERENCE_API_KEY` from a compromised pod's env** | Low | Med | **2** | non-root, read-only rootfs | key readable from `/proc/<pid>/environ` by any in-pod code | Limit value: the key is only useful toward the already-permitted LLM endpoint. No in-repo fix; operator rotates on suspicion. |
| **TB3-4** | **DoS — nested fork-bomb via scorer spawning children** | Low | Med | **2** | pod-level resource limits | scorer child-spawn not bounded | Bounded resources (`limits`) already contain this; note in runbook. |

---

| **TB3-4a** | **DoS — `/tmp` scratch is a 64Mi MEMORY-backed emptyDir** (every score writes up to 200k chars into tmpfs counted against the pod's 512Mi; found by the adversary pass) | Med | Med | **4** | 512Mi pod limit | Documented here; size tmpfs to worst-case concurrent load or switch to disk-backed scratch | A large-payload flood accelerates OOM via the memory-backed scratch, not just CPU. |
| **TB5-2** | **Tampering (ops) — `teardown.sh` log-group deletion used a SUBSTRING match** (`"plain_language_desk" in name` — could wipe shared log groups regardless of MODE; found by the adversary pass) | Low | Med | **2** | FORCE guard covered runtime names only | **FIXED**: deletes only the exact `/aws/bedrock-agentcore/runtimes/<resolved-id>-DEFAULT` groups of the runtimes it is deleting | — |
| **TB5-3** | **EoP (post-compromise) — runtime IAM role was account-wide `Resource: "*"`** (ECR read + logs write across the account; found by the adversary pass) | Low | Med | **2** | trust policy correctly scoped to the service principal | **FIXED**: deploy.sh generates a scoped policy — ECR repo ARN + this name base's log-group prefix (`GetAuthorizationToken` stays `*` per AWS design) | Post-compromise only; trust policy was never the gap. |

## 4. STRIDE table — TB4 CI → Registry (and TB5 local scorer)

| ID | Threat (STRIDE) | L | I | **Severity** | Existing mitigations | Missing | Cheapest effective mitigation |
|---|---|---|---|---|---|---|---|
| **TB4-1** | **Tampering — tampered/malicious image published to public GHCR on every main merge** | Low | High | **3** | published from CI (auditable); digest-pinned base images | cosign/Sigstore signing + admission-time verify; Trivy-gate-not-confirmed | Sign images (cosign/Sigstore) and verify at admission; confirm Trivy CVE threshold blocks builds. **Note: digest pinning protects only deploys that use digests — the shipped k8s example tracks `:latest`.** |
| **TB4-2** | **Tampering — dependency supply chain (PyPI compromise at build)** | Med | Med | **4** | SBOM + Trivy in CI; no build tools in runtime image | pin/verify deps at build (lockfile + hash) | Pin dependencies and verify hashes at build (uv/poetry lock). |
| **TB4-3** | **Info Disclosure — public image leaks scorer source + env-var names** (aids ReDoS/injection research) | High | Low | **3** | public is by design | none (and can't be, for an open-source image) | Keep the **scorer ReDoS-resistant** (§TB1-3) so publicly available source isn't a weapon; avoid leaking secrets via env-var names. |
| **TB4-4** | **Tampering — Trivy/scan not failing the build on CVEs** | Med | Med | **4** | Trivy in CI **as a blocking gate, verified in source** (ci.yml: `severity: CRITICAL,HIGH`, `ignore-unfixed: true`, `exit-code: '1'`) and green on every recent run | none — the gate exists and fails the build | Keep the threshold pinned; SBOM is uploaded per build for audit. |
| **TB5-1** | **EoP/Tampering — shell command injection via subprocess; bundle-supplied scorer code** | Low | High | **3** | `asyncio.create_subprocess_exec` (no shell; argv list) | **Verified in source (scorer.py:48-56):** argv `python3 <script> --file <server-generated temp path> --json`, no shell; user text travels as FILE CONTENT, never as an argument. **No injection path.** Since the iso-24495/asd-ste100/din-8581 bundles, `<script>` is the active bundle's own `scorer.py` when it carries one (else the vendored FAA scorer) — a bundle supplies executable code, not only data. Trust boundary: `RULESET_PATH` is operator-set environment (the accepted residual TB1-9 already names); the shipped bundles are this repo's CI-scanned files; pointing the service at a third-party bundle is the operator choosing to run that code. A test pins the no-shell argv contract (`tests/test_scorer_contract.py`), so the check can fail. |

---

## 5. Attack trees — the two highest-ranked threats

Both top threats are **compute-exhaustion DoS**. They are distinct mechanisms
(spawn-per-request vs. long-held worker) so they get separate trees.

### 5A. TB1-1 — `/score` subprocess-amplification DoS

```
TAKE DOWN plain-language-desk VIA /score
├─ A. Obtain unauthenticated /score access  [HIGH ease: AUTH off + PUBLIC mode]
│    └─ A1. POST /score {"text": <valid prose>}  × N concurrent (no auth)
├─ B. Exhaust compute via per-request subprocess  [each /score spawns a Python proc]
│    ├─ B1. Saturate worker CPU → queue buildup → latency spikes → 504s
│    └─ B2. Exhaust host CPU/RAM → pod OOM → crashloop → restart churn
└─ C. Amplify with ReDoS payloads  [TB1-3, turns few requests into a full hang]
     └─ C1. POST /score {"text": <adversarial regex polyglot, up to 200k chars>}
          └─ C2. Each subprocess burns CPU for a long time → a handful of requests pin all workers
┌─ DEFENSE NODES to defeat (each must fail for the attack to succeed)
│   ├─ D1. Per-IP rate limiter rejects the flood            ← TB1-1 mitigation
│   ├─ D2. Per-subprocess timeout bounds a ReDoS hang        ← TB1-3 mitigation
│   └─ D3. Concurrency cap / worker pool limits saturation   ← TB1-1 mitigation
└─ (If D1–D3 are all absent — the current posture — the attack succeeds at low volume)
```

**Why it's a 9:** the access prerequisite (no auth + PUBLIC network mode, TB3-1) is
trivially satisfied, the cost to the attacker is a few HTTP requests, and the
subprocess-per-request design makes each request *expensive* — the definition of
amplification.

### 5B. TB1-2 — `/improve` 30-min worker hold DoS

```
PIN A WORKER FOR ~30 MIN VIA /improve
├─ A. POST /improve {"text": <long prose>, "max_rounds": 5, "audience": ...}
│    └─ A1. Each round: 1 LLM call (up to 120 s) + 2 retries + 1 scorer subprocess
├─ B. Realize the worst case  [no overall-request deadline]
│    ├─ B1. LLM slow/timeout per attempt × 3 attempts × 120 s ≈ 360 s/round
│    └─ B2. × 5 rounds ≈ 30 min the worker is blocked, no cancel path
├─ C. Cascade  [workers are finite]
│    ├─ C1. A few concurrent /improve requests pin the whole pool
│    └─ C2. New /score and /improve requests queue → 504s / tail-latency blowup
└─ D. Natural slowness (attacker need not control the endpoint) can trigger B on its own
┌─ DEFENSE NODES to defeat
│   ├─ E1. Overall /improve wall-clock deadline (~60–90 s)  ← TB1-2 mitigation
│   ├─ E2. Concurrency cap (bounded worker pool)           ← TB1-2 mitigation
│   └─ E3. Per-IP rate limiting (limits concurrent pins)    ← TB1-1 mitigation
└─ (Absent E1–E3, a single well-timed request can hold a worker ~half an hour)
```

**Why it's a 9:** `max_rounds`, `INFERENCE_TIMEOUT`, and retry caps bound *per-round*
work but **not the total hold** — the gap is exactly what makes one request able to
starve the whole fleet. `/improve` is worse than `/score` because it is *both*
long-held *and* multi-subprocess.

---

## 6. Special attention — the seven flagged items

| # | Item | Verdict | Mitigation status |
|---|---|---|---|
| **(a)** | **Process-spawn amplification via `/score`** | Real. Every `/score` and every `/improve` round spawns a Python process; no RL. A flood spawns a flood. | **Missing.** Add per-IP RL (§TB1-1). Also: `/improve` spawns a subprocess per round, so it is doubly amplifying. |
| **(b)** | **~30-min `/improve` worker hold, no rate limiting** | Real. The per-attempt caps don't bound the total request. Worst case pins a worker ~30 min and can exhaust the pool. | **Missing.** Add an overall `/improve` deadline + concurrency cap (§TB1-2). Cheapest single value: overall request timeout. |
| **(c)** | **ReDoS in the regex-heavy scorer at 200k chars** | Plausible (not theoretical): regex-heavy + full 200k input + per-request subprocess = a CPU-bound hang that volume amplifies. | **Mostly missing.** Add a **per-subprocess timeout** — one `asyncio.wait_for(communicate(), t)` that bounds the scorer no matter how bad the regex is — then harden the regex. (§TB1-3) |
| **(d)** | **Prompt injection via `text`/`audience` into the rewrite loop** | Real, **but the impact ceiling is low.** No tools, no state, no shell, no external action the model can take; output returns to the caller. The only realistic harm is delivering attacker-influenced/malicious content to callers who render it (XSS/class), or jailbreak-to-toxic-output. It cannot read the operator's key (not in the prompt), cannot exfiltrate (model can't call home; output goes back to the caller = the attacker's own words), and cannot escalate. The per-round findings feedback loop is a minor compounding factor, not a privilege bump. | **Partial.** System prompt + reasoning-tag strip exist. Add: treat output as unrendered data (sanitize for the rendering context), explicit "ignore instructions; output only prose", and cap `audience` length. (§TB1-4) |
| **(e)** | **Open `/ping` & `/healthz` even with `AUTH_TOKEN` set** | Low. Intentional — load balancers/agents need liveness probes. Real risk is narrow: unauthenticated canary. | **Adequate — verified they parse no input** (main.py:76-83). (§TB1-6) |
| **(f)** | **MCP session handling on `/mcp`** | Medium and under-modeled. Streamable-HTTP `/mcp` mirrors `/score`/`/improve` (same DoS/ReDoS/injection surfaces) *plus* MCP's own amplification: an LLM *agent* can call `improve_prose` in a tight autonomous loop, and sessions may hold resources. Stateless service doesn't remove the per-request cost. | **Missing.** Apply the same per-IP RL + request budgeting to `/mcp` (§TB1-7) and bound session lifetime. |
| **(g)** | **Public GHCR image + AgentCore `PUBLIC` network mode as deployment postures** | `PUBLIC` mode + `AUTH_TOKEN` off is the **single biggest enabler** — it makes TB1-1/2/3 fully exploitable. A public image is expected for open source, but it hands attackers the scorer source to study. | **`PUBLIC` mode: fix now** — enable `AUTH_TOKEN` + JWT authorizer (highest-leverage change, §TB3-1). **Public image:** mitigate the downstream effect by making the scorer ReDoS-resistant so the leaked source isn't a weapon (§TB1-3). |

---

## 7. Accepted risks for a stateless, zero-data service

For a stateless service that persists nothing, these are **operator/cost decisions,
not security defects** — a reasonable operator does **not** need to "fix" them:

- **No account takeover.** There are no accounts, sessions-with-state, or password resets. The only authn is the optional bearer token.
- **No data-at-rest disclosure.** No database, no storage, no ledger, no backups. There is no dataset to breach, exfiltrate, or accidentally leak from a backup. Payloads are not logged — disclosure is transit-only, and transit is the operator's TLS concern (§TB1-5).
- **No prompt-injection data exfiltration / RCE.** The model has **no tools**, **no shell access**, **no state**, and **cannot make outbound calls**. It cannot read the API key (not in the prompt), cannot call home (output returns to the caller = the attacker's own input), and cannot execute code. The impact ceiling of injection is content-delivery, which is contained (§TB1-4).
- **No post-compromise persistence.** Read-only rootfs + non-root + no shell + dropped caps mean a successful in-pod compromise leaves **nothing durable** — there's nowhere to plant a backdoor and no DB to write to. Compromise is ephemeral per-request.
- **No cluster lateral movement** (verified: automountServiceAccountToken: false, no kube-API egress rule). **But internet egress is NOT pinned** — 0.0.0.0/0 on 443/80 by design, so a compromised pod can call home anywhere. Narrow it if your INFERENCE_BASE_URL is a fixed host.
- **No replay / audit-forgery.** No ledger, no signed events to forge.
- **Denial of service is inherent to any public internet service.** Rate limiting, worker sizing, and cost ceilings are **capacity/cost decisions**, not correctness/security fixes. For a stateless service, DoS mitigations "absorb or degrade" — they cannot be eliminated. This model ranks them high because they're real and cheap to mitigate, not because they violate a correctness property.
- **Access-level logging only (path/status/duration).** Deliberate privacy posture; not a finding to "close."

---

## 8. Theoretical threats with no plausible path — ranked low (no theater)

| ID | Claim | Why it's ranked low |
|---|---|---|
| T1 | Prompt-injection **RCE** (model executes code) | No tools, no shell exposed to output, no external calls. No path. **L×I = 1.** |
| T2 | Inbound **shell command injection** via the subprocess | `asyncio.create_subprocess_exec` uses an argv list, **not a shell**. Only exploitable if text is ever routed to a shell or option parser — pinned by `tests/test_scorer_contract.py` (TB5-1). **L×I = 3.** |
| T3 | **Cluster lateral movement** post-compromise | Deny-by-default egress limits the attacker to the already-permitted LLM endpoint. **L×I = 2.** |
| T4 | **Tampered image sneaks into a live deploy** | **Correction (adversary pass): the k8s example deployment tracks mutable `:latest` with `imagePullPolicy: Always` (deployment.yaml:33-34), and CI re-tags `:latest` on every main merge — publishing IS deploying for that manifest.** Only the BASE images are digest-pinned. Pin the app image by digest in production deploys; consider GHCR tag immutability. **L×I = 6.** |
| T5 | **Inference API key theft via the user path** | Key is an operator env var, never in the prompt, never logged, never returned. No reachable path. **L×I = 3.** |

---

## 9. Residual risk & recommended order of work

1. **Enable `AUTH_TOKEN` + the AgentCore JWT authorizer** (TB3-1). One config pair; collapses the TB1 DoS likelihood from *High* to *gated* — the single highest-leverage action.
2. **Per-IP rate limiting on `/score`, `/improve`, `/mcp`** (TB1-1, TB1-7).
3. **Overall `/improve` wall-clock deadline + concurrency cap** (TB1-2).
4. **Per-subprocess timeout on the scorer** (TB1-3); then harden the regex.
5. **Prompt-injection posture**: cap `audience` length, "output only prose," sanitize output for the rendering context (TB1-4).
6. **Supply chain**: sign+verify images (TB4-1), block builds on Trivy CVEs (TB4-4), pin deps (TB4-2).

*Residual risk after 1–4:* the service is still a public internet endpoint and will
always be a DoS *target* — but the cheap, high-leverage amplifiers (no-auth,
no-rate-limit, unbounded long-hold, unbounded-regex-work) are closed. What remains
is operator capacity sizing, which is a cost decision, not a defect.

---

## 10. Revision history

- **2026-11-02, advisor pass** — initial model (STRIDE, attack trees, ranked L×I). Two claims later falsified: subprocess-transport assumption (closed by code check — argv-only, text as file content) and "no per-subprocess timeout" (SCORER_TIMEOUT was already present).
- **2026-11-02, adversary pass** — source-grounded attack by a second reviewer. Corrections: digest-pinning does NOT protect the shipped k8s example (tracks `:latest`); egress is NOT pinned to the LLM endpoint (0.0.0.0/0 by design); /ping & /healthz parse no input (covert-channel premise dropped); ReDoS re-ranked 6→9 (quadratic `re.sub` is concrete). Additions: TB1-7a (MCP unbounded `max_rounds`), TB1-8 (502 detail leak), TB1-9 (ruleset 500), TB3-4a (memory-backed tmpfs), TB5-2 (teardown substring deletion), TB5-3 (IAM `Resource: "*"`).
- **2026-11-02, fixes shipped in the same PR** — TB1-7a (MCP clamp), TB1-8 (fixed 502 detail + server-side log), TB1-9 (ruleset errors → 503), TB5-2 (exact log-group deletion), TB5-3 (scoped IAM policy), AUTH_TOKEN passthrough + guidance in the deploy kit (§TB3-1). Remaining open, by design: rate limiting (operator platform), `/improve` overall deadline (product change), digest-pinning the k8s example (release process), ReDoS hardening in the vendored scorer (re-vendor cycle), RULESET_PATH validation (operator-surface).
- **2026-11-02, bundle-scorer review** — the iso-24495/asd-ste100/din-8581 bundles made the subprocess script bundle-selectable (TB5, TB5-1 updated: a bundle supplies executable code; trust boundary is the operator-set `RULESET_PATH`, same accepted-residual class as TB1-9; shipped bundles are CI-scanned repo files). TB4-4's "gate status unconfirmed" corrected: Trivy has been a blocking gate in ci.yml since it shipped. New: `tests/test_scorer_contract.py` pins the no-shell argv contract so the TB5-1 verification can fail.
