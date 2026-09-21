# Machine load during this run (snapshot, 2026-09-19 11:47 UTC)

Recorded while the run was in progress, because timeouts and slow installs depend on how busy the machine is.

- 8 cores. Load average: 14.43 14.12 14.07 (1, 5, 15 min).
- The run's own 6 task containers used about 0.6 of a core in total (docker stats).
- Other work on the same machine, not started by this run: a headless Chrome (about 96% of a core), a Next.js server
  (about 62% CPU, 16% of memory), and two containers from a different benchmark harness (`task-n-...`). By user, non-root
  processes used about 290% CPU in total.
- Both builds run at the same time, so both face the same contention. Comparisons between the two builds within this run
  are therefore fair. Comparisons with the earlier v4 flash run are not: that run had a load of about 8 with the same 6 containers.
- Model reply time in this run: median 5.6 s per turn over 351 calls so far, about 3x slower than v4 flash (median about 1.9 s), and about 72% of attempt time so far is tool execution (installs).
