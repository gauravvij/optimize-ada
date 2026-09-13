#!/bin/bash
# L1L2 smoke test 2: bridge-level proof that the directives reach the
# composed systemPromptAppend. The [lever-debug] log line is printed
# synchronously when runTurn composes the append — BEFORE any API call —
# so we can POST a session, capture the log, and DELETE immediately
# with zero meaningful API spend.
set -u
export PATH=/tmp/node-v24.11.0-linux-x64/bin:$PATH
export $(grep -v '^#' /root/optimize_ada/.env | xargs)
export ANTHROPIC_MODEL=claude-haiku-4-5
export ADA_SELF_VERIFY=1
export ADA_ADAPTIVE_CONCISION=1
export ADA_LEVER_DEBUG=1
export PORT=8097
export WORKSPACE_ROOT=/tmp/ada-smoke-ws
export MAX_CONCURRENT_RUNS=3
LOG=/tmp/l1l2-smoke-bridge.log
mkdir -p "$WORKSPACE_ROOT"
cd /root/optimize_ada/eval/ada-runtime/ada

# start bridge fresh
nohup node agent/index.ts > "$LOG" 2>&1 &
BPID=$!
for i in $(seq 1 20); do
  curl -s -o /dev/null http://localhost:$PORT/ && break
  sleep 1
done
echo "bridge up (pid $BPID)"

post() { # $1 = prompt, $2 = label
  SID=$(curl -s -X POST http://localhost:$PORT/sessions \
    -H 'Content-Type: application/json' \
    -d "{\"prompt\": $(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$1"), \"cwd\": \"/tmp\"}" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('sessionId',''))")
  sleep 2   # let runTurn compose + log
  if [ -n "$SID" ]; then curl -s -X DELETE http://localhost:$PORT/sessions/$SID > /dev/null; fi
}

BULK='Transform /app/input.csv (1 million rows) to match /app/expected.csv exactly using keystroke-efficient Vim macros. Save your script as /app/apply_macros.vim.'
PLAIN='I just made some changes to my personal site and checked out master, but now I cannot find those changes. Please help me find them and merge them into master.'

post "$BULK" bulk
post "$PLAIN" plain
sleep 1
kill $BPID 2>/dev/null
echo "=== SMOKE LOG ==="
grep -c 'lever-debug' "$LOG" || true
echo "--- bulk append (first lever-debug block) ---"
awk '/lever-debug/{n++} n==1' "$LOG" | head -40
echo "--- plain append (second lever-debug block) ---"
awk '/lever-debug/{n++} n==2' "$LOG" | head -40
