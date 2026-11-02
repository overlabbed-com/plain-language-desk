#!/usr/bin/env bash
# Invoke an AgentCore HTTP runtime. The raw-in-base64-out flag is REQUIRED:
# with the CLI's default blob format the JSON payload arrives mangled and the
# service answers 400 (lesson learned 2026-11-02).
# usage: invoke.sh <runtime-arn> <region> '<json-payload>'
set -euo pipefail
ARN="$1"; REGION="$2"; PAYLOAD="$3"
SESSION="pld-$(date +%s)-$RANDOM-0000000000000000"   # >=32 chars, AgentCore requirement
exec aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn "$ARN" \
  --runtime-session-id "$SESSION" \
  --content-type application/json \
  --cli-binary-format raw-in-base64-out \
  --payload "$PAYLOAD" \
  /dev/stdout --region "$REGION" --no-cli-pager
