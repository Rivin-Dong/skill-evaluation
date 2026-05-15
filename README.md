# Skill Eval

> 🏥 **A diagnostic instrument for AI skills.** Test, score, and fix any AI skill through systematic evaluation — then iterate until it's bulletproof.

---

<p align="center">
  <b>Feed it any skill → Get back what's broken and how to fix it.</b>
</p>

---

## 🤔 The Problem

You wrote an AI skill (a prompt, a system instruction, an agent). You ran a few examples. It looked fine. You shipped it.

**Then it broke in production.** An empty input crashed it. A confusing query sent it down the wrong path. A user's slight rephrase made it skip a critical step entirely.

Most skill testing today is **vibes-based** — run a couple of examples, eyeball the output, call it good. That's not testing. That's hoping.

## ✅ What Skill Eval Does

Skill Eval treats skill testing like **medical diagnosis**:

| Instead of... | It does this... |
|--------------|----------------|
| "Looks fine to me" | 3 independent scores per step (Completion, Correctness, Quality) |
| One happy-path example | 4-12 test cases spanning normal, edge, and adversarial inputs |
| Vagueness about what went wrong | Bad Cases shown FIRST with exact reasons |
| "I'll tweak something" and hoping | Root cause analysis → concrete fix → re-test |
| No proof the skill even helps | Baseline comparison (skill on vs skill off) |
| No version tracking | Immutable v1/v2/v3 directories with full iteration history |

---

## 🧠 The Pipeline (5 Phases, 1 Rule)

Each phase produces **exactly one file**. No file = phase incomplete. Go back.

```
Target Skill
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Phase 0-1: Analyze & Plan          → plan.md       │
│  Phase 2:   Design Test Cases       → cases.json    │
│  Phase 3:   Execute & Record        → execution.json│
│  Phase 4:   Score & Verify          → (scored data)  │
│  Phase 5:   Report & Optimize       → report.md     │
│                                      → new SKILL.md  │
└─────────────────────────────────────────────────────┘
```

### The Scoring System (3 Scores, Never Combined)

| Score | Scale | What It Measures |
|-------|-------|-----------------|
| **Completion** | 0 or 1 | Did the operation even execute? |
| **Correctness** | 0 / 1 / 2 | Does actual match expected? |
| **Execution Quality** | 0 / 1 / 2 | Did it follow the skill's own rules? |

No weighted totals. No "78/100". Just honest, independent scores that tell you exactly where things broke.

---

## 📁 What You Get

After evaluation, a versioned directory appears next to your skill:

```
your-skill-eval/
├── v1/                          # First evaluation round
│   ├── plan.md                  # Test strategy & risk assessment
│   ├── cases.json               # 4-12 test cases with expected results
│   ├── execution-results.json   # What actually happened, step by step
│   ├── report.md                # Full report (Bad Cases FIRST)
│   └── optimized-skill/         # Fixed skill, ready for round 2
│       └── SKILL.md
├── v2/                          # Second round (did the fixes work?)
│   └── ...
└── summary.md                   # Cross-version overview
```

**You can trace the entire journey** from the initial evaluation through every fix and re-test.

---

## 🔴 Bad Cases First

Most reports bury bad news. Not this one. The report opens with what's broken:

```
┌───────────────────────────────────────────────────────────┐
│  BAD CASES (3 of 10, 30%)                                 │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  TC-003  "Edge case: empty input"                         │
│  Step 3  [Submit form]                                    │
│  Completion: 0  |  Correctness: 0  |  Quality: 0          │
│                                                           │
│  Expected: Show error message "Please fill required..."   │
│  Actual:   Submitted empty form, got 500 error            │
│  Reason:   Core validation not performed                  │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

Then the overview, then step-by-step scores. Then **an optimized version of your skill with the exact fixes applied**.

---

## 🎯 When to Use

| Scenario | What You Get |
|----------|-------------|
| "I wrote a skill. Is it good?" | A full report with scores and improvement suggestions |
| "I fixed something. Did it work?" | Version comparison showing exactly what improved (and what regressed) |
| "My skill works... sometimes." | Per-step diagnosis revealing which specific steps fail under which inputs |
| "Is this skill ready for production?" | Stop conditions: 0 Bad Cases, correctness ≥ 1.8/2, no regressions, 0% unsafe |
| "Someone asked me to review their skill" | A structured, evidence-based evaluation you can share |

---

## 🔬 Real Test Cases, Real Results

Test cases are **not generic**. Each is tailored to the skill being evaluated:

| Category | What It Tests | Example |
|----------|--------------|---------|
| **Normal** | Happy path with valid inputs | "Query user 123 and generate a report" |
| **Edge** | Boundary conditions | "Query user 999" (doesn't exist) |
| **Adversarial** | Inputs designed to confuse | Provide conflicting instructions |
| **Deviation** | Multi-turn chaos | User changes mind mid-session |

Each test case defines **exactly what each step should produce** — before execution. Never adjusted after.

---

## 🛡️ Safety Included

Skill Eval doesn't just measure performance. It scans for danger:

- 🔴 Hardcoded credentials or API keys
- 🔴 `rm -rf`, `eval()`, `os.system()`, or `subprocess(shell=True)`
- 🟠 Unrestricted file system access
- 🟠 Environment variable exposure
- 🟡 Prompt injection susceptibility

Plus: **sandbox-first execution** — when evaluating untrusted skills, everything runs in a disposable workspace with approval mode.

---

## 🌐 Multi-Platform

Skill Eval works across AI coding platforms:

| Platform | Where skills live | How triggers are tested |
|----------|------------------|------------------------|
| **Claude Code** | `.claude/commands/` | `claude -p` CLI |
| **Cursor** | `.cursor/rules/` | Agent mode |
| **Codex** | `.codex/skills/` | CLI/API |
| **OpenClaw** | `.claw/skills/` | Hub activation |

Auto-detection or explicit `--platform` flag — your choice.

---

## ⚡ Quick Start

### Evaluate Any Skill

```
"Evaluate my skill at skills/my-skill/SKILL.md using quick mode"
```

The evaluator will:
1. Read your skill and produce `my-skill-eval/v1/plan.md`
2. Generate `v1/cases.json` with 4 test cases
3. Execute them and record `v1/execution-results.json`
4. Score everything, find Bad Cases
5. Write `v1/report.md` and (if Bad Cases found) `v1/optimized-skill/SKILL.md`

### Iterate

```
"Now evaluate my-skill-eval/v1/optimized-skill/SKILL.md"
```

This creates `v2/` with comparison against `v1` — showing exactly what improved.

### Repeat Until...

```
Bad Cases: 0 ✅
Correctness avg: 1.92/2 ✅
No regressions ✅
Unsafe rate: 0% ✅
→ PASSED. Your skill is production-ready.
```

---

## 🧱 Architecture

```
├── SKILL.md              ← Main entry point (212 lines of flow + checkpoints)
├── agents/               ← Each phase has its own agent protocol
│   ├── planner.md        ← Phase 0-1: Structure assessment + strategy
│   ├── executor.md       ← Phase 3:   Test execution + sandboxing
│   ├── judge.md          ← Phase 4:   Scoring engine
│   ├── advisor.md        ← Phase 5B:  Root cause analysis + fixes
│   └── reporter.md       ← Phase 5:   Report generation + summary
├── references/           ← Deep-dive guides and schemas
│   ├── test-case-design.md
│   ├── schemas.md
│   ├── scoring.md
│   ├── rubrics.md
│   └── report-format.md
└── scripts/              ← Computation engines
    ├── score_engine.py   ← Automated score computation
    ├── safety_scanner.py ← Static security analysis
    ├── generate_scorecard.py ← HTML report generation
    └── run_trigger_eval.py   ← Multi-platform trigger testing
```

---

## 📊 Sample Report Snippet

```markdown
## Overview

| Metric | Value |
|--------|-------|
| Total Cases | 10 |
| Bad Cases | 3 (30%) |
| Completion avg | 0.85/1 |
| Correctness avg | 1.42/2 |
| Exec Quality avg | 1.65/2 |
| Trigger Precision | 83% |
| Trigger Recall | 100% |
| Unsafe Rate | 10% (2/20) |

## Step Scores

| Step | Completion | Correctness | Quality |
|------|-----------|-------------|---------|
| Step 1: Fetch data | 1.00 | 1.80 | 2.00 |
| Step 2: Parse data | 0.90 | 1.50 | 1.70 |
| Step 3: Generate report | 0.60 | 0.90 | 1.00 ⚠️ |
```

---

## 💡 Philosophy

> Most skill testing is vibes-based. Skill Eval is evidence-based.

- **Low scores, not percentage soup.** A 2-point correctness scale tells you more than "87/100".
- **Bad Cases first, always.** Averages lie. Failures don't.
- **Every fix has an address.** Each optimization references which Bad Case it fixes, in which step, with what expected improvement.
- **Immutable versions.** You can't "fix in place." Every change is a new version with a full delta report.
- **The baseline proves value.** If your skill doesn't outperform a bare model on the same input, why use it?

---

<p align="center">
  <sub>Built to turn "trust me, it works" into "here's the data, it works."</sub>
</p>
