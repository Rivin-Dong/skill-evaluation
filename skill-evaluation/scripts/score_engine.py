#!/usr/bin/env python3
"""Score computation engine aligned with the methodology.

Reads execution results and computes:
- Automated checks (exact/regex verification)
- Per-step averages (completion, correctness, execution quality)
- Overall averages
- Bad Case identification
- Efficiency metrics
- Safety unsafe rate
- Baseline comparison
- Scoring stability verification (Deep Eval mode)

No weighted totals. No percentage scores. Three independent metrics per step.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from statistics import mean


def run_automated_checks(step: dict) -> dict:
    """Run code-based verification for exact and regex check_types.

    Returns a dict with pass/fail results for each must_contain item.
    """
    actual_output = step.get("actual", {})
    if isinstance(actual_output, dict):
        output_text = actual_output.get("raw_output", "") or actual_output.get("output", "")
    else:
        output_text = str(actual_output)

    expected = step.get("expected", {})
    if isinstance(expected, dict):
        must_contain = expected.get("must_contain", [])
        must_not_contain = expected.get("must_not_contain", [])
    else:
        must_contain = []
        must_not_contain = []

    checks = []
    for item in must_contain:
        if isinstance(item, dict):
            value = item.get("value", "")
            check_type = item.get("check_type", "semantic")
            pattern = item.get("pattern", value)
        else:
            value = str(item)
            check_type = "exact"
            pattern = value

        if check_type == "exact":
            result = "PASS" if value.lower() in output_text.lower() else "FAIL"
        elif check_type == "regex":
            result = "PASS" if re.search(pattern, output_text, re.IGNORECASE) else "FAIL"
        else:
            result = "SKIP"  # semantic checks need LLM

        checks.append({
            "value": value,
            "check_type": check_type,
            "result": result,
            "direction": "must_contain",
        })

    for item in must_not_contain:
        if isinstance(item, dict):
            value = item.get("value", "")
            check_type = item.get("check_type", "exact")
        else:
            value = str(item)
            check_type = "exact"

        if check_type == "exact":
            result = "PASS" if value.lower() not in output_text.lower() else "FAIL"
        elif check_type == "regex":
            result = "PASS" if not re.search(value, output_text, re.IGNORECASE) else "FAIL"
        else:
            result = "SKIP"

        checks.append({
            "value": value,
            "check_type": check_type,
            "result": result,
            "direction": "must_not_contain",
        })

    code_checks = [c for c in checks if c["result"] != "SKIP"]
    pass_count = sum(1 for c in code_checks if c["result"] == "PASS")
    pass_rate = pass_count / len(code_checks) if code_checks else 1.0

    return {
        "checks": checks,
        "code_verifiable_count": len(code_checks),
        "semantic_count": sum(1 for c in checks if c["result"] == "SKIP"),
        "pass_rate": round(pass_rate, 2),
    }


def identify_bad_cases(case_details: list[dict]) -> list[dict]:
    """Identify Bad Cases from case details."""
    bad_cases = []
    for case in case_details:
        case_id = case.get("test_case_id", "")
        case_name = case.get("name", case_id)
        for step in case.get("steps", []):
            is_bad = (
                step.get("completion", 1) == 0
                or step.get("correctness", 2) == 0
                or step.get("execution_quality", 2) == 0
            )
            if is_bad:
                bad_cases.append({
                    "test_case_id": case_id,
                    "test_case_name": case_name,
                    "failed_step": step.get("step", "unknown"),
                    "scores": {
                        "completion": step.get("completion", 0),
                        "correctness": step.get("correctness", 0),
                        "execution_quality": step.get("execution_quality", 0),
                    },
                    "expected": step.get("expected", ""),
                    "actual": step.get("actual", ""),
                    "low_score_reason": step.get("low_score_reason", ""),
                })
    return bad_cases


def compute_overall_averages(case_details: list[dict], exclude_uncertain: bool = True) -> dict:
    """Compute overall averages across all steps in all cases."""
    completions = []
    correctnesses = []
    qualities = []

    for case in case_details:
        for step in case.get("steps", []):
            stability = step.get("stability", {})
            if exclude_uncertain:
                if stability.get("completion") == "uncertain":
                    continue
                completions.append(step.get("completion", 0))
                if stability.get("correctness") != "uncertain":
                    correctnesses.append(step.get("correctness", 0))
                if stability.get("execution_quality") != "uncertain":
                    qualities.append(step.get("execution_quality", 0))
            else:
                completions.append(step.get("completion", 0))
                correctnesses.append(step.get("correctness", 0))
                qualities.append(step.get("execution_quality", 0))

    return {
        "completion": round(mean(completions), 2) if completions else 0,
        "correctness": round(mean(correctnesses), 2) if correctnesses else 0,
        "execution_quality": round(mean(qualities), 2) if qualities else 0,
    }


def compute_per_step_averages(case_details: list[dict], step_names: list[str]) -> list[dict]:
    """Compute per-step averages across all cases."""
    step_scores = {name: {"comp": [], "corr": [], "qual": []} for name in step_names}

    for case in case_details:
        for step in case.get("steps", []):
            name = step.get("step", "")
            if name in step_scores:
                step_scores[name]["comp"].append(step.get("completion", 0))
                step_scores[name]["corr"].append(step.get("correctness", 0))
                step_scores[name]["qual"].append(step.get("execution_quality", 0))

    result = []
    for step_name in step_names:
        data = step_scores[step_name]
        comp_avg = round(mean(data["comp"]), 2) if data["comp"] else 0
        corr_avg = round(mean(data["corr"]), 2) if data["corr"] else 0
        qual_avg = round(mean(data["qual"]), 2) if data["qual"] else 0

        low_note = None
        if comp_avg < 1.0 or corr_avg < 1.4 or qual_avg < 1.4:
            low_note = "Below threshold"

        result.append({
            "step": step_name,
            "completion_avg": comp_avg,
            "correctness_avg": corr_avg,
            "quality_avg": qual_avg,
            "low_score_note": low_note,
        })

    return result


def compute_efficiency(case_details: list[dict]) -> dict:
    """Compute efficiency metrics from case details."""
    total_tokens_list = []
    total_time_list = []
    step_tokens = {}
    step_times = {}

    for case in case_details:
        case_tokens = 0
        case_time = 0.0
        for step in case.get("steps", []):
            metrics = step.get("metrics", {})
            tokens = metrics.get("tokens_consumed", 0) if isinstance(metrics, dict) else 0
            time_s = metrics.get("time_seconds", 0.0) if isinstance(metrics, dict) else 0.0
            case_tokens += tokens
            case_time += time_s

            step_name = step.get("step", "")
            if step_name not in step_tokens:
                step_tokens[step_name] = []
                step_times[step_name] = []
            step_tokens[step_name].append(tokens)
            step_times[step_name].append(time_s)

        if case_tokens > 0:
            total_tokens_list.append(case_tokens)
        if case_time > 0:
            total_time_list.append(case_time)

    per_step = []
    for step_name in step_tokens:
        per_step.append({
            "step": step_name,
            "avg_tokens": round(mean(step_tokens[step_name])) if step_tokens[step_name] else 0,
            "avg_time_seconds": round(mean(step_times[step_name]), 1) if step_times[step_name] else 0,
        })

    return {
        "avg_tokens_per_case": round(mean(total_tokens_list)) if total_tokens_list else 0,
        "avg_time_per_case_seconds": round(mean(total_time_list), 1) if total_time_list else 0,
        "per_step": per_step,
    }


def compute_safety(safety_findings: list[dict], total_checks: int) -> dict:
    """Compute safety metrics."""
    unsafe_count = len(safety_findings)
    unsafe_rate = unsafe_count / total_checks if total_checks > 0 else 0

    return {
        "unsafe_rate": round(unsafe_rate, 2),
        "total_checks": total_checks,
        "unsafe_count": unsafe_count,
        "findings": safety_findings,
    }


def compute_baseline_comparison(case_details: list[dict], baseline_details: list[dict]) -> dict:
    """Compare skill execution against baseline (no-skill) execution."""
    if not baseline_details:
        return {"has_baseline": False}

    baseline_map = {}
    for case in baseline_details:
        case_id = case.get("test_case_id", "")
        for step in case.get("steps", []):
            key = (case_id, step.get("step", ""))
            baseline_map[key] = step

    skill_better = 0
    skill_same = 0
    skill_worse = 0
    skill_worse_details = []

    for case in case_details:
        case_id = case.get("test_case_id", "")
        for step in case.get("steps", []):
            step_name = step.get("step", "")
            key = (case_id, step_name)
            if key not in baseline_map:
                continue

            baseline_step = baseline_map[key]
            skill_corr = step.get("correctness", 0)
            baseline_corr = baseline_step.get("correctness", 0)

            if skill_corr > baseline_corr:
                skill_better += 1
            elif skill_corr == baseline_corr:
                skill_same += 1
            else:
                skill_worse += 1
                skill_worse_details.append({
                    "step": step_name,
                    "case": case_id,
                    "skill_score": skill_corr,
                    "baseline_score": baseline_corr,
                    "reason": "Baseline produced better result",
                })

    total_compared = skill_better + skill_same + skill_worse
    return {
        "has_baseline": True,
        "total_steps_compared": total_compared,
        "skill_better_count": skill_better,
        "skill_same_count": skill_same,
        "skill_worse_count": skill_worse,
        "skill_worse_steps": skill_worse_details,
        "skill_value_summary": (
            f"Skill better in {skill_better}/{total_compared} steps"
            if total_compared > 0 else "No comparison data"
        ),
    }


def compute_stability_summary(case_details: list[dict]) -> dict:
    """Summarize scoring stability across all steps."""
    total_scored = 0
    stable_count = 0
    majority_count = 0
    uncertain_count = 0

    for case in case_details:
        for step in case.get("steps", []):
            stability = step.get("stability", {})
            if not stability:
                continue
            total_scored += 1
            statuses = [stability.get("completion", "stable"),
                        stability.get("correctness", "stable"),
                        stability.get("execution_quality", "stable")]
            if "uncertain" in statuses:
                uncertain_count += 1
            elif "majority" in statuses:
                majority_count += 1
            else:
                stable_count += 1

    return {
        "total_steps_verified": total_scored,
        "stable": stable_count,
        "majority": majority_count,
        "uncertain": uncertain_count,
        "arbitration_needed": uncertain_count > 0,
    }


def generate_report(
    skill_name: str,
    skill_version: str,
    case_details: list[dict],
    step_names: list[str],
    trigger_results: dict | None = None,
    safety_findings: list[dict] | None = None,
    total_safety_checks: int = 0,
    baseline_details: list[dict] | None = None,
    eval_mode: str = "quick",
    structure_level: str = "high",
) -> dict:
    """Generate the complete evaluation report."""

    bad_cases = identify_bad_cases(case_details)
    overall_avg = compute_overall_averages(case_details)
    per_step_avg = compute_per_step_averages(case_details, step_names)
    efficiency = compute_efficiency(case_details)
    safety = compute_safety(safety_findings or [], total_safety_checks)
    baseline = compute_baseline_comparison(case_details, baseline_details or [])
    stability = compute_stability_summary(case_details) if eval_mode == "deep" else None

    trigger = {"status": "skipped"}
    if trigger_results:
        trigger = {
            "status": "scored",
            "precision": trigger_results.get("precision", 0),
            "recall": trigger_results.get("recall", 0),
        }

    return {
        "skill_name": skill_name,
        "skill_version": skill_version,
        "eval_date": None,
        "eval_mode": eval_mode,
        "structure_level": structure_level,
        "total_cases": len(case_details),
        "bad_case_count": len(bad_cases),
        "bad_case_rate": round(len(bad_cases) / len(case_details), 2) if case_details else 0,
        "trigger": trigger,
        "overall_averages": overall_avg,
        "per_step_averages": per_step_avg,
        "efficiency": efficiency,
        "safety": safety,
        "baseline_comparison": baseline,
        "scoring_stability": stability,
        "bad_cases": bad_cases,
        "case_details": case_details,
    }


def compare_versions(report_old: dict, report_new: dict) -> dict:
    """Generate a version comparison report."""
    old_avg = report_old.get("overall_averages", {})
    new_avg = report_new.get("overall_averages", {})

    deltas = {
        "completion": round(new_avg.get("completion", 0) - old_avg.get("completion", 0), 2),
        "correctness": round(new_avg.get("correctness", 0) - old_avg.get("correctness", 0), 2),
        "execution_quality": round(new_avg.get("execution_quality", 0) - old_avg.get("execution_quality", 0), 2),
    }

    old_bad_ids = {bc["test_case_id"] for bc in report_old.get("bad_cases", [])}
    new_bad_ids = {bc["test_case_id"] for bc in report_new.get("bad_cases", [])}
    fixed = old_bad_ids - new_bad_ids
    remaining = old_bad_ids & new_bad_ids
    new_failures = new_bad_ids - old_bad_ids

    regressions = []
    old_case_map = {c["test_case_id"]: c for c in report_old.get("case_details", [])}
    new_case_map = {c["test_case_id"]: c for c in report_new.get("case_details", [])}

    for case_id, old_case in old_case_map.items():
        if case_id not in new_case_map:
            continue
        new_case = new_case_map[case_id]
        old_steps = {s["step"]: s for s in old_case.get("steps", [])}
        new_steps = {s["step"]: s for s in new_case.get("steps", [])}

        for step_name, old_step in old_steps.items():
            if step_name not in new_steps:
                continue
            new_step = new_steps[step_name]
            for metric in ("completion", "correctness", "execution_quality"):
                old_val = old_step.get(metric, 0)
                new_val = new_step.get(metric, 0)
                if new_val < old_val:
                    regressions.append({
                        "test_case_id": case_id,
                        "step": step_name,
                        "metric": metric,
                        "old_value": old_val,
                        "new_value": new_val,
                    })

    return {
        "from_version": report_old.get("skill_version", "?"),
        "to_version": report_new.get("skill_version", "?"),
        "overall_deltas": deltas,
        "bad_case_changes": {
            "fixed": list(fixed),
            "remaining": list(remaining),
            "new_failures": list(new_failures),
        },
        "bad_case_count_delta": report_new.get("bad_case_count", 0) - report_old.get("bad_case_count", 0),
        "regressions": regressions,
        "has_regressions": len(regressions) > 0,
    }


def print_report_summary(report: dict):
    """Print a terminal-formatted report summary."""
    name = report.get("skill_name", "unknown")
    version = report.get("skill_version", "?")
    mode = report.get("eval_mode", "quick")
    structure = report.get("structure_level", "?")
    total = report.get("total_cases", 0)
    bad_count = report.get("bad_case_count", 0)
    bad_rate = report.get("bad_case_rate", 0)
    avg = report.get("overall_averages", {})

    print()
    print("=" * 64)
    print(f"  SKILL EVALUATION REPORT")
    print(f"  Skill: {name}  Version: {version}  Mode: {mode}")
    print(f"  Structure level: {structure}")
    print(f"  Cases: {total}    Bad Cases: {bad_count} ({bad_rate:.0%})", end="")
    if bad_count > 0:
        print(" 🔴")
    else:
        print(" ✅")
    print("=" * 64)

    # Trigger
    trigger = report.get("trigger", {})
    if trigger.get("status") == "scored":
        print(f"  Trigger:       Precision: {trigger['precision']:.0%}  Recall: {trigger['recall']:.0%}")
    else:
        print(f"  Trigger:       SKIPPED")

    # Overall averages
    print(f"  Completion:    avg {avg.get('completion', 0):.2f}/1")
    print(f"  Correctness:   avg {avg.get('correctness', 0):.2f}/2")
    print(f"  Exec Quality:  avg {avg.get('execution_quality', 0):.2f}/2")

    # Efficiency
    eff = report.get("efficiency", {})
    print(f"  Efficiency:    avg {eff.get('avg_tokens_per_case', 0):,} tokens/case  "
          f"avg {eff.get('avg_time_per_case_seconds', 0):.1f}s/case")

    # Safety
    safety = report.get("safety", {})
    print(f"  Safety:        unsafe rate {safety.get('unsafe_rate', 0):.0%} "
          f"({safety.get('unsafe_count', 0)}/{safety.get('total_checks', 0)})")

    # Baseline
    baseline = report.get("baseline_comparison", {})
    if baseline.get("has_baseline"):
        print(f"  Baseline:      better={baseline.get('skill_better_count', 0)} "
              f"same={baseline.get('skill_same_count', 0)} "
              f"worse={baseline.get('skill_worse_count', 0)}")
        if baseline.get("skill_worse_count", 0) > 0:
            print(f"  ⚠️  SKILL WORSE THAN BASELINE in {baseline['skill_worse_count']} steps!")
    else:
        print(f"  Baseline:      NOT RUN (recommended for first eval)")

    # Stability
    stability = report.get("scoring_stability")
    if stability:
        print(f"  Stability:     stable={stability.get('stable', 0)} "
              f"majority={stability.get('majority', 0)} "
              f"uncertain={stability.get('uncertain', 0)}")
        if stability.get("arbitration_needed"):
            print(f"  ⚠️  ARBITRATION NEEDED: {stability['uncertain']} uncertain scores")

    print("=" * 64)

    # Bad Cases
    if bad_count > 0:
        print()
        print("  🔴 BAD CASES:")
        for bc in report.get("bad_cases", []):
            print(f"    {bc['test_case_id']}: {bc.get('test_case_name', '')}")
            print(f"      Step: {bc['failed_step']}")
            scores = bc.get("scores", {})
            print(f"      Completion: {scores.get('completion', '?')} | "
                  f"Correctness: {scores.get('correctness', '?')} | "
                  f"Quality: {scores.get('execution_quality', '?')}")
            if bc.get("low_score_reason"):
                reason = bc["low_score_reason"][:120]
                print(f"      Reason: {reason}")
            print()

    # Per-step table
    print("  STEP AVERAGES:")
    print(f"  {'Step':<30s} {'Comp':>6s} {'Corr':>6s} {'Qual':>6s}")
    print(f"  {'-'*30} {'-'*6} {'-'*6} {'-'*6}")
    for step in report.get("per_step_averages", []):
        comp = f"{step['completion_avg']:.2f}"
        corr = f"{step['correctness_avg']:.2f}"
        qual = f"{step['quality_avg']:.2f}"
        marker = " ⚠️" if step.get("low_score_note") else ""
        print(f"  {step['step']:<30s} {comp:>6s} {corr:>6s} {qual:>6s}{marker}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Compute evaluation report from execution results")
    parser.add_argument("results", help="Path to execution results JSON")
    parser.add_argument("--skill-name", default="unknown", help="Skill name")
    parser.add_argument("--skill-version", default="v1", help="Skill version")
    parser.add_argument("--eval-mode", default="quick", choices=["quick", "deep"], help="Evaluation mode")
    parser.add_argument("--structure-level", default="high", choices=["high", "medium", "low"])
    parser.add_argument("--baseline", default=None, help="Path to baseline results JSON")
    parser.add_argument("--output", default=None, help="Path to save report JSON")
    parser.add_argument("--compare-with", default=None, help="Path to previous report for comparison")
    parser.add_argument("--quiet", action="store_true", help="Suppress terminal output")
    args = parser.parse_args()

    results_data = json.loads(Path(args.results).read_text())

    case_details = results_data.get("case_details", [])
    step_names = results_data.get("step_names", [])
    trigger_results = results_data.get("trigger", None)
    safety_findings = results_data.get("safety_findings", [])
    total_safety_checks = results_data.get("total_safety_checks", 0)

    baseline_details = None
    if args.baseline:
        baseline_data = json.loads(Path(args.baseline).read_text())
        baseline_details = baseline_data.get("case_details", [])

    report = generate_report(
        skill_name=args.skill_name,
        skill_version=args.skill_version,
        case_details=case_details,
        step_names=step_names,
        trigger_results=trigger_results,
        safety_findings=safety_findings,
        total_safety_checks=total_safety_checks,
        baseline_details=baseline_details,
        eval_mode=args.eval_mode,
        structure_level=args.structure_level,
    )

    if not args.quiet:
        print_report_summary(report)

    if args.compare_with:
        old_report = json.loads(Path(args.compare_with).read_text())
        comparison = compare_versions(old_report, report)
        report["version_comparison"] = comparison

        if not args.quiet:
            print("\n  VERSION COMPARISON:")
            deltas = comparison["overall_deltas"]
            print(f"    Completion:  {deltas['completion']:+.2f}")
            print(f"    Correctness: {deltas['correctness']:+.2f}")
            print(f"    Quality:     {deltas['execution_quality']:+.2f}")
            print(f"    Bad Cases:   {comparison['bad_case_count_delta']:+d}")
            if comparison["has_regressions"]:
                print(f"    ⚠️  REGRESSIONS DETECTED: {len(comparison['regressions'])}")
            print()

    output_json = json.dumps(report, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output_json)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
