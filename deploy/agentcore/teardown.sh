#!/usr/bin/env bash
# Remove everything deploy.sh created. Idempotent: ignores already-deleted.
set -uo pipefail
: "${REGION:?}"; NAME_BASE="${NAME_BASE:-plain_language_desk}"
for SUFFIX in score improve; do
  ID="${NAME_BASE}_${SUFFIX}"
  if OUT=$(aws bedrock-agentcore-control delete-agent-runtime --agent-runtime-id "$ID" \
    --region "$REGION" --no-cli-pager 2>&1); then
    echo "delete requested: $ID ($(echo "$OUT" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("status","?"))' 2>/dev/null || echo '?'))"
  else
    echo "DELETE FAILED for $ID: $OUT"
  fi
done
if [ "${CREATE_ROLE:-0}" = "1" ]; then
  ROLE_NAME="${ROLE_NAME:-${NAME_BASE}-role}"
  aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name ecr-logs-minimal 2>/dev/null \
    && aws iam delete-role --role-name "$ROLE_NAME" 2>/dev/null && echo "deleted role $ROLE_NAME" || echo "role $ROLE_NAME absent"
fi
# The CloudWatch log group AgentCore auto-creates outlives the runtime:
aws logs describe-log-groups --region "$REGION" --no-cli-pager --output json 2>/dev/null \
  | python3 -c 'import sys,json;[print(g["logGroupName"]) for g in json.load(sys.stdin).get("logGroups",[]) if "plain_language_desk" in g["logGroupName"]]' \
  | while read -r LG; do aws logs delete-log-group --log-group-name "$LG" --region "$REGION" && echo "deleted $LG"; done
echo "teardown done — verify: list-agent-runtimes returns none"
