#!/usr/bin/env bash
# Install independent, bounded literature discovery within the private factory.
# Live storefronts, human review, stock and final QA remain untouched.
set -euo pipefail
umask 077
test "$(id -un)" = githubops && test "$(id -u)" -ne 0
test "$#" -eq 1
src="$1"
test -f "$src" && test ! -L "$src"
base="$HOME/factory-runtime"
root="$base/private/autonomous-product-cycle"
ops="$base/operations/production-instructions"
py="$base/.venv/bin/python"
main_agent="$ops/stage2-research.py"
dest="$ops/stage2-literature-scout.py"
marker="SAEIT_FACTORY_STAGE2_SOURCE_DISCOVERY_V1"
test -d "$ops" && test ! -L "$ops"
test -d "$root/production-instructions/stage-02/inbox"
test -f "$main_agent" && test ! -L "$main_agent"
test -x "$py"
command -v flock >/dev/null
exec 8>"$ops/.stage2-scout-deploy.lock"
flock -w 40 8
back="$base/operations/backups/stage2-scout-$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 700 "$back"
crontab -l > "$back/crontab.before"
chmod 600 "$back/crontab.before"
if test -e "$dest"; then
  test ! -L "$dest"
  cp -p "$dest" "$back/scout.before.py"
fi
"$py" -B -c 'import ast,sys;ast.parse(open(sys.argv[1],encoding="utf8").read())' "$src"
temp="$(mktemp "$ops/.scout.XXXXXX")"
install -m 600 "$src" "$temp"
mv -f "$temp" "$dest"
chmod 600 "$dest"

# Real outside-source retrieval; fail-closed source filtering and traceable
# abstract claims. Up to 100 remaining P0 orders in this first run.
timeout 650s "$py" -B "$dest" --factory-private "$root" \
    --stage2-program "$main_agent" --batch 50 --workers 2 --query-burst 3
# Promote ONLY independently source-linked dossier work that passes stage 2's
# normal gates, not raw bibliographic candidates.
timeout 120s "$py" -B "$main_agent" --factory-private "$root" --batch 250

cron='*/2 * * * * /usr/bin/flock -n /home/githubops/factory-runtime/operations/production-instructions/.stage2-scout-minute.lock /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/stage2-literature-scout.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --stage2-program /home/githubops/factory-runtime/operations/production-instructions/stage2-research.py --batch 12 --workers 1 --query-burst 2 >> /home/githubops/factory-runtime/operations/production-instructions/stage2-literature-scout.log 2>&1 && /usr/bin/timeout 120s /home/githubops/factory-runtime/.venv/bin/python -B /home/githubops/factory-runtime/operations/production-instructions/stage2-research.py --factory-private /home/githubops/factory-runtime/private/autonomous-product-cycle --batch 250 >> /home/githubops/factory-runtime/operations/production-instructions/stage2-literature-scout.log 2>&1 # SAEIT_FACTORY_STAGE2_SOURCE_DISCOVERY_V1'
if grep -Fq "$marker" "$back/crontab.before"; then
  test "$(grep -Fc "$marker" "$back/crontab.before")" -eq 1
  if grep -Fxq "$cron" "$back/crontab.before"; then
    echo FACTORY_STAGE2_SCOUT_CRON=ALREADY_PRESENT
  else
    # Upgrade only this exact owned entry; preserve every unrelated job.
    awk -v marker="$marker" -v replacement="$cron" '
      index($0,marker) {print replacement; next} {print}
    ' "$back/crontab.before" | crontab -
    echo FACTORY_STAGE2_SCOUT_CRON=UPDATED
  fi
else
  { cat "$back/crontab.before"; printf '%s\n' "$cron"; } | crontab -
  echo FACTORY_STAGE2_SCOUT_CRON=INSTALLED
fi
test "$(crontab -l | grep -Fc "$marker")" -eq 1
"$py" -B - "$root/production-instructions" <<'PY'
import collections,json,sys
from pathlib import Path
area=Path(sys.argv[1])
idx=json.loads((area/"owner-agri200-p0-index.json").read_text())
stat=json.loads((area/"stage-02/literature-scout-status.json").read_text())
source_dir=area/"stage-02/source-evidence"
work_dir=area/"stage-02/literature-candidates"
brief_dir=area/"stage-02/research-needed"
stage3_dir=area/"stage-03/inbox"
num_source=0; num_candidate=0; num_research=0; num_handoff=0
tracked_gaps={
    "under_four_topic_relevant_article_abstracts",
    "insufficient_independent_publishers_or_domains",
    "missing_bilingual_scope",
    "duplicate_indexed_abstract_claims",
    "fifth_distinct_verbatim_claim_unavailable",
    "additional_provenance_or_validation_review",
}
gap_counts=collections.Counter()
for n,w in enumerate(idx["order_ids_ranked"],1):
    topic="AGRI-%03d"%n
    name=w+"--r001.json"
    if (source_dir/(topic+"--r001.json")).is_file(): num_source+=1
    candidate_file=work_dir/(topic+"--r001.json")
    if candidate_file.is_file():
        num_candidate+=1
        if not (source_dir/(topic+"--r001.json")).is_file():
            try:
                candidate=json.loads(candidate_file.read_text())
                reason=candidate.get("evidence_gap_reason")
                if reason in tracked_gaps:
                    gap_counts[reason]+=1
            except (OSError,ValueError,TypeError):
                pass
    if (brief_dir/name).is_file(): num_research+=1
    if (stage3_dir/name).is_file(): num_handoff+=1
assert stat["sites_changed"] is False
assert stat["human_specialist_reviews_completed"]==0
assert type(stat["attempted_this_run"]) is int and 0<=stat["attempted_this_run"]<=200
assert num_source>=3, "Original three vetted sources missing"
assert num_handoff>=3, "Stage 2 pilot lost"
assert num_source+num_candidate>=3+stat["attempted_this_run"]-stat["previously_seeded"]-stat["external_provider_unavailable"]-stat.get("requests_skipped_due_to_provider_cooldown",0)
print("FACTORY_STAGE2_SCOUT_P0_SOURCE_PACKETS="+str(num_source))
print("FACTORY_STAGE2_SCOUT_P0_BIBLIOGRAPHIC_WORKPAPERS="+str(num_candidate))
print("FACTORY_STAGE2_SCOUT_P0_MISSING_SOURCE_BRIEFS="+str(num_research))
print("FACTORY_STAGE2_SCOUT_P0_STAGE3_DOSSIERS="+str(num_handoff))
for gap in sorted(tracked_gaps):
    print("FACTORY_STAGE2_SCOUT_P0_EVIDENCE_GAP_"+
          gap.upper()+"="+str(gap_counts[gap]))
print("FACTORY_STAGE2_SCOUT_P0_ATTEMPTED_THIS_RUN="+str(stat["attempted_this_run"]))
print("FACTORY_STAGE2_SCOUT_PROVIDER_ERRORS="+str(stat["external_provider_unavailable"]))
print("FACTORY_STAGE2_SCOUT_PROVIDER_COOLDOWN_SKIPPED="+str(stat.get("requests_skipped_due_to_provider_cooldown",0)))
print("FACTORY_STAGE2_SCOUT_INDEPENDENT_EXPERT_APPROVALS=0")
print("FACTORY_STAGE2_SCOUT_SITE_PUBLICATIONS=0")
PY
echo FACTORY_STAGE2_SCOUT_DEPLOY_BACKUP="$back"
