# The Watchdog That Worked, and the Clock That Didn't

> **This is the narrative account of the campaign.** Every figure in it is restated with
> its statistics, its caveats and its artifact path in [`RESULTS.md`](RESULTS.md), which is
> the record. Where the two differ, `RESULTS.md` is correct.

*NEO, our autonomous engineering agent, took a coding agent from 34/81 to 54/81 on
software-setup tasks — not by making it smarter, but by stopping the harness from killing it
mid-flight. It then built an elegant second fix, measured it at +28, promoted it, and — three
runs later — caught its own control being a bad day and withdrew the claim. The withdrawal is
the more useful half of this report.*

> **Confirmed, 2026-09-16.** The kept fix has since been re-measured on its own: a
> pre-registered two-replicate run on 2026-09-15 scores the shipped build **98/157 against the
> origin build's 67/157 (net +31, p = 7.92e-09)**, with every condition of the rule met before
> the numbers were seen. The full decomposition is in [`RESULTS.md`](RESULTS.md).

> **Correction, 2026-09-13.** This report previously headlined `24/81 → 52/81, p = 0.0000008`
> for the time-hints change. That comparison paired two runs on different days, and the
> control was a depressed run: the same build scores 54/81 two days later. Re-measured
> against a same-day control, the time-hints change is **−4 tasks (54/81 → 50/81, p = 0.42)**
> and its promotion has been withdrawn. Every figure below is the corrected one.

The system we optimized is **Ada**, a TypeScript coding agent that does software setup
tasks: installing dependencies, configuring databases, getting real repositories running.
It runs `z-ai/glm-5.3-flash` through OpenRouter and is graded by official task checkers in
Docker containers on **SetupBench**, an 81-task suite.

Two layers are at work in this campaign, and both run the same model. **Ada** is the agent
being optimized — it runs `z-ai/glm-5.3-flash` as its working brain. **The autoresearcher
loop** (`autoresearcher/`) is the harness that proposes, implements, and evaluates changes
to Ada — its orchestrator, planner, and experiment roles are also configured on
`z-ai/glm-5.3-flash` (`config-ada.toml`). The same model is both the subject and the
experimenter; every judgment in this report about what Ada should do next came from the
same model family that runs inside Ada.

Ada had a problem that had nothing to do with skill.

Give it a task with an 8-minute budget and it would work competently for 7 minutes —
installing packages, editing configs, starting services — and then, with 60 seconds left,
start a `sleep 300` poll or a fresh debugging tangent. The clock would run out mid-flight,
the run would be killed, and the task would fail. The agent never knew the deadline was
coming, because the only mention of the budget was written into its system prompt once, at
the start, and never updated.

A human developer glances at the clock. Ada couldn't.

## The two fixes, in one sentence each

> **The watchdog (kept):** anchor the deadline to the container's actual start time and
> interrupt the agent before the external kill, then exit cleanly so the partial work gets
> graded.

> **The time hints (tried, not kept):** before every model request, inject
> `⏱ 74 s of 480 s remain.` — and when time is nearly up, say *stop exploring, make the
> success command pass now, and stop*; cap any Bash timeout so a single `sleep` can never
> eat the remaining budget.

The watchdog is the one that moved pass rate. The time hints ship in the code, default off.

## What it delivered

Three builds, all measured on the **same day**, all 81 tasks, one driver, identical
conditions. Same-day is the whole point — see "the number we had to take back", twice, below.

| Build | What it adds | Passed | Against the row above |
|---|---|---:|---|
| `df0c537` | the starting point | 34 / 81 | — |
| `6672af8` | **a watchdog and a container-anchored deadline** | **54 / 81** | **+20**, 21 gained / 1 lost, McNemar **p = 0.000011** |
| `2e495bb` | **+ the time hints described above** | 50 / 81 | **−4**, 5 gained / 9 lost, **p = 0.42** |

**The win is the watchdog, and it is entirely one thing.** Before it, 46 of the 81 tasks
produced *zero turns* — the agent overran its budget, the harness hard-killed the container,
and nothing was ever graded. After it, an overrun becomes an interrupt, the partial work gets
graded, and 21 of those 46 tasks pass. On the 35 tasks the old build could actually run, it
scored 34/35 — and nothing built since has beaten that.

**The time hints did not add to it.** They do everything they were designed to do: runs
interrupted at the deadline drop from 34 to 7, total turns fall 11%, wall time falls 5%. The
agent really does pace itself once it can see the clock. It just doesn't finish more tasks
that way, and on the 47 tasks where the control had time to spare it finishes *fewer*
(42/47 → 37/47) — the wrap-up instruction reaches tasks that were never in trouble and tells
them to stop looking.

That is not a null result dressed up. It is two results that were blended into one and should
never have been: **an efficiency win and no accuracy win.**

## The two failures that came first

The interesting part of this story is what *didn't* work, because it shows which kind of
change this model responds to.

### Failure 1: asking the model to be more careful

The failure traces showed a pattern: the agent would finish, announce "Setup complete
and verified," and the grader's command would fail — the wrong test runner, a database
verified over TCP when the grader uses a Unix socket, a literal value that didn't match
the task's contract.

So we wrote a careful "definition of done" section into the prompt: reproduce every path,
port, and value exactly; use the project's canonical toolchain; run the success check in a
fresh login shell before claiming victory. About 900 characters of precise, correct,
evidence-derived instruction.

The model read it. We can prove the model read it — byte-identity tests confirm the text
was delivered. And it changed almost nothing: 0 of the 10 targeted failure tasks
converted, and the paired dev run scored 2/12 against the control's 3/12. Dead tie within
noise.

**Verdict: not promoted. The gate stays in the code, default off.**

### Failure 2: making the model think less

The traces also showed thinking tokens consuming up to 93% of output on some runs. A probe
tested every suppression option the SDK exposes: `thinking: disabled` (the gateway rejects
it — "reasoning is mandatory"), `effort: low` (no effect), `budget_tokens` (works at the
raw HTTP layer, cutting thinking 6× — but the SDK path the agent actually uses never
forwards it).

**Verdict: no-go, dropped before spending a single evaluation dollar.**

## What the third attempt showed

Both failures shared a shape: they tried to change *what the model does* by changing what
it was *told* or how it was *configured*. The time hints didn't try to alter behavior at
all. They delivered a piece of information the model provably lacked — the current time
remaining — through a channel that cannot be ignored: a hook that fires before every
single model request.

The mechanism worked: given the clock, the model paced itself. Pacing just did not turn into
passed tasks — same-day, the hints are −4 (p = 0.42). The pass-rate gain that held came from
the watchdog, which changes nothing about the model and everything about whether its work
gets graded.

The smoke test made this visible. Asked to "quote verbatim any timing note attached to the
last tool result," the model wrote the hint back word for word. Asked to run `sleep 300`
with a 300-second timeout under a 90-second budget, the tool result reported a timeout of
20 seconds — the clamp had silently protected the budget.

## The caveat that turned out to be the result

When the time-hints change was promoted, three caveats were written down next to it. Two of
them were the story, and we ranked them as footnotes.

**"The arms ran on different days."** The protocol called for interleaved same-day arms; the
control was a stored run from the previous day. We wrote that cross-day pairing "adds variance
we can't fully exclude — though a p-value of 7.66e-07 leaves a lot of room for it."

It did not leave enough room. That control was a depressed run. Running the same build
again, on the same 81 tasks, under the same protocol, two days later: **24/81 became 54/81.
Thirty tasks gained, none lost, p = 0.0000000019.** Turn counts 0.6% apart, zero timeouts both days — the agent did
identical work and simply succeeded far more often, because the model behind it was having a
better day. A control that moves 30 tasks on its own cannot anchor a claim of 28.

**"The wrap-up instruction occasionally causes surrender."** Six candidate tasks had failed
with more than 40% of their budget unused, against zero for the control. The predicted
mechanism metric had moved *opposite* to the prediction, and we filed it as an acceptable
cost of a large win. With the win gone, it is the whole effect: on the same-day comparison,
the 47 tasks where the control finished comfortably go **42/47 → 37/47**.

**"More finishing means more confident wrong finishes."** This one replicated exactly, and
it is now the most useful number in the campaign. Of the candidate's 31 failures, **25 ended
with the agent announcing it was done while the grader's command failed** — against 5 of 27
for the control. The time hints do not make Ada finish more tasks. They make Ada *declare*
more tasks finished. That is the next real problem, and it is a different problem.

## Two numbers we had to take back

Twice in this campaign we corrected our own headline downward, unprompted, before anyone
else did — and both times for the same underlying reason.

**The first was 59/81 (73%).** That run was a hybrid: 50 scores carried over from earlier
measurements plus 31 fresh ones. Run whole and fresh, the same lineage measures 54/81 against
the origin build's 34/81. The carried scores had been measured under different conditions.

**The second, now withdrawn, was 52/81 against 24/81, +28, p = 0.0000008** — the headline of
this report until 2026-09-13. Its control was measured two days before its candidate. Re-measured same-day, the
change is −4.

Both failures are the same failure: **a comparison anchored to a run measured under conditions
that no longer held.** The first carried scores across protocols; the second carried a control
across days. There is now exactly one admissible design on this harness — two arms, one
driver, one machine, one day — and one canonical index of every run that exists
(`../bench/RUN_REGISTRY.md`), so no document can name "the control" without naming which run
it was.

The same discipline corrected the external benchmark: Terminal-Bench 2.0 was reported as
26/40 vs 28/40 until we found two trials where the *verifier's own infrastructure* failed
(apt mirror 404, missing curl) — those were never agent failures. The honest evaluable
endpoint is a dead tie, 26/38 vs 26/38, p = 1.0. The pass-rate gain did not reproduce
externally; what did carry over was efficiency — 39% fewer turns, 35% less execution time.

## What this demonstrates

**Your control is a measurement too.** We spent the campaign scrutinising candidates and
treated the control as a fixed number on a shelf. It was not. It moved 30 tasks between two
Thursdays while doing provably identical work. Every wrong headline in this project came from
a control measured under conditions that no longer held — and no amount of statistical rigour
on the candidate side can rescue that. Run both arms on the same day, or do not run them.

**A significant p-value is not a shield against a bad design.** The withdrawn result had
p = 0.0000008 and a confidence interval nowhere near zero. Both were computed correctly. Both
were answers to a question nobody wanted asked: *did these two particular runs differ?* They
did. It just wasn't because of the code.

**Separate the efficiency result from the accuracy result, always.** The time hints reduce
interrupted runs by 79% and turns by 11%. That is real, replicated, and worth having. It is
not a pass-rate improvement, and presenting one number that blends them is exactly how a
change gets promoted on evidence it does not have.

**Mechanism working is not the same as the change working.** We proved the model receives the
hint, quotes it verbatim, and paces itself accordingly. Every one of those checks passed.
The agent did precisely what we asked and did not get better at the task.

**Negative results are load-bearing.** Two prompt-only ideas were tried before this one and
reported as failures; a third was promoted and has now joined them. The honest count of this
campaign is one change that worked — a watchdog worth +20 — and three that did not. That
count is more useful than the one we published.

## Where this stands now

- **The build with evidence behind it** is `6672af8`: watchdog, container-anchored deadline,
  clean exit. Same-day, 54/81 against the origin build's 34/81, p = 0.000011.
- **It has been confirmed a second time, on the build that actually ships.** On 2026-09-15 a
  pre-registered two-replicate run measured `5f4c5c0` (the watchdog build with the time-hint
  gates off) at 47/81 and 52/81 against the origin build's 32/81 and 36/81 — pooled +31,
  p = 7.92e-09. The timeouts tell the same story as the first time: 44 and 40 on the baseline,
  **zero** on the shipped build, and every converted task comes from a run that used to be
  killed before it could be graded.
- **The time-awareness bundle now ships default-off.** Its gates stay in the code, opt-in,
  with their unit tests; with both off the agent registers no hooks and behaves as `6672af8`.
- **The one experiment worth running next on it**: raise `ADA_WRAP_UP_MS`, or fire the wrap-up
  only when the task has actually consumed most of its budget, and see whether the 5 lost
  clean-finish tasks come back without giving up the 34 → 7. Same-day paired, ≈$6.
- **The largest remaining headroom is verification discipline**, not pacing: 25 of 31 failures
  are the agent claiming success against a grader that disagrees.
- **Not claimed**: the agent is not more capable than before. On the 35 tasks the original
  build could attempt at all, it scored 34/35 and nothing since has improved on it. 27 of 81
  tasks still fail on the best build measured.

The full statistical record, per-task flip tables, and the audit checklist are in
[`RESULTS.md`](RESULTS.md). Every run in the campaign is indexed with its build, date and
score in `../bench/RUN_REGISTRY.md`, and the comparison that settled this is
`../bench/CTRL_VS_T12_REPORT.md`.

---

**[NEO: Your Autonomous AI Engineering Agent](https://heyneo.com)**

[![VS Code Extension](https://img.shields.io/badge/VS%20Code-Get%20the%20Extension-007ACC?style=for-the-badge&logo=visualstudiocode&logoColor=white)](https://marketplace.visualstudio.com/items?itemName=NeoResearchInc.heyneo)
[![Cursor Extension](https://img.shields.io/badge/Cursor-Get%20the%20Extension-1F1F1F?style=for-the-badge&logo=cursor&logoColor=white)](https://marketplace.cursorapi.com/items/?itemName=NeoResearchInc.heyneo)
[![Neo MCP Docs](https://img.shields.io/badge/Neo%20MCP-Documentation-6E56CF?style=for-the-badge&logo=readthedocs&logoColor=white)](https://docs.heyneo.com/neo-mcp)