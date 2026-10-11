#!/usr/bin/env bash
# Usage: scope.sh <paths-regex> <git-range>. Prints run=true when a changed file matches (an empty regex matches
# everything), run=false otherwise. A git or regex error exits non-zero, so the lane fails instead of skipping.
set -euo pipefail
files=$(git diff --name-only "$2")
matched=0
grep -qE "$1" <<<"$files" || matched=$?
case $matched in
  0) echo run=true ;;
  1) echo run=false ;;
  *) exit "$matched" ;;
esac
