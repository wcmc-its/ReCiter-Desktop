#!/usr/bin/env bash
# Show upstream ReCiter commits that touch parity-relevant paths since the
# SHA pinned in .upstream-ref. See PARITY.md for the file allowlist.
#
# Override the upstream repo path with RECITER_REPO=/path/to/reciter.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ref_file="$here/.upstream-ref"
default_repo="$HOME/Dropbox/GitHub/ReCiter"
repo="${RECITER_REPO:-$default_repo}"

if [[ ! -f "$ref_file" ]]; then
  echo "error: $ref_file not found" >&2
  exit 1
fi

if [[ ! -d "$repo/.git" ]]; then
  echo "error: $repo is not a git repo (set RECITER_REPO to override)" >&2
  exit 1
fi

pinned="$(awk '$1 == "ReCiter" {print $2}' "$ref_file")"
if [[ -z "$pinned" ]]; then
  echo "error: no ReCiter SHA in $ref_file" >&2
  exit 1
fi

# Paths in upstream ReCiter that map to mirrored Desktop files.
# Keep in sync with PARITY.md's "Mirrored slice" table.
paths=(
  'src/main/resources/application.properties'
  'src/main/java/reciter/algorithm/cluster/article/retrieval/'
  'src/main/java/reciter/xml/retriever/pubmed/'
  'src/main/java/reciter/pubmed/'
  'src/main/java/reciter/algorithm/evidence/'
  'src/main/java/reciter/algorithm/article/score/'
  'src/main/java/reciter/algorithm/util/ArticleTranslator.java'
  'src/main/java/reciter/algorithm/cluster/ReCiterCluster.java'
  'src/main/java/reciter/engine/'
  'src/main/java/reciter/model/article/'
)

cd "$repo"

if ! git cat-file -e "$pinned^{commit}" 2>/dev/null; then
  echo "error: pinned SHA $pinned not found in $repo (run git fetch?)" >&2
  exit 1
fi

upstream_head="$(git rev-parse HEAD)"

echo "Upstream:   $repo"
echo "Pinned at:  $pinned"
echo "Upstream HEAD: $upstream_head"
echo

if [[ "$pinned" == "$upstream_head" ]]; then
  echo "Pin is at upstream HEAD. No drift possible."
  exit 0
fi

range="$pinned..HEAD"
echo "Commits in $range touching mirrored paths:"
echo

count="$(git log --oneline "$range" -- "${paths[@]}" | wc -l | tr -d ' ')"
if [[ "$count" == "0" ]]; then
  echo "  (none — pin is current for the mirrored slice)"
  exit 0
fi

git log --oneline "$range" -- "${paths[@]}"
echo
echo "--- Diff stat ---"
git diff --stat "$range" -- "${paths[@]}"
echo
echo "Review each commit and either:"
echo "  1. Port the change into Desktop, then bump $ref_file"
echo "  2. Mark it N/A in PARITY.md's changelog and bump $ref_file"
