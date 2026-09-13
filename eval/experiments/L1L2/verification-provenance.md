# L1L2 arm — post-run verification provenance (close-out audit)

Commands re-run at close-out (2025-09-03 cycle, after the v2 arm completed),
with captured output, so the treatment-reach and stats claims are reproducible
without re-deriving them from inline scripts.

## 1. Treatment reach (job `l1l2-arm-v2`, 60 trial dirs)

```
$ grep -l '\[lever-debug\]' /root/optimize_ada/eval/jobs/l1l2-arm-v2/*/agent/ada-bridge.log | wc -l
60
$ grep -l 'Self-verification requirement' /root/optimize_ada/eval/jobs/l1l2-arm-v2/*/agent/ada-bridge.log | wc -l
60
$ grep -l 'Operating-efficiency' /root/optimize_ada/eval/jobs/l1l2-arm-v2/large-scale-text-editing*/agent/ada-bridge.log | wc -l
4        # 4/4
$ grep -l 'Operating-efficiency' /root/optimize_ada/eval/jobs/l1l2-arm-v2/password-recovery*/agent/ada-bridge.log | wc -l
4        # 4/4
$ grep -l 'Operating-efficiency' /root/optimize_ada/eval/jobs/l1l2-arm-v2/*/agent/ada-bridge.log \
    | grep -v -e large-scale-text-editing -e password-recovery | wc -l
0        # 0/4 in all other 13 tasks
```

## 2. Gate implementation (lever-guidance.ts, md5 ccadffd9)

```
$ grep -n 'bulkVolume\|forensic\|concisionGateFires' eval/ada-runtime/ada/agent/lever-guidance.ts
73:  const bulkVolume = /million|thousand|large[- ]scale/.test(p);
75:  const forensicSearch = /forensic/.test(p) && /deleted/.test(p);
76:  return bulkVolume || forensicSearch;
```

Gate = bulk-volume **OR** forensic-search (the forensic signal itself is the
AND of `/forensic/` and `/deleted/`). README/campaign-report wording corrected
to match at close-out (previously mis-stated as AND).

## 3. Paired stats recomputation (position-paired within task)

```
discordant: 13 | b_only: 7 | v_only: 6
mcnemar exact two-sided p: 1.0
cost pairs: 59 | delta mean: 0.02113 | CI95: [-0.00032, 0.04258]
```

Matches decision.json (p=1.0, +$0.0211, CI [−0.0003, +0.0426], 59 pairs).

## 4. Kill-criteria recomputation from raw JSONLs

```
MIXED candidate: 19/32  (B: 21)          -> KILL (bar 23)
fix-git+regex candidate: 4  (B: 7)       -> KILL (bar <=5)
large-scale: 2  (B: 0)                   -> PASS (bar >=2)
fix-code-vulnerability 4/4, git-leak-recovery 4/4, vulnerable-secret 4/4  -> PASS
suite: 32/60 = 0.533 (B 33/60 = 0.550)   -> PASS (bar >=0.424)
mean cost: $0.1248 (B $0.1042)           -> KILL (bar $0.1229)
total cost: $7.4895
```

## 5. mean_turns denominators

```
B mean_turns all-60: 20.333  | non-null n: 59  mean: 20.678
V mean_turns non-null n: 60  mean: 23.65
```

B's 20.3 = sum over 59 non-null trials ÷ 60 (one arm-B timeout trial has null
num_turns). Documented in README §4 and decision.json `mean_turns_note`.

## 6. md5 parity (source vs runtime)

```
ccadffd92bfb5cfad02ccf2dd1fae277  ada/agent/lever-guidance.ts
ccadffd92bfb5cfad02ccf2dd1fae277  eval/ada-runtime/ada/agent/lever-guidance.ts
37fd53b1c7e8dc15c61eb166910661d1  ada/agent/index.ts
37fd53b1c7e8dc15c61eb166910661d1  eval/ada-runtime/ada/agent/index.ts
```
