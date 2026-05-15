# JSON Schemas

Data structures used by skill-evaluation. All paths are relative to the evaluation output
directory `{skill-name}-eval/`.

---

## v{N}/cases.json

Test case definitions with per-step expected results.

```json
{
  "test_cases_version": "v1",
  "skill_name": "example-skill",
  "created_at": "2026-05-14T16:00:00Z",
  "cases": [
    {
      "test_case_id": "TC-001",
      "name": "Normal flow - fetch and process user data",
      "category": "normal",
      "input": {
        "user_query": "Help me query user 123's info and generate a report",
        "context_files": ["users.json"]
      },
      "expected_results": {
        "per_step": [
          {
            "step": "Step 1: Call user API",
            "operation_type": "api_call",
            "expected_action": "GET /api/users/123",
            "expected_output": "User object with name, email, role",
            "must_contain": ["name", "email", "role"],
            "must_not_contain": ["password", "internal_id"],
            "scoring_scale": {
              "correctness": 3,
              "quality": 3
            }
          },
          {
            "step": "Step 2: Parse and clean data",
            "operation_type": "data_processing",
            "expected_action": "Extract key fields and format",
            "expected_output": "Markdown table with username and email",
            "must_contain": ["username", "email"],
            "format_requirement": "Markdown table",
            "scoring_scale": {
              "correctness": 3,
              "quality": 3
            }
          },
          {
            "step": "Step 3: Generate report",
            "operation_type": "content_generation",
            "expected_action": "Produce complete report",
            "expected_output": "Report with user overview, activity, recommendations",
            "must_contain": ["overview", "activity", "recommendations"],
            "scoring_scale": {
              "correctness": 3,
              "quality": 3
            }
          }
        ],
        "final_output": {
          "format": "Markdown",
          "must_contain": ["user 123", "report"]
        }
      },
      "skill_requirements_ref": [
        "SKILL.md Step 1: Must use REST API",
        "SKILL.md Step 3: Report must include actionable recommendations"
      ]
    }
  ]
}
```

---

## v{N}/execution-results.json

Execution records with per-step actual behavior. This is the Phase 3 output file.

```json
{
  "run_id": "run-2026-05-14-v1",
  "skill_name": "example-skill",
  "skill_version": "v1",
  "executed_at": "2026-05-14T20:00:00+08:00",
  "environment": {
    "model": "claude-sonnet-4-20250514",
    "platform": "claude"
  },
  "step_names": [
    "Step 1: Call user API",
    "Step 2: Parse and clean data",
    "Step 3: Generate report"
  ],
  "total_cases": 10,
  "total_steps": 50,
  "duration_seconds": 452,
  "case_details": [
    {
      "test_case_id": "TC-001",
      "name": "Normal flow - fetch user data",
      "baseline": false,
      "steps": [
        {
          "step": "Step 1: Call user API",
          "operation_type": "api_call",
          "action_taken": "Called GET /api/users/123 with auth header",
          "actual_output": "{\"name\": \"Alice\", \"email\": \"alice@example.com\", \"role\": \"admin\"}",
          "tool_calls": ["api_call", "parse_response"],
          "tokens": 2100,
          "time_seconds": 8.2
        }
      ]
    }
  ]
}
```

**Key fields:**
- `baseline: true` — marks cases run WITHOUT the target skill (for comparison)
- `action_taken` — natural language description of what the model did
- `actual_output` — the raw output from the step
- `tool_calls` — array of tool names invoked during this step

> **Note**: This file does NOT contain scores. Scores are computed in Phase 4 and
> written into `v{N}/report.md`.

---

## v{N}/report.md (Embedded Data)

The evaluation report is a Markdown file. Scoring data, Bad Cases, and comparisons
are embedded within the report sections. No separate JSON report file is used.

The score engine (`scripts/score_engine.py`) consumes `v{N}/execution-results.json`
and outputs computed scores. These scores are then formatted into `v{N}/report.md`.

### Scoring Data Schema (used by score_engine.py)

```json
{
  "run_id": "run-2026-05-14-v1",
  "skill_name": "example-skill",
  "skill_version": "v1",
  "step_names": [
    "Step 1: Call user API",
    "Step 2: Parse and clean data",
    "Step 3: Generate report"
  ],
  "trigger": {
    "precision": 0.83,
    "recall": 1.0
  },
  "safety_findings": [
    {
      "severity": "MEDIUM",
      "description": "Output contains system path",
      "location": "Step 3, TC-007"
    }
  ],
  "total_safety_checks": 20,
  "case_details": [
    {
      "test_case_id": "TC-001",
      "name": "Normal flow - fetch user data",
      "steps": [
        {
          "step": "Step 1: Call user API",
          "operation_type": "api_call",
          "completion": 1,
          "correctness": 2,
          "execution_quality": 2,
          "expected": "GET /api/users/123 -> {name, email, role}",
          "actual": "GET /api/users/123 -> {name, email, role, avatar}",
          "low_score_reason": null,
          "tokens": 2100,
          "time_seconds": 8.2
        },
        {
          "step": "Step 2: Parse and clean data",
          "operation_type": "data_processing",
          "completion": 1,
          "correctness": 1,
          "execution_quality": 1,
          "expected": "Markdown table with username and email columns",
          "actual": "Plain text list, not table format",
          "low_score_reason": "correctness=1(partial): Content correct but format is plain text not Markdown table as expected. quality=1(partial): Skill requires table format (ref: SKILL.md Step 2), used plain list instead.",
          "tokens": 1800,
          "time_seconds": 3.5
        }
      ]
    }
  ]
}
```

---

## v{N}/plan.md (Format Specification)

The evaluation plan, in Markdown format:

```markdown
# Evaluation Plan — {skill-name} v{N}

## Target Skill Summary
- **Name**: {name}
- **Description**: {description}
- **Version**: {version}
- **Structure Level**: high / medium / low
- **Inferred Steps**: {yes if level=low, list inferred step names}

## Dissected Steps
| # | Step Name | Operation Type | Expected Output | Key Skill Requirements |
|---|-----------|---------------|-----------------|------------------------|
| 1 | ...       | ...           | ...             | ...                    |

## Test Strategy
- **Eval Mode**: quick (4 cases) / deep (8-12 cases)
- **Case Categories**: normal, edge, adversarial, [additional]
- **Check Type Distribution**:
  - exact: N items
  - regex: N items
  - semantic: N items
- **Steps Requiring Special Sandboxing**: [list]

## Baseline Plan
- **Run baseline**: yes / no
- **Compared Step Types**: [list]
- **Expected Skill Gain**: [qualitative]

## Expected Risks
- **Highest Risk Steps**: [list with reasoning]
- **Operation Types Needing Extra Scrutiny**: [list]

## Evaluation Output
- **Output Root**: {skill-name}-eval/
- **Current Version**: v{N}
- **Expected Files**: plan.md, cases.json, execution-results.json, report.md, optimized-skill/SKILL.md
```

---

## v{N}/report.md — Report Schema (Embedded)

The evaluation report (`v{N}/report.md`) is Markdown. The structural data it contains
is consumed by the score engine and HTML generator. Below is the report's internal
data schema for reference.

```json
{
  "skill_name": "example-skill",
  "skill_version": "v1",
  "eval_date": "2026-05-14",
  "test_cases_version": "v1",
  "total_cases": 10,
  "bad_case_count": 3,
  "bad_case_rate": 0.3,

  "trigger": {
    "status": "scored",
    "precision": 0.83,
    "recall": 1.0
  },

  "overall_averages": {
    "completion": 0.85,
    "correctness": 1.42,
    "execution_quality": 1.65
  },

  "per_step_averages": [
    {
      "step": "Step 1: Call user API",
      "operation_type": "api_call",
      "completion_avg": 1.0,
      "correctness_avg": 1.8,
      "quality_avg": 2.0,
      "low_score_note": null
    }
  ],

  "efficiency": {
    "avg_tokens_per_case": 18420,
    "avg_time_per_case_seconds": 45.2,
    "per_step": [
      {"step": "Step 1: Call user API", "avg_tokens": 2100, "avg_time_seconds": 8.2}
    ]
  },

  "safety": {
    "unsafe_rate": 0.1,
    "total_checks": 20,
    "unsafe_count": 2,
    "findings": []
  },

  "bad_cases": [
    {
      "test_case_id": "TC-003",
      "test_case_name": "Edge case: empty input",
      "failed_step": "Step 3: Submit form",
      "scores": {"completion": 0, "correctness": 0, "execution_quality": 0},
      "expected": "Show error message",
      "actual": "Submitted empty form, 500 error",
      "low_score_reason": "completion=0: Validation step not executed..."
    }
  ],

  "case_details": [],

  "version_comparison": null
}
```

---

## v{N}/report.md — Version Comparison (Section 9)

When `v{N>1}`, the report includes a version comparison section with this data:

```json
{
  "from_version": "v1",
  "to_version": "v2",
  "overall_deltas": {
    "completion": 0.07,
    "correctness": 0.33,
    "execution_quality": 0.17
  },
  "bad_case_changes": {
    "fixed": ["TC-003", "TC-007"],
    "remaining": ["TC-009"],
    "new_failures": []
  },
  "bad_case_count_delta": -2,
  "regressions": [
    {
      "test_case_id": "TC-002",
      "step": "Step 1: Call API",
      "metric": "correctness",
      "old_value": 2,
      "new_value": 1
    }
  ],
  "has_regressions": true
}
```

---

## v{N}/optimized-skill/SKILL.md

The optimized skill is a valid SKILL.md file, NOT a JSON optimization plan.
It is the actual skill content with fixes applied, ready to be used as `v{N+1}` input.

The optimization metadata is embedded as an HTML comment at the end of the file:

```markdown
---
name: {original-name}
description: >
  {description with fixes applied}
---

# {Skill Title}

... (fixed skill content) ...

<!-- EVALUATION OPTIMIZATION METADATA
optimization_id: OPT-{N}
from_version: v1
to_version: v2
date: 2026-05-14
based_on_report: v1/report.md

changes:
  - priority: P0
    target: "Step 3: Web scrape"
    bad_case_ref: TC-003
    root_cause: vague_instruction
    problem: "Step says 'extract info' without specifying fields or method"
    change_type: instruction_rewrite
    before: "Extract key information from the page"
    after: "Use querySelector: .title -> title, .price -> price, .stock -> stock"
    expected_improvement:
      correctness: "0 -> 2"
      execution_quality: "0 -> 2"
-->
```

**Key principle**: The optimized skill is a drop-in replacement for the original.
It can be fed directly into the next evaluation round as the `v{N+1}` target.

---

## summary.md

Top-level iteration overview, at `{skill-name}-eval/summary.md`.

```markdown
# Evaluation Summary — {skill-name}

| Version | Date | Cases | Bad Cases | Completion | Correctness | Quality | Unsafe Rate | Status |
|---------|------|-------|-----------|------------|-------------|---------|-------------|--------|
| v1      | 2026-05-13 | 10 | 3 | 0.85 | 1.42 | 1.65 | 10% | IN_PROGRESS |
| v2      | 2026-05-14 | 10 | 1 | 0.92 | 1.75 | 1.82 | 5%  | IN_PROGRESS |

## Iteration History
- **v1**: Initial evaluation. 3 Bad Cases in Steps 3, 5.
  Fixed: empty input validation, timeout retry.
- **v2**: 2 Bad Cases fixed. 1 remaining in Step 5 (format consistency).

## Current Status
**IN_PROGRESS** — 1 Bad Case remaining.

## Recommendations
- Focus on Step 5 format consistency
- Consider adding format template to SKILL.md
```

