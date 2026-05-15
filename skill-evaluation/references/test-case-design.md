# Test Case Design Guide

Detailed guide for designing test cases with per-step expected results (Phase 2).

## Core Principles

1. **Expected results BEFORE execution.** Never adjust after seeing actual output.
2. **Prefer code-verifiable checks.** exact/regex > semantic, always.
3. **Every step must be individually testable.** If you can't define expected output
   for a step, the skill's instruction for that step is too vague.
4. **Cover the failure space.** Normal cases prove it works; edge/adversarial cases
   prove it's robust.

---

## check_type Selection

| check_type | Verification Method | When to Use | Example |
|------------|-------------------|-------------|---------|
| `"exact"` | `value in output` (code) | Keywords, field names, format markers, error messages | `"must_contain": [{"value": "username", "check_type": "exact"}]` |
| `"regex"` | `re.search(pattern, output)` (code) | Patterns, flexible formats, dates, numbers | `"must_contain": [{"value": "\\d{4}-\\d{2}-\\d{2}", "check_type": "regex"}]` |
| `"semantic"` | LLM judgment | Quality of reasoning, appropriateness, coherence | `"must_contain": [{"value": "explanation of why the error occurred", "check_type": "semantic"}]` |

**Target distribution:** >50% exact/regex, <50% semantic.

---

## Case Category Definitions

### Normal Cases
- Happy path with valid, typical inputs
- Tests the skill under ideal conditions
- Should pass with completion=1, correctness=2, quality=2

### Edge Cases
- Boundary values, empty inputs, very large inputs
- Missing optional fields, extra unexpected fields
- Tests robustness of individual steps

### Adversarial Cases
- Inputs designed to confuse or break the skill
- Conflicting instructions, ambiguous requests
- Inputs that look valid but are semantically wrong

### Deviation Cases (for multi-turn skills)
- User changes mind mid-conversation
- User provides contradictory follow-up
- User cancels or restarts

---

## cases.json Structure

```json
{
  "test_cases_version": "v1",
  "skill_name": "example-skill",
  "created_at": "2026-05-14T16:00:00Z",
  "eval_mode": "quick",
  "total_cases": 4,
  "cases": [
    {
      "test_case_id": "TC-001",
      "name": "Normal flow - standard user query",
      "category": "normal",
      "input": {
        "user_query": "Help me query user 123's info and generate a report",
        "context_files": ["users.json"],
        "context_data": {
          "users.json": "{\"123\": {\"name\": \"Alice\", \"email\": \"a@b.com\"}}"
        }
      },
      "expected_results": {
        "per_step": [
          {
            "step": "Step 1: Fetch user data",
            "operation_type": "data_reading",
            "expected_action": "Read users.json and extract user 123",
            "expected_output": "User object with name and email fields",
            "must_contain": [
              {"value": "Alice", "check_type": "exact"},
              {"value": "a@b.com", "check_type": "exact"},
              {"value": "user\\s*1?2?3", "check_type": "regex"}
            ],
            "must_not_contain": ["password", "internal_id", "secret"],
            "scoring_scale": {
              "correctness": 3,
              "quality": 3
            }
          },
          {
            "step": "Step 2: Generate report",
            "operation_type": "content_generation",
            "expected_action": "Format user data into markdown report",
            "expected_output": "Markdown formatted report with user info",
            "must_contain": [
              {"value": "# User Report", "check_type": "exact"},
              {"value": "Alice", "check_type": "exact"},
              {"value": "\\|.*name.*\\|.*email.*\\|", "check_type": "regex"}
            ],
            "must_not_contain": [],
            "format_requirement": "Markdown with table",
            "scoring_scale": {
              "correctness": 3,
              "quality": 3
            }
          }
        ]
      }
    },
    {
      "test_case_id": "TC-002",
      "name": "Edge case - user not found",
      "category": "edge",
      "input": {
        "user_query": "Get info for user 999",
        "context_files": ["users.json"],
        "context_data": {
          "users.json": "{\"123\": {\"name\": \"Alice\"}}"
        }
      },
      "expected_results": {
        "per_step": [
          {
            "step": "Step 1: Fetch user data",
            "operation_type": "data_reading",
            "expected_action": "Attempt to find user 999, discover it doesn't exist",
            "expected_output": "Error or not-found indication",
            "must_contain": [
              {"value": "not found|does not exist|no user", "check_type": "regex"}
            ],
            "must_not_contain": ["Alice"],
            "scoring_scale": {
              "correctness": 2,
              "quality": 3
            }
          }
        ]
      }
    }
  ]
}
```

---

## Per-Step Expected Results Fields

| Field | Required | Description |
|-------|----------|-------------|
| `step` | Yes | Must match step name from plan.md exactly |
| `operation_type` | Yes | From the dissection in plan.md |
| `expected_action` | Yes | What the model SHOULD do (human readable) |
| `expected_output` | Yes | What the output SHOULD contain (human readable) |
| `must_contain` | Yes | Array of check items (value + check_type) |
| `must_not_contain` | No | Array of strings that MUST NOT appear |
| `format_requirement` | No | Expected format (JSON, Markdown table, etc.) |
| `scoring_scale` | Yes | `correctness`: 2 or 3 point; `quality`: 2 or 3 point |

---

## Scoring Scale Selection

| Step characteristic | Correctness scale | Quality scale |
|--------------------|-------------------|---------------|
| Binary outcome (number matches, boolean check) | 2-point (0/1) | 3-point |
| Gradient outcome (content, extraction, formatting) | 3-point (0/1/2) | 3-point |
| Simple constraint (one rule) | 3-point | 2-point (0/1) |
| Complex constraints (multiple rules) | 3-point | 3-point |

---

## How Many Cases

| Mode | Total | Normal | Edge | Adversarial | Other |
|------|-------|--------|------|-------------|-------|
| Quick | 4 | 1-2 | 1 | 1 | 0-1 |
| Deep | 8-12 | 3-4 | 2-3 | 2-3 | 1-2 |

For iterative evaluation (v2+):
- Keep ALL previous cases
- Add 1-2 new cases targeting the specific fixes applied
- Total may grow beyond the mode's original count

---

## Common Pitfalls

| Pitfall | Why it's bad | Fix |
|---------|-------------|-----|
| All semantic checks | Can't verify reproducibly | Convert to exact/regex where possible |
| Expected results too vague | Judge can't score reliably | Be specific: "table with 3 columns" not "some output" |
| No edge cases | Skill looks good but breaks in production | Always include at least 1 edge case |
| must_contain matches too broadly | False positives | Make patterns more specific |
| Adjusting expected after seeing actual | Defeats the purpose | Write ALL expected results BEFORE Phase 3 |
