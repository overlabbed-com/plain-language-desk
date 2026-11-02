# Deploying plain-language-desk to Amazon Bedrock AgentCore Runtime

The same image that ships to GHCR runs on AgentCore unchanged: it listens on
8080, answers the runtime's `/ping` probe, and speaks plain JSON over HTTP.
Verified end to end in eu-west-2 on 2026-11-02 (see the smoke suite below).

## Deploy

`MODE=test` (default) names everything under `plain_language_desk_test` and is
what `teardown.sh` deletes freely. `MODE=prod` names it under
`plain_language_desk`, tags `env=prod`, and is meant to stay up — `teardown.sh`
refuses prod-named resources unless `FORCE=1`.

```sh
export MODE=prod                            # or test (default)
export ACCOUNT_ID=123456789012 REGION=eu-west-2   # your account, an AgentCore region
export IMAGE_URI=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/plain-language-desk:<tag>   # arm64
export CREATE_ROLE=1 CREATE_ECR=1           # role + ECR repo created if absent
# inference backend (optional — omit for deterministic /score only):
export INFERENCE_BASE_URL=https://bedrock-runtime.eu-west-2.amazonaws.com/openai/v1
export INFERENCE_MODEL=openai.gpt-oss-20b-1:0
export INFERENCE_API_KEY=<bedrock api key>
export INFERENCE_EXTRA_JSON='{"reasoning_effort":"low"}'
./deploy.sh        # prints PLD_SCORE_RUNTIME / PLD_IMPROVE_RUNTIME ids
```

## Test (the demonstrable proof)

```sh
# locally, against a running container:
./smoke.py --local http://localhost:8080
# through AgentCore (two runtimes: /score and /improve):
./smoke.py --runtime-score arn:...:runtime/<id-score> \
           --runtime-improve arn:...:runtime/<id-improve> \
           --region eu-west-2
```

Every test prints PASS/FAIL with observed values; the JSON report is the artifact.

## Lessons learned (2026-11-02, eu-west-2, a single AWS account)

1. **AgentCore Runtime is arm64-only** (at least eu-west-2). The release image
   must be multi-arch; the publish workflow now builds
   `linux/amd64,linux/arm64`. An amd64-only image fails `create-agent-runtime`
   with `Architecture incompatible … Supported platforms: [arm64]`.
2. **One route per runtime.** An AgentCore HTTP runtime forwards every invoke
   to the single configured `path`, so `/score` and `/improve` need one
   runtime each (deploy.sh creates both).
3. **`--cli-binary-format raw-in-base64-out` is required** when invoking with
   the AWS CLI. With the default blob format the JSON payload arrives mangled
   and the service answers 400 (FastAPI malformed-JSON, visible in runtime logs
   as `POST /score 400` while `/ping` stays 200).
4. **Runtime names are `[a-zA-Z][a-zA-Z0-9_]{0,47}`** — no hyphens. Session
   ids must be ≥ 32 characters.
5. **The runtime role needs only ECR read + CloudWatch logs writes**
   (iam-permissions.json). Nothing else. AgentCore auto-creates a log group
   named `/aws/bedrock-agentcore/runtimes/<id>-DEFAULT` that outlives the
   runtime — teardown.sh removes it.
6. **Bedrock as the inference backend.** The service speaks one wire protocol
   (OpenAI chat-completions), and Bedrock serves one natively:
   `INFERENCE_BASE_URL=https://bedrock-runtime.<region>.amazonaws.com/openai/v1`.
   Auth is a **Bedrock API key** — mint one with
   `aws iam create-service-specific-credential --service-name bedrock.amazonaws.com`
   (scoped to `AmazonBedrockLimitedAccess`), delete it when done. Max 2 such
   credentials per user.
7. **Model choice on bedrock-runtime (eu-west-2, 2026-11-02):** models must
   support the Chat Completions API on that endpoint. `openai.gpt-oss-20b-1:0`
   and `openai.gpt-oss-120b-1:0` do; `amazon.nova-micro-v1:0` /
   `nova-lite` / `nova-pro` return *model doesn't exist or doesn't support
   this API*; `eu.`-prefixed inference-profile ids are rejected. Check
   [Models at a glance](https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html)
   before picking.
8. **Reasoning models leak their thinking into `content`** (gpt-oss on
   Bedrock returns `<reasoning>…</reasoning>` + the answer in one string).
   The service strips reasoning blocks before scoring, so the analysis
   channel is never graded as prose — and `INFERENCE_EXTRA_JSON='{"reasoning_effort":"low"}'`
   trims the token spend.
9. **Cost:** gpt-oss-20b on short prose costs fractions of a cent per improve
   round; an idle runtime with no active sessions bills nothing. Delete the
   runtime when done (`teardown.sh`).
10. **Deleting by bare runtime name returns a misleading `AccessDenied`.**
   `DeleteAgentRuntime` wants the FULL id (`name-XXXXXXXXXX`). CloudTrail
   showed the same user getting AccessDenied for bare names and success for
   full ids — across BOTH CLI versions (v2 succeeded with full ids three
   times; an early "v1 works, v2 is denied" read was confounded by which
   identifier each call carried). `teardown.sh` resolves name-prefix matches
   to full ids via `list-agent-runtimes` before deleting.
