#!/usr/bin/env bash
# Remove the runtimes deploy.sh created (matched by NAME_BASE prefix), plus the
# role when CREATE_ROLE=1 was used, plus the AgentCore log groups.
#
# Safety: a NAME_BASE without "test" is treated as prod and refused unless
# FORCE=1. Set NAME_BASE to the deploy.sh value; MODE must match too.
#
# DeleteAgentRuntime takes the FULL runtime id (name-suffix). Passing the bare
# name returns a misleading AccessDenied (lesson 10 in the README) — this
# script resolves names to full ids before deleting.
set -uo pipefail
AWS="aws"
$AWS --version | grep -q "aws-cli/2" || { echo "AWS CLI v2 required"; exit 1; }
: "${REGION:?}"; MODE="${MODE:-test}"
NAME_BASE="${NAME_BASE:-plain_language_desk$([ "$MODE" = test ] && echo _test)}"
if [[ "$NAME_BASE" != *test* && "${FORCE:-0}" != "1" ]]; then
  echo "refusing: NAME_BASE '$NAME_BASE' looks like a prod deploy; set FORCE=1 to delete it" >&2
  exit 1
fi
echo "deleting runtimes with name base: $NAME_BASE (env=$MODE)"
# Resolve every live runtime whose id starts with the name base, then delete
# by full id — never by bare name.
IDS=$($AWS bedrock-agentcore-control list-agent-runtimes --region "$REGION" --no-cli-pager --output json 2>/dev/null \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('agentRuntimes') or d.get('items') or []
print('\n'.join(i['agentRuntimeId'] for i in items if i['agentRuntimeId'].startswith('$NAME_BASE')))")
if [ -z "$IDS" ]; then echo "no runtimes found for $NAME_BASE"; else
  for ID in $IDS; do
    if OUT=$($AWS bedrock-agentcore-control delete-agent-runtime --agent-runtime-id "$ID" \
      --region "$REGION" --no-cli-pager 2>&1); then
      echo "delete requested: $ID ($(echo "$OUT" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status","?"))' 2>/dev/null || echo '?'))"
    else
      echo "DELETE FAILED for $ID: $OUT"
    fi
  done
fi
if [ "${CREATE_ROLE:-0}" = "1" ]; then
  ROLE_NAME="${ROLE_NAME:-${NAME_BASE}-role}"
  $AWS iam delete-role-policy --role-name "$ROLE_NAME" --policy-name ecr-logs-minimal 2>/dev/null
  $AWS iam delete-role --role-name "$ROLE_NAME" 2>/dev/null && echo "deleted role $ROLE_NAME" || echo "role $ROLE_NAME absent"
fi
# The CloudWatch log group AgentCore auto-creates outlives the runtime. Delete
# ONLY the exact groups of the runtimes resolved above (an exact-name match —
# a substring match once wiped shared log groups that merely contained the
# name base; THREAT-MODEL TB5-2).
for ID in $IDS; do
  LG="/aws/bedrock-agentcore/runtimes/$ID-DEFAULT"
  $AWS logs delete-log-group --log-group-name "$LG" --region "$REGION" 2>/dev/null \
    && echo "deleted $LG" || echo "log group $LG absent or already gone"
done
echo "teardown done — verify: list-agent-runtimes returns none for $NAME_BASE"
