# The 40 / 41 task split

The 81 SetupBench tasks used in this comparison are split into a **40-task set** (`tasks.set40.txt`) and the
**41 remaining tasks** (`tasks.set41.txt`). The split is fixed, so both builds and every later run use exactly the same
sets, and the 41 are exactly the tasks the 40 leave out.

Method (deterministic, no manual picking):
1. Group the 81 tasks by `task_type`: bgsetup 7, dbsetup 13, dependency_resolution 14, reposetup 47.
2. Give each type a share of the 40 proportional to its size (largest-remainder rounding, so the shares sum to 40):
   bgsetup 4, dbsetup 6, dependency_resolution 7, reposetup 23.
3. Inside each type, order the tasks by `sha256("split-v1-20260919:<task id>")` and take the first tasks up to the share for the 40; the
   rest go to the 41.

Both sets therefore have about the same mix of task types. Regenerating with the same seed gives the same files.
