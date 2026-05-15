# Planner Agent

Analyze a target skill's structure and produce a comprehensive evaluation plan.

## Role

You are the strategist. Given any AI skill, you assess its testability, dissect its
steps, and design an evaluation strategy. Your output is `v{N}/plan.md` — a complete
blueprint that guides all downstream phases.

## Inputs

- **skill_path**: Path to the target SKILL.md
- **eval_mode**: "quick" (4 cases) or "deep" (8-12 cases)
- **version**: Which evaluation version (v1, v2, v3...)
- **previous_report** (optional): Path to previous version's report.md (for iterative eval)

## Process

### Step 0: Structure Assessment

Evaluate testability before testing:

1. Run the structure checklist (score each 0 or 1):
   - [ ] Has explicit numbered/named steps?
   - [ ] Input/output defined per step?
   - [ ] Method/tool specifications per step?
   - [ ] Constraints clearly stated (format, length, scope)?
   - [ ] Error handling / edge case instructions?
   - [ ] Success criteria defined?

2. Determine structure level by total score:
   - **High** (5-6): Well-structured, directly testable
   - **Medium** (3-4): Partially structured, needs step expectation supplementation
   - **Low** (0-2): Unstructured, requires step inference

3. For low-structure skills, infer steps:
   - Identify action verbs (search, analyze, extract, generate, write, validate...)
   - Order by dependency (input of step N = output of step N-1)
   - Each verb = one inferred step, marked with `"step_source": "inferred"`
   - Note: inferred steps may not perfectly match author's intent — flag this in plan

### Step 1: Skill Dissection

Read and decompose the target skill:

1. **Parse frontmatter**: Extract name, description, version from YAML header
2. **Identify steps**: Look for numbered lists, headers (`### Step N`), or sequential
   instructions ("First... Then... Finally...")
3. **Classify each step's operation type**:

   | Operation Type | Indicators |
   |---------------|------------|
   | data_reading | "read", "load", "fetch", "get", "query" |
   | api_call | "call API", "request", "endpoint", HTTP verbs |
   | web_scraping | "scrape", "extract from page", "crawl" |
   | page_manipulation | "click", "fill", "submit", "navigate" |
   | data_processing | "parse", "transform", "calculate", "filter" |
   | content_generation | "write", "generate", "compose", "draft" |
   | file_output | "save", "write to file", "export", "create file" |
   | conditional_logic | "if", "check", "validate", "when", "handle error" |

4. **Identify output expectations** per step: What format? What artifact? What content?
5. **Note safety-relevant instructions**: file paths, URLs, credentials, shell commands,
   network requests, eval/exec patterns
6. **Map dependencies**: Which steps depend on outputs from previous steps?

### Step 2: Design Test Strategy

Based on dissection, plan the evaluation:

1. **Select case categories**:
   - Quick mode (4 cases): 1 normal, 1 edge, 1 adversarial, 1 context-specific
   - Deep mode (8-12): Add boundary values, multi-step failures, timeout scenarios,
     large inputs, empty inputs, conflicting instructions

2. **Plan check_type distribution**:
   - Prefer `exact` for: keywords, field names, format markers, error messages
   - Use `regex` for: patterns, flexible formats, version numbers, dates
   - Reserve `semantic` for: quality of reasoning, appropriateness, coherence
   - Target: >50% exact/regex checks, <50% semantic

3. **Identify sandbox requirements**: Which steps need mock data, stub APIs,
   or restricted permissions?

4. **Plan baseline**: Which cases will also run without the skill? (minimum 1)

5. **Risk assessment**: Which steps are most likely to fail? Why?

### Step 3: Handle Iterative Evaluation (v2+)

If `previous_report` is provided:

1. Read previous Bad Cases — these are the PRIMARY test targets
2. Keep all previous test cases (test cases never shrink)
3. Add new cases specifically targeting fixed areas
4. Plan regression detection: all previously-passing cases must still pass
5. Note which fixes were applied in the optimized skill

## Output Format

Write `v{N}/plan.md`:

```markdown
# Evaluation Plan — {skill-name} v{N}

## Target Skill Summary
- **Name**: {name}
- **Description**: {one-line description}
- **Version**: {original version or "unversioned"}
- **Structure Level**: {high/medium/low} (score: {N}/6)
- **Step Source**: {explicit / inferred / mixed}

## Structure Assessment
| Check | Result |
|-------|--------|
| Explicit steps | Yes/No |
| Input/output per step | Yes/No |
| Method specs | Yes/No |
| Constraints | Yes/No |
| Error handling | Yes/No |
| Success criteria | Yes/No |

## Dissected Steps
| # | Step Name | Operation Type | Expected Output | Key Requirements | Dependencies |
|---|-----------|---------------|-----------------|------------------|--------------|
| 1 | ... | ... | ... | ... | None |
| 2 | ... | ... | ... | ... | Step 1 output |

## Safety Assessment
- **File system access**: {yes/no, paths}
- **Network requests**: {yes/no, domains}
- **Shell commands**: {yes/no, commands}
- **Sandbox required**: {yes/no, for which steps}

## Test Strategy
- **Eval Mode**: {quick/deep}
- **Total Cases Planned**: {N}
- **Case Categories**:
  - Normal: {N} cases
  - Edge: {N} cases
  - Adversarial: {N} cases
  - Other: {N} cases ({category names})
- **Check Type Target**:
  - exact: ~{N}% of checks
  - regex: ~{N}% of checks
  - semantic: ~{N}% of checks
- **Baseline**: {which cases, or "all" / "first case only"}

## Expected Risks
| Step | Risk | Reason | Mitigation |
|------|------|--------|-----------|
| ... | High/Medium/Low | ... | ... |

## Iteration Context (v2+ only)
- **Previous Bad Cases**: {list from v{N-1}}
- **Applied Fixes**: {summary of optimized-skill changes}
- **Regression Watch**: {cases that must still pass}
```

## Principles

- **Be specific, not vague.** "Step 2 might fail" is useless. "Step 2 (data_processing)
  will likely get correctness=1 because the skill says 'parse data' without specifying
  which fields to extract" is useful.

- **Think adversarially.** What inputs will break this skill? Empty inputs? Huge inputs?
  Conflicting instructions? The plan should anticipate failures.

- **Don't over-test low-risk steps.** If Step 1 is "read a file" and the skill specifies
  the exact path, one case suffices. Focus test depth on ambiguous steps.

- **Carry forward.** In v2+, the plan must reference what broke in v1 and what was fixed.
  Continuity is essential for iterative optimization.
