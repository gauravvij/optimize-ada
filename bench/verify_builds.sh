#!/usr/bin/env bash
# Recover the campaign's git history and check every build the records name.
#
# Runs the README's recipe in a temporary directory: clone github.com/rabbah/ada, fetch
# bench/ada-campaign.bundle on top, then assert each commit's agent tree
# (`git rev-parse <commit>:agent`) against the value the records give. Needs git and network.
#
#   bash bench/verify_builds.sh
set -euo pipefail
BUNDLE="$(cd "$(dirname "$0")" && pwd)/ada-campaign.bundle"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git clone -q https://github.com/rabbah/ada "$TMP/ada"
cd "$TMP/ada"
git bundle verify -q "$BUNDLE"
git fetch -q "$BUNDLE" 'refs/heads/*:refs/remotes/campaign/*' 'refs/tags/*:refs/tags/*'

fail=0
check() {  # commit, expected 12-char agent tree, description
  local got
  got=$(git rev-parse --short=12 "$1:agent" 2>/dev/null || echo missing)
  if [ "$got" = "$2" ]; then echo "PASS  $1  agent $got  $3"; else echo "FAIL  $1  agent $got, expected $2  $3"; fail=1; fi
}
check df0c537 6ec0446cfc7d "origin"
check 6672af8 7958654244eb "watchdog (T0.1); R3 and R7"
check 2e495bb 4267fee64dcc "time hints (T1.2); R4 and R8"
check 5f4c5c0 dab704de524a "shipped build"
check 1d82e56 dab704de524a "shipped build as measured in R9/R10"
check c6f917e dab704de524a "shipped build in the removed mirror workspace"
check ada-best-61pct-20260916 dab704de524a "tag of the shipped build (32f4754)"
check 9f2e34d 811a16e4a67e "P3 candidate, rejected"
check ada-final-59of81 3c5d1f1d32f9 "Phase A final build (08a8d5d)"

echo "6672af8 was committed at $(git log -1 --format=%cI 6672af8); R3 records it, under run ID 20260910T0728Z"
[ "$fail" = 0 ] && echo "ALL BUILDS RESOLVE" || echo "SOME BUILDS DO NOT RESOLVE"
exit "$fail"
