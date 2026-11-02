# Live test report: plain-language-desk on AWS Bedrock + AgentCore

**2026-11-02 · eu-west-2 · account 530456407074 · image `v1.0.0-bedrock-test`
(digest `sha256:c30ae16e…`, arm64 build of this branch)**

The service was deployed twice and the same 8-check suite was run against both
surfaces, with Amazon Bedrock (`openai.gpt-oss-20b-1:0`, via the
OpenAI-compatible endpoint and a Bedrock API key) as the inference engine:

1. **Local container** — `docker run` with `INFERENCE_BASE_URL` pointed at
   `bedrock-runtime.eu-west-2.amazonaws.com/openai/v1`.
2. **AgentCore Runtime** — two runtimes (`…_score`, `…_improve`) created by
   `deploy/agentcore/deploy.sh`, inference env injected at creation.

## Results — identical verdicts on both surfaces

```
PASS  health.ping: GET /ping -> 200 {'ok': True}                      (local)
PASS  score.deterministic_and_discriminating: BAD twice -> 62==62
      findings equal=True; clean text -> 100 > 62                     (both)
PASS  score.shape_and_ruleset_echo: version=WPS/1.1
      ruleset=faa-plain-language@1.0.0 bar=80 findings=8              (both)
PASS  score.machine_format_free: prose 62 == prose+code+table 62      (both)
PASS  improve.minimal_mode_improves_monotonically: 62 -> 100 in
      1-2 round(s); improved=True; echo matches score; clean text     (both)
PASS  improve.full_mode_improves_monotonically: 62 -> 98-100 in
      1 round(s); improved=True; echo matches score; clean text       (both)
PASS  surfaces.ruleset_echo_consistent: faa-plain-language@1.0.0 @80  (both)
PASS  mcp.score_prose_roundtrip: initialize 200 (session id True),
      tools/call 200, result contains score: True                     (local)
```

Full run: 8/8 local (`smoke.py --local`), 8/8 through AgentCore
(`smoke.py --runtime-score … --runtime-improve …`). The same prose scores 62
with 8 findings on both surfaces and improves to 98-100 through the real
Bedrock round-trip, with the reasoning model's analysis channel stripped
before scoring.

## What the suite proves

- **Determinism:** identical input → identical score + findings, twice.
- **Discrimination:** clean prose scores 100 where passive/archaic prose
  scores 62 — the check can fail.
- **Ruleset identity:** every response carries `WPS/1.1`,
  `faa-plain-language@1.0.0`, bar 80.
- **Machine-format immunity:** appending a code fence + table to the prose
  does not move the score.
- **The improve loop:** monotonic (`final_score > original_score`), honors
  the round cap, returns the best-scoring text, and echoes the same ruleset
  as the score endpoint.
- **Engine normalization:** gpt-oss's reasoning block never reaches the
  scorer (new `strip_reasoning`, covered by an e2e test).
- **MCP surface:** native streamable-HTTP MCP initialize + `score_prose`
  round-trip works (local; AgentCore HTTP runtimes route one path each).

## Cost

gpt-oss-20b on short prose: the whole campaign (dozens of invocations across
wire probes, local runs, and the AgentCore suite) consumed well under 100K
tokens — fractions of a cent. Idle AgentCore runtimes with no active sessions
bill nothing; all test resources were deleted after the run.

## Reproduce

See [deploy/agentcore/README.md](../deploy/agentcore/README.md) — deploy,
invoke, smoke, teardown, and the nine lessons learned from this run
(arm64-only runtime, one route per runtime, `raw-in-base64-out`, runtime-name
charset, minimal role, Bedrock API key minting, model support matrix,
reasoning-strip, cost shape).
