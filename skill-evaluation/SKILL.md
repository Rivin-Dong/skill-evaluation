---
name: skill-evaluation
description: >
  Evaluate any AI skill's quality through step-by-step diagnosis — measuring trigger accuracy,
  per-step execution (completion/correctness/quality), efficiency, and safety — then produce a
  structured report with Bad Cases highlighted and actionable fixes. Supports iterative
  optimization with version control. Use this skill whenever someone wants to test a skill,
  evaluate prompt quality, benchmark a skill, diagnose why a skill underperforms, compare
  skill versions, check if a skill is production-ready, or get a quality assessment for any
  AI skill or prompt.
---

# Skill Eval

A diagnostic instrument for AI skills. Feed it any skill, get back a structured report —
what's working, what's broken (Bad Cases), and what to fix — then iterate until it passes.

---

## Output Structure (Mandatory)

Create `{target-skill-name}-eval/` at the same level as the target skill:

```
{target-skill-name}-eval/
├── v1/
│   ├── plan.md
│   ├── cases.json
│   ├── execution-results.json
│   ├── report.md
│   └── optimized-skill/SKILL.md
├── v2/ ...
└── summary.md
```

Version rule: v1 → v2 → v3. Always create a new `v{N}/` for each run.

---

## Pipeline & Checkpoints

| Phase | Action | Output File | Detail |
|-------|--------|-------------|--------|
| 0-1 | Analyze skill + design plan | `v{N}/plan.md` | `agents/planner.md` |
| 2 | Design test cases | `v{N}/cases.json` | `references/test-case-design.md` |
| 3 | Execute & record | `v{N}/execution-results.json` | `agents/executor.md` |
| 4 | Score & verify | _(scores for Phase 5)_ | `agents/judge.md` + `references/scoring.md` |
| 5 | Report + optimize | `v{N}/report.md` + `optimized-skill/SKILL.md` + `summary.md` | `agents/reporter.md` + `agents/advisor.md` |

**RULE: Each phase writes its file BEFORE the next begins. No file = not done. Go back.**

---

## Phase 0-1: Analyze & Plan

**Input**: Target SKILL.md
**Output**: `v{N}/plan.md`

Assess structure (high/medium/low), dissect steps with operation types, design test
strategy, identify risks and sandbox requirements.

Full protocol → `agents/planner.md`

> **CHECKPOINT**: Write `v{N}/plan.md`. Verify it exists. Do NOT proceed until written.

---

## Phase 2: Design Test Cases

**Input**: `v{N}/plan.md` + target SKILL.md
**Output**: `v{N}/cases.json`

Generate per-step expected results with check_types (exact > regex > semantic).
Quick mode: 4 cases. Deep mode: 8-12 cases.

Critical: Expected results written BEFORE execution. Never adjust after.

Full protocol → `references/test-case-design.md`
JSON schema → `references/schemas.md`

> **CHECKPOINT**: Write `v{N}/cases.json`. At least 4 cases (quick) or 8 (deep). Do NOT proceed until written.

---

## Phase 3: Execute & Record

**Input**: `v{N}/cases.json` + target SKILL.md
**Output**: `v{N}/execution-results.json`

Run each case with the skill active. Record per-step: action_taken, actual_output,
tool_calls, tokens, time. Run at least 1 baseline (without skill).

Full protocol → `agents/executor.md`
JSON schema → `references/schemas.md`

> **CHECKPOINT**: Write `v{N}/execution-results.json`. Every case must have entries. Do NOT proceed until written.

---

## Phase 4: Score & Verify

**Input**: `v{N}/execution-results.json` + `v{N}/cases.json`
**Output**: Scored data for Phase 5

Three independent scores per step:
- **Completion** (0/1): Did the operation execute?
- **Correctness** (0/1/2): Does actual match expected?
- **Execution Quality** (0/1/2): Did it follow the skill's method?

Rules: Completion=0 cascades. Scores never combined. Every sub-max score needs a reason.

Full protocol → `agents/judge.md`
Scoring definitions → `references/scoring.md`
Rubric templates → `references/rubrics.md`

> **CHECKPOINT**: All steps scored. Every step has three scores + reasons. Ready for Phase 5.

---

## Phase 5: Report & Optimize

**Input**: Scored results + Advisor analysis
**Outputs**: `v{N}/report.md` + `v{N}/optimized-skill/SKILL.md` + `summary.md`

Report order: Bad Cases FIRST → Overview → Step Scores → Baseline → Efficiency → Safety → Details.

If Bad Cases exist → produce optimized skill with fixes applied.
If Bad Cases = 0 + stop conditions met → PASSED.

Full protocol → `agents/reporter.md`
Root cause analysis → `agents/advisor.md`
Visual formats → `references/report-format.md`

> **CHECKPOINT**:
> - `v{N}/report.md` exists with Bad Cases + overview + step scores
> - Bad Cases > 0 → `v{N}/optimized-skill/SKILL.md` exists
> - `summary.md` updated

---

## Bad Cases

A step is a Bad Case if ANY: Completion=0, Correctness=0, Quality=0, or safety finding.

---

## Stop Conditions (All Must Be True to PASS)

| Condition | Threshold |
|-----------|-----------|
| Bad Cases = 0 | No steps with any score = 0 |
| Correctness avg | >= 1.8/2 |
| No regressions | No previously-passing case now fails |
| Unsafe rate = 0% | No safety findings |

---

## Non-Negotiables

1. Expected results before execution.
2. Low scores need reasons (expected vs actual).
3. Bad Cases shown first.
4. Three scores stay independent. Never combined.
5. Versions immutable. New v{N} for each run.
6. Every fix traces to a Bad Case.
7. Regressions are zero-tolerance.
8. Structure check before testing.
9. Baseline proves skill's value.
10. Every phase writes its file. No file = not done.

---

## File Index

| File | Purpose |
|------|---------|
| `agents/planner.md` | Phase 0-1: Structure assessment + plan generation |
| `agents/executor.md` | Phase 3: Test execution + recording |
| `agents/judge.md` | Phase 4: Scoring engine protocol |
| `agents/advisor.md` | Phase 5B: Root cause analysis + optimization |
| `agents/reporter.md` | Phase 5: Report generation + summary |
| `references/test-case-design.md` | Phase 2: Case design guide + cases.json schema |
| `references/schemas.md` | All JSON data structure definitions |
| `references/scoring.md` | Scoring scales, computation, display |
| `references/rubrics.md` | Per-operation-type rubric templates |
| `references/report-format.md` | Visual report presentation |
| `scripts/score_engine.py` | Automated scoring computation |
| `scripts/safety_scanner.py` | Static safety analysis |
| `scripts/generate_scorecard.py` | HTML report generation |
| `scripts/run_trigger_eval.py` | Multi-platform trigger evaluation |

---

## Platform Compatibility

| Platform | Skill Location | Trigger |
|----------|---------------|---------|
| Claude Code | `.claude/commands/` | `claude -p` CLI |
| Cursor | `.cursor/rules/` | Agent mode |
| Codex | `.codex/skills/` | CLI/API |
| OpenClaw | `.claw/skills/` | Hub activation |

---

## Security

- **Sandbox untrusted skills** — disposable workspace, mock data, approval mode
- **Skill names sanitized** — no path traversal in trigger probes
- **HTML reports escaped** — `html.escape()` on all interpolated values
- **Descriptions neutralized** — prompt-injection patterns stripped from probe files

See `agents/executor.md` Safety Boundary section for full sandboxing protocol.
