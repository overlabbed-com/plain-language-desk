# Plain-Language Desk

Prose in, plain-language prose out. One service scores prose against the FAA
standard for plain language and returns it rewritten to the bar. You choose
the engine. Any tool that speaks HTTP or MCP can call it, and it runs anywhere
a container runs. The image is public on GitHub's container registry, so the
pull below needs no credentials.

## Quick start

```sh
docker run --rm -p 8080:8080 \
  -e INFERENCE_BASE_URL=https://your-gateway.example/v1 \
  -e INFERENCE_MODEL=your-model \
  -e INFERENCE_API_KEY=$TOKEN \
  ghcr.io/overlabbed-com/plain-language-desk:latest

curl -s localhost:8080/score -H 'Content-Type: application/json' \
  -d '{"text":"It shall be noted that the aforementioned provisions are required."}'
```

`POST /score` grades the text and returns findings with a number. It changes
nothing. `POST /improve` returns the prose rewritten to the bar:

```sh
curl -s localhost:8080/improve -H 'Content-Type: application/json' \
  -d '{"text":"…","mode":"full","audience":"ship engineers"}'
```

`mode=minimal` fixes the violations the scorer names, and nothing else.
`mode=full` rewrites for style. Both run the same loop: score, rewrite with
the findings as feedback, re-score. The loop is monotonic — the response
carries the best score seen — and stops at the bar, the round cap, or when a
rewrite stops improving.

## Configuration

| Variable | Meaning | Default |
|----------|---------|---------|
| `INFERENCE_BASE_URL` | OpenAI-compatible chat-completions endpoint | none — `/improve` returns 503 without it |
| `INFERENCE_MODEL` | Model name the endpoint serves | none |
| `INFERENCE_API_KEY` | Bearer key, if the endpoint wants one | empty |
| `INFERENCE_EXTRA_JSON` | Raw JSON merged into each request body, for engine-specific kwargs | empty |
| `INFERENCE_TIMEOUT` / `INFERENCE_MAX_RETRIES` | Per-call timeout and retry count | 120 s / 2 |
| `RULESET_PATH` | A ruleset bundle directory | the shipped FAA bundle |
| `BAR` | Pass bar | 80 (bundle value) |
| `MAX_ROUNDS` | Default round cap for `/improve` | 3 (request can set 1–5) |
| `AUTH_TOKEN` | Set it and every path but `/healthz` needs `Authorization: Bearer <token>` | unset — open |
| `PORT` | Listen port | 8080 |

## Surfaces

One process serves both. The HTTP API lives at `/score`, `/improve`,
`/healthz`, and `/ping`. The MCP surface lives at `/mcp` with the tools
`score_prose` and `improve_prose` — DSH, Claude Code, omp, pi, and any other
MCP client call it directly. No harness-specific code exists in the service.

The same container deploys to Amazon Bedrock AgentCore Runtime unchanged: it
listens on port 8080 (`PORT` overrides it), answers `/ping` for the runtime's
health probe, and speaks plain JSON over HTTP — no cloud software development
kit anywhere.

## Ruleset bundles

The standard is data, not code. A bundle is a directory: `RULESET.md` (the
standard), `ruleset.json` (identity, bar, version), the two rewrite prompts,
and `golden/` fixtures with pinned scores that the test suite replays. The
FAA bundle (`faa-plain-language@1.0.0`, from FAA Order 1000.36A and the federal
plain-language handbook) ships inside the package. Point `RULESET_PATH` at a
work-tuned bundle to run a different standard — a new bundle, not a fork.

Every response reports `ruleset` (id@version) and the `bar` that scored the
text. Code blocks, tables, and front matter never cost points: the scorer
strips machine-necessary formatting before it reads a word.

## Hardening

The container image is the deliverable, so its posture is checked, not
promised — CI fails the build if any proof fails:

- The runtime image has no shell; `docker run … sh` refuses.
- It runs as a fixed non-root user with all capabilities dropped and a
  read-only root filesystem; the health check and a full score call pass
  under exactly that posture.
- Both base images are pinned by digest; dependencies install from the
  package metadata, with no build tools in the final image.
- Every build ships a software bill of materials, and the scanner fails on
  critical or high findings.
- Port and health-check path env-configurable (`PORT`, `/ping` compatible) —
  the AgentCore Runtime contract, and any kubelet or load balancer probe, out
  of the box.
- No secrets live in layers: configuration arrives at runtime by environment,
  and nothing in the image reads it at build time.

The digest pins age by design: refresh them deliberately — rebuild, scan,
re-pin — in one commit.

## Provenance

The scorer decides every score; the engine only rewrites. The rules it applies
live in this repo: `RULESET.md` carries the rule table with its FAA citations
(FAA Order 1000.36A, the federal plain-language handbook) — that bundle is the
checkable source of truth for what gets deducted and why, and the goldens
replay its behavior.

The scorer code is vendored from a private writing-standard tool (WPS/1.1,
2026-10-31). It is pinned, not just claimed: `tests/test_parity.py` fails if
the vendored file's sha256 (`2329248ae069…`) changes, and replays golden
fixtures the original generated. The honest limit: the original is a
single-machine artifact — the hash proves the vendored copy has not drifted,
but nothing public lets you diff it against the source it names. The rules,
citations, and goldens are in this repo; argue with those.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest tests -q
.venv/bin/python -m plain_language_desk     # serve on :8080
```

## Deploying

Amazon Bedrock AgentCore Runtime is a first-class target:
[deploy/agentcore/](deploy/agentcore/README.md) ships the deploy/test kit and
the lessons learned from the live eu-west-2 run.

`deploy/k8s/` ships a kustomize tree — Deployment, Service, ServiceAccount,
ConfigMap, and a deny-by-default NetworkPolicy — mirroring the homelab
log-triage pattern. `kustomize build deploy/k8s | kubectl apply -f -` after
setting `INFERENCE_BASE_URL`/`INFERENCE_MODEL` in `configmap.yaml`. CI
publishes the image to `ghcr.io/overlabbed-com/plain-language-desk` on every
merge to `main` (pin by digest in production).
