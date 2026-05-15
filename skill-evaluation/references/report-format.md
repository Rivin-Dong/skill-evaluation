# Report Presentation Format

Visual formats for displaying evaluation reports in terminal and documents.

---

## Bad Cases First

```
+===================================================================+
|  BAD CASES (3 cases, 30% of total)                                |
+===================================================================+
|                                                                   |
|  TC-003 "Edge case: empty input"                                  |
|  Failed step: Step 3 [page_action] Submit form                    |
|  Completion: 0 | Correctness: 0 | Quality: 0                     |
|  Expected: Show error "Please fill required fields"               |
|  Actual: Submitted empty form, got 500 error                      |
|  Reason: Core validation not performed (ref: SKILL.md Step 3)     |
|                                                                   |
+===================================================================+
```

---

## Overview Panel

```
+===================================================================+
|  SKILL EVALUATION REPORT                                          |
|  Skill: {name}  Version: v1  Date: {date}                        |
|  Cases: 10     Bad Cases: 3 (30%)                                 |
+===================================================================+
|                                                                   |
|  Trigger:      Precision: 83%    Recall: 100%                     |
|  Completion:   avg 0.85/1                                         |
|  Correctness:  avg 1.42/2                                         |
|  Exec Quality: avg 1.65/2                                         |
|  Efficiency:   avg 18,420 tokens/case  avg 45.2s/case             |
|  Safety:       unsafe rate 10% (2/20)                             |
|                                                                   |
+===================================================================+
```

---

## Step Scores Table

```
+-----------------------+-----------+----------+----------+---------------+
| Step                  | Completion|Correctness| Quality | Low-score note|
|                       | (avg/1)   | (avg/2)  | (avg/2)  |              |
+-----------------------+-----------+----------+----------+---------------+
| Step 1: Search API    |  1.0      |  1.8     |  2.0     | -            |
| Step 2: Parse data    |  0.9      |  1.5     |  1.7     | -            |
| Step 3: Web scrape    |  0.8      |  1.1     |  1.2     | Incomplete   |
| Step 5: Generate report|  0.6     |  0.9     |  1.0     | Format issues|
+-----------------------+-----------+----------+----------+---------------+
```
