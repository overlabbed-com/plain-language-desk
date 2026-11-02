#!/usr/bin/env bash
# Deploy plain-language-desk to Amazon Bedrock AgentCore Runtime.
# Two runtimes share one image and one role: /score and /improve are separate
# routes, and an AgentCore HTTP runtime forwards every invoke to ONE path.
#
# MODE=test (default)  name base plain_language_desk_test, env=test tag;
#                      teardown.sh deletes it freely.
# MODE=prod            name base plain_language_desk, env=prod tag; meant to
#                      stay up. teardown.sh refuses prod names unless FORCE=1.
#
# Required env:
#   ACCOUNT_ID    AWS account number
#   REGION        region (AgentCore Runtime: arm64 microVMs; eu-west-2 verified)
#   IMAGE_URI     <account>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>  (arm64!)
#   RUNTIME_ROLE_ARN  existing role, or set CREATE_ROLE=1 to create the minimal one
# Optional env:
#   MODE          test (default) | prod
#   NAME_BASE     override the name base (default per MODE, see above)
#   CREATE_ECR=1  create the ECR repository named in IMAGE_URI if absent
# Inference backend (omit for deterministic-only /score):
#   INFERENCE_BASE_URL  e.g. https://bedrock-runtime.eu-west-2.amazonaws.com/openai/v1
#   INFERENCE_MODEL     e.g. openai.gpt-oss-20b-1:0
#   INFERENCE_API_KEY   Bedrock API key (IAM service-specific credential)
#   INFERENCE_EXTRA_JSON  e.g. {"reasoning_effort":"low"}
# AWS CLI v2 >= 2.39 required (port/path in protocol-configuration).
set -euo pipefail

: "${ACCOUNT_ID:?}" "${REGION:?}" "${IMAGE_URI:?}"
MODE="${MODE:-test}"
case "$MODE" in test|prod) ;; *) echo "MODE must be test or prod" >&2; exit 1;; esac
DEFAULT_BASE="plain_language_desk"
[ "$MODE" = "test" ] && DEFAULT_BASE="plain_language_desk_test"
NAME_BASE="${NAME_BASE:-$DEFAULT_BASE}"
AWS="aws"
$AWS --version | grep -q "aws-cli/2" || { echo "AWS CLI v2 required"; exit 1; }

ENV_ARGS=()
if [ -n "${INFERENCE_BASE_URL:-}" ]; then
  # JSON form: the shorthand key=value map cannot carry values containing
  # commas/quotes/equals (e.g. INFERENCE_EXTRA_JSON={"reasoning_effort":"low"}).
  ENV_JSON=$(python3 -c 'import json,os;print(json.dumps({k:os.environ.get(k,"") for k in ["INFERENCE_BASE_URL","INFERENCE_MODEL","INFERENCE_API_KEY","INFERENCE_EXTRA_JSON"]}))')
  ENV_ARGS+=(--environment-variables "$ENV_JSON")
fi

if [ "${CREATE_ECR:-0}" = "1" ]; then
  ECR_REPO="${IMAGE_URI##*/}"; ECR_REPO="${ECR_REPO%%:*}"
  $AWS ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" >/dev/null 2>&1 \
    || $AWS ecr create-repository --repository-name "$ECR_REPO" --region "$REGION" >/dev/null \
    && echo "ECR repository ready: $ECR_REPO"
fi

if [ "${CREATE_ROLE:-0}" = "1" ]; then
  ROLE_NAME="${ROLE_NAME:-${NAME_BASE}-role}"
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document file://"$(dirname "$0")"/iam-trust.json 2>/dev/null || true
  aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name ecr-logs-minimal \
    --policy-document file://"$(dirname "$0")"/iam-permissions.json
  RUNTIME_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
fi
: "${RUNTIME_ROLE_ARN:?set RUNTIME_ROLE_ARN or CREATE_ROLE=1}"

create_runtime() { # $1 suffix, $2 path
  local ID="${NAME_BASE}_${1}"
  $AWS bedrock-agentcore-control create-agent-runtime \
    --agent-runtime-name "$ID" \
    --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"$IMAGE_URI\"}}" \
    --role-arn "$RUNTIME_ROLE_ARN" \
    --network-configuration '{"networkMode":"PUBLIC"}' \
    --protocol-configuration "{\"serverProtocol\":\"HTTP\",\"port\":8080,\"path\":\"$2\"}" \
    --description "plain-language-desk ($MODE)" \
    --tags Key=project,Value=plain-language-desk Key=env,Value="$MODE" \
    ${ENV_ARGS[@]+"${ENV_ARGS[@]}"} \
    --region "$REGION" --output json --no-cli-pager \
    | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["agentRuntimeId"])'
}

wait_ready() { # $1 runtime id
  for _ in $(seq 1 40); do
    ST=$($AWS bedrock-agentcore-control get-agent-runtime --agent-runtime-id "$1" \
      --region "$REGION" --output json --no-cli-pager 2>/dev/null \
      | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status","?"))' 2>/dev/null || echo "?")
    [ "$ST" = "READY" ] && { echo "$1 READY"; return 0; }
    [ "$ST" = "CREATE_FAILED" ] && { echo "$1 CREATE_FAILED"; return 1; }
    sleep 15
  done
  echo "$1 not READY after timeout"; return 1
}

SCORE_ID=$(create_runtime score /score)
IMPROVE_ID=$(create_runtime improve /improve)
wait_ready "$SCORE_ID"
wait_ready "$IMPROVE_ID"
echo "MODE=$MODE NAME_BASE=$NAME_BASE"
echo "export PLD_SCORE_RUNTIME=$SCORE_ID"
echo "export PLD_IMPROVE_RUNTIME=$IMPROVE_ID"
if [ "$MODE" = "test" ]; then
  echo "test deploy — when done: MODE=test NAME_BASE=$NAME_BASE ./teardown.sh"
else
  echo "prod deploy left running — verify with: ./smoke.py --runtime-score <score-arn> --runtime-improve <improve-arn>"
fi
