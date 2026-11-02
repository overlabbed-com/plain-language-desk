# Security policy

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Use GitHub's **private vulnerability reporting** on this repository
(Security tab → Report a vulnerability). If that is not available to you,
contact the maintainers through the org and we will set up a private channel.

Include: what you found, how you triggered it, the image digest you ran, and
your assessment of impact. A minimal reproduction is worth more than a long
essay.

## Scope

In scope:

- The service (`src/`): the HTTP and MCP surfaces, request handling, the
  scoring pipeline, and the improve loop.
- The published container image and its build (`.github/workflows/`,
  `Dockerfile`, dependency metadata).
- The deployment kits (`deploy/k8s/`, `deploy/agentcore/`) and the posture
  they document.

Out of scope:

- The inference backend you point the service at — its security is the
  operator's configuration, not this codebase. (What IS in scope: anything
  this service sends it, or fails to bound, that makes an attack on it easier.)
- Denial of service by means the operator's platform is responsible for
  bounding (ingress rate limits, pod limits) — though documented resource
  envelopes are in scope if they are misleading.
- Volumetric scanning of a public instance.

## What the service is, so you can assess it

Stateless: no database, no storage, no accounts, no sessions. Prose in, score
and optionally rewritten prose out. Optional bearer auth (`AUTH_TOKEN`);
`/healthz` and `/ping` stay open for probes regardless. Every score spawns a
local subprocess; every improve round calls the operator-configured LLM
endpoint with operator-configured credentials. Submitter prose is sent to that
endpoint and is never logged or persisted. The full model — trust boundaries,
ranked threats, accepted risks — lives in [`docs/THREAT-MODEL.md`](docs/THREAT-MODEL.md).

## Supported versions

The `main` branch and the latest release tag. Older tags get fixes on a
best-effort basis only — pin by digest and upgrade.
