#!/usr/bin/env bash
# Execute exactly one of the three approved, tenant-isolated agent workflows.
# This script does not touch website or factory data directly; each target owns its guardrails.
set -euo pipefail

approved=(
  vps-master-agent-activate.yml
  mpw-all-agents-private-activation.yml
  zomorod-site-agent-cycle.yml
)
if [[ "${1:-}" == "--selftest" ]]; then
  [[ "${#approved[@]}" -eq 3 ]]
  printf 'APPROVED_THREE_AGENT_WORKFLOWS=%s\n' "${approved[*]}"
  exit 0
fi
[[ "${1:-}" == "--execute" && "$#" -eq 2 ]] || { echo "INVALID_INVOCATION" >&2; exit 2; }
target="$2"
case "$target" in
  vps-master-agent-activate.yml|mpw-all-agents-private-activation.yml|zomorod-site-agent-cycle.yml) ;;
  *) echo "UNAPPROVED_AGENT_WORKFLOW" >&2; exit 3 ;;
esac
[[ "${GITHUB_REPOSITORY:-}" == "mojtabarozegar11-ship-it/Saeit" ]] || { echo "WRONG_REPOSITORY" >&2; exit 4; }
[[ -n "${GH_TOKEN:-}" ]] || { echo "GITHUB_ACTIONS_TOKEN_MISSING" >&2; exit 5; }
command -v gh >/dev/null
command -v jq >/dev/null

root="/repos/$GITHUB_REPOSITORY/actions"
workflow="$root/workflows/$target"
runs="$workflow/runs?event=workflow_dispatch&branch=main&per_page=10"
state="$(gh api "$workflow" --jq '.state')"
[[ "$state" == active ]] || { echo "TARGET_WORKFLOW_NOT_ACTIVE: $target" >&2; exit 6; }

baseline="$(gh api "$runs" | jq -er '[.workflow_runs[].id] | max // 0')"
echo "TARGET=$target BASELINE=$baseline"
gh workflow run "$target" --ref main
echo "DISPATCH_SUBMITTED=$target"

run_id=""
for attempt in $(seq 1 24); do
  response="$(gh api "$runs")"
  # Refuse to attribute somebody else's concurrent run to this invocation.
  mapfile -t new_ids < <(printf '%s' "$response" | jq -r --argjson base "$baseline" '.workflow_runs[] | select(.id > $base and .event == "workflow_dispatch" and .head_branch == "main") | .id')
  if [[ "${#new_ids[@]}" -gt 1 ]]; then
    echo "AMBIGUOUS_CONCURRENT_DISPATCH: $target" >&2
    exit 7
  fi
  if [[ "${#new_ids[@]}" -eq 1 ]]; then run_id="${new_ids[0]}"; break; fi
  sleep 5
done
[[ -n "$run_id" ]] || { echo "DISPATCH_RUN_NOT_OBSERVED: $target" >&2; exit 8; }
echo "DISPATCH_RUN_URL=https://github.com/$GITHUB_REPOSITORY/actions/runs/$run_id"

for attempt in $(seq 1 96); do
  state_json="$(gh api "$root/runs/$run_id")"
  status="$(printf '%s' "$state_json" | jq -r '.status')"
  conclusion="$(printf '%s' "$state_json" | jq -r '.conclusion // ""')"
  if [[ "$status" == completed ]]; then
    echo "AGENT_WORKFLOW=$target RESULT=$conclusion"
    [[ "$conclusion" == success ]] || { echo "AGENT_EXECUTION_NOT_VERIFIED: $target $run_id" >&2; exit 9; }
    echo "AGENT_GROUP_EXECUTION_VERIFIED=$target"
    exit 0
  fi
  sleep 12
done
echo "AGENT_EXECUTION_TIMED_OUT: $target $run_id" >&2
exit 10
