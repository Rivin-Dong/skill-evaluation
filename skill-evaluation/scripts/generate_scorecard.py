#!/usr/bin/env python3
"""Generate a standalone HTML evaluation report.

Reads report.json to produce a single self-contained HTML file with inline styles.
Report structure follows the methodology:
1. Bad Cases (first, most prominent)
2. Overview panel (averages)
3. Step scores table
4. Efficiency details
5. Safety details
6. Full case details
"""

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _esc(value) -> str:
    """Escape untrusted values for safe HTML insertion."""
    if value is None:
        return "—"
    return html.escape(str(value))


def generate_html(report: dict) -> str:
    """Generate complete HTML report from report data."""
    skill_name = report.get("skill_name", "unknown")
    skill_version = report.get("skill_version", "?")
    eval_date = report.get("eval_date", datetime.now().strftime("%Y-%m-%d"))
    total_cases = report.get("total_cases", 0)
    bad_case_count = report.get("bad_case_count", 0)
    bad_case_rate = report.get("bad_case_rate", 0)
    overall_avg = report.get("overall_averages", {})
    per_step_avg = report.get("per_step_averages", [])
    efficiency = report.get("efficiency", {})
    safety = report.get("safety", {})
    trigger = report.get("trigger", {})
    bad_cases = report.get("bad_cases", [])
    case_details = report.get("case_details", [])
    comparison = report.get("version_comparison", None)

    # Build HTML
    html_parts = []
    html_parts.append(_header(skill_name, skill_version, eval_date))
    html_parts.append(_overview_panel(
        skill_name, skill_version, eval_date,
        total_cases, bad_case_count, bad_case_rate,
        overall_avg, trigger, efficiency, safety
    ))

    if bad_cases:
        html_parts.append(_bad_cases_section(bad_cases, bad_case_count, bad_case_rate))

    # Scoring stability (Deep Eval)
    stability = report.get("scoring_stability")
    if stability:
        html_parts.append(_stability_section(stability))

    if comparison:
        html_parts.append(_comparison_section(comparison))

    html_parts.append(_step_scores_section(per_step_avg))

    # Baseline comparison
    baseline = report.get("baseline_comparison", {})
    if baseline.get("has_baseline"):
        html_parts.append(_baseline_section(baseline))

    html_parts.append(_efficiency_section(efficiency))
    html_parts.append(_safety_section(safety))

    if case_details:
        html_parts.append(_case_details_section(case_details))

    html_parts.append(_footer())

    return "\n".join(html_parts)


def _header(skill_name: str, version: str, date: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Skill Eval Report - {_esc(skill_name)} {_esc(version)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 20px; background: #f8fafc; color: #1e293b; }}
.container {{ max-width: 900px; margin: 0 auto; }}
h1 {{ color: #0f172a; margin-bottom: 4px; }}
h2 {{ color: #334155; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-top: 32px; }}
h3 {{ color: #475569; }}
.subtitle {{ color: #64748b; margin-bottom: 24px; }}
.panel {{ background: white; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.bad-case {{ background: #fef2f2; border-left: 4px solid #ef4444; }}
.bad-case h3 {{ color: #dc2626; }}
.metric {{ display: inline-block; margin-right: 24px; margin-bottom: 8px; }}
.metric-label {{ color: #64748b; font-size: 12px; text-transform: uppercase; }}
.metric-value {{ font-size: 24px; font-weight: 600; color: #0f172a; }}
.metric-value.warn {{ color: #f59e0b; }}
.metric-value.bad {{ color: #ef4444; }}
.metric-value.good {{ color: #10b981; }}
table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
th {{ background: #f1f5f9; text-align: left; padding: 8px 12px; font-size: 13px; color: #475569; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 14px; }}
tr:hover {{ background: #f8fafc; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }}
.tag-red {{ background: #fee2e2; color: #dc2626; }}
.tag-orange {{ background: #ffedd5; color: #ea580c; }}
.tag-yellow {{ background: #fef3c7; color: #d97706; }}
.tag-green {{ background: #d1fae5; color: #059669; }}
.reason {{ background: #f1f5f9; border-radius: 4px; padding: 8px 12px; margin-top: 8px; font-size: 13px; color: #475569; white-space: pre-wrap; }}
.comparison-positive {{ color: #059669; }}
.comparison-negative {{ color: #dc2626; }}
.regression-banner {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; padding: 12px; margin: 12px 0; }}
</style>
</head>
<body>
<div class="container">
"""


def _overview_panel(skill_name, version, date, total, bad_count, bad_rate,
                    avg, trigger, efficiency, safety) -> str:
    bad_class = "bad" if bad_count > 0 else "good"
    trigger_html = ""
    if trigger.get("status") == "scored":
        trigger_html = f"""
        <div class="metric">
            <div class="metric-label">Precision</div>
            <div class="metric-value">{trigger['precision']:.0%}</div>
        </div>
        <div class="metric">
            <div class="metric-label">Recall</div>
            <div class="metric-value">{trigger['recall']:.0%}</div>
        </div>"""
    else:
        trigger_html = '<div class="metric"><div class="metric-label">Trigger</div><div class="metric-value">SKIPPED</div></div>'

    return f"""
<h1>Skill Evaluation Report</h1>
<p class="subtitle">{_esc(skill_name)} &middot; {_esc(version)} &middot; {_esc(date)}</p>

<div class="panel">
    <div class="metric">
        <div class="metric-label">Test Cases</div>
        <div class="metric-value">{total}</div>
    </div>
    <div class="metric">
        <div class="metric-label">Bad Cases</div>
        <div class="metric-value {bad_class}">{bad_count} ({bad_rate:.0%})</div>
    </div>
    <div class="metric">
        <div class="metric-label">Completion Avg</div>
        <div class="metric-value">{avg.get('completion', 0):.2f}/1</div>
    </div>
    <div class="metric">
        <div class="metric-label">Correctness Avg</div>
        <div class="metric-value">{avg.get('correctness', 0):.2f}/2</div>
    </div>
    <div class="metric">
        <div class="metric-label">Exec Quality Avg</div>
        <div class="metric-value">{avg.get('execution_quality', 0):.2f}/2</div>
    </div>
    {trigger_html}
    <div class="metric">
        <div class="metric-label">Avg Tokens/Case</div>
        <div class="metric-value">{efficiency.get('avg_tokens_per_case', 0):,}</div>
    </div>
    <div class="metric">
        <div class="metric-label">Avg Time/Case</div>
        <div class="metric-value">{efficiency.get('avg_time_per_case_seconds', 0):.1f}s</div>
    </div>
    <div class="metric">
        <div class="metric-label">Unsafe Rate</div>
        <div class="metric-value">{safety.get('unsafe_rate', 0):.0%}</div>
    </div>
</div>
"""


def _bad_cases_section(bad_cases: list, count: int, rate: float) -> str:
    out = f'<h2>🔴 Bad Cases ({count}, {rate:.0%} of total)</h2>\n'
    for bc in bad_cases:
        scores = bc.get("scores", {})
        out += f"""
<div class="panel bad-case">
    <h3>{_esc(bc.get('test_case_id', '?'))} — {_esc(bc.get('test_case_name', ''))}</h3>
    <p><strong>Failed Step:</strong> {_esc(bc.get('failed_step', '?'))}</p>
    <p>
        <span class="tag tag-{'red' if scores.get('completion', 0) == 0 else 'green'}">Completion: {_esc(scores.get('completion', '?'))}</span>
        <span class="tag tag-{'red' if scores.get('correctness', 0) == 0 else 'yellow' if scores.get('correctness', 0) == 1 else 'green'}">Correctness: {_esc(scores.get('correctness', '?'))}</span>
        <span class="tag tag-{'red' if scores.get('execution_quality', 0) == 0 else 'yellow' if scores.get('execution_quality', 0) == 1 else 'green'}">Quality: {_esc(scores.get('execution_quality', '?'))}</span>
    </p>
    <p><strong>Expected:</strong> {_esc(bc.get('expected', '—'))}</p>
    <p><strong>Actual:</strong> {_esc(bc.get('actual', '—'))}</p>
    <div class="reason">{_esc(bc.get('low_score_reason', '—'))}</div>
</div>
"""
    return out


def _comparison_section(comparison: dict) -> str:
    deltas = comparison.get("overall_deltas", {})
    out = f"""
<h2>Version Comparison: {_esc(comparison.get('from_version', '?'))} → {_esc(comparison.get('to_version', '?'))}</h2>
<div class="panel">
    <table>
        <tr><th>Metric</th><th>Delta</th></tr>
        <tr><td>Completion</td><td class="{'comparison-positive' if deltas.get('completion', 0) >= 0 else 'comparison-negative'}">{deltas.get('completion', 0):+.2f}</td></tr>
        <tr><td>Correctness</td><td class="{'comparison-positive' if deltas.get('correctness', 0) >= 0 else 'comparison-negative'}">{deltas.get('correctness', 0):+.2f}</td></tr>
        <tr><td>Exec Quality</td><td class="{'comparison-positive' if deltas.get('execution_quality', 0) >= 0 else 'comparison-negative'}">{deltas.get('execution_quality', 0):+.2f}</td></tr>
        <tr><td>Bad Cases</td><td class="{'comparison-positive' if comparison.get('bad_case_count_delta', 0) <= 0 else 'comparison-negative'}">{comparison.get('bad_case_count_delta', 0):+d}</td></tr>
    </table>
"""
    if comparison.get("has_regressions"):
        out += '<div class="regression-banner"><strong>⚠️ Regressions detected:</strong><ul>'
        for reg in comparison.get("regressions", []):
            out += f'<li>{_esc(reg.get("test_case_id", "?"))} {_esc(reg.get("step", "?"))}: {_esc(reg.get("metric", "?"))} {_esc(reg.get("old_value", "?"))} → {_esc(reg.get("new_value", "?"))}</li>'
        out += "</ul></div>"

    changes = comparison.get("bad_case_changes", {})
    if changes.get("fixed"):
        out += f'<p><strong>Fixed:</strong> {_esc(", ".join(changes["fixed"]))}</p>'
    if changes.get("remaining"):
        out += f'<p><strong>Remaining:</strong> {_esc(", ".join(changes["remaining"]))}</p>'

    out += "</div>\n"
    return out


def _step_scores_section(per_step_avg: list) -> str:
    out = "<h2>Step Scores</h2>\n<div class=\"panel\"><table>\n"
    out += "<tr><th>Step</th><th>Completion (avg/1)</th><th>Correctness (avg/2)</th><th>Exec Quality (avg/2)</th><th>Note</th></tr>\n"
    for step in per_step_avg:
        note = step.get("low_score_note") or "—"
        out += f"<tr><td>{_esc(step.get('step', '?'))}</td><td>{step['completion_avg']:.2f}</td><td>{step['correctness_avg']:.2f}</td><td>{step['quality_avg']:.2f}</td><td>{_esc(note)}</td></tr>\n"
    out += "</table></div>\n"
    return out


def _efficiency_section(efficiency: dict) -> str:
    out = "<h2>Efficiency</h2>\n<div class=\"panel\">\n"
    out += f"<p><strong>Average per case:</strong> {efficiency.get('avg_tokens_per_case', 0):,} tokens, {efficiency.get('avg_time_per_case_seconds', 0):.1f}s</p>\n"
    out += "<table><tr><th>Step</th><th>Avg Tokens</th><th>Avg Time</th></tr>\n"
    for step in efficiency.get("per_step", []):
        out += f"<tr><td>{_esc(step.get('step', '?'))}</td><td>{step.get('avg_tokens', 0):,}</td><td>{step.get('avg_time_seconds', 0):.1f}s</td></tr>\n"
    out += "</table></div>\n"
    return out


def _safety_section(safety: dict) -> str:
    out = "<h2>Safety</h2>\n<div class=\"panel\">\n"
    out += f"<p><strong>Unsafe rate:</strong> {safety.get('unsafe_rate', 0):.0%} ({safety.get('unsafe_count', 0)}/{safety.get('total_checks', 0)} checks failed)</p>\n"
    findings = safety.get("findings", [])
    if findings:
        out += "<table><tr><th>Severity</th><th>Finding</th><th>Location</th></tr>\n"
        for f in findings:
            sev = f.get("severity", "?")
            tag_class = {"CRITICAL": "tag-red", "HIGH": "tag-orange", "MEDIUM": "tag-yellow", "LOW": "tag-green"}.get(sev, "")
            out += f"<tr><td><span class=\"tag {tag_class}\">{_esc(sev)}</span></td><td>{_esc(f.get('description', ''))}</td><td>{_esc(f.get('location', ''))}</td></tr>\n"
        out += "</table>\n"
    else:
        out += "<p>No safety findings. ✅</p>\n"
    out += "</div>\n"
    return out


def _stability_section(stability: dict) -> str:
    """Render scoring stability summary (Deep Eval mode)."""
    html = "<h2>Scoring Stability</h2>\n<div class=\"panel\">\n"
    total = stability.get("total_steps_verified", 0)
    stable = stability.get("stable", 0)
    majority = stability.get("majority", 0)
    uncertain = stability.get("uncertain", 0)

    html += f"<p><strong>Steps verified:</strong> {total}</p>\n"
    html += "<table><tr><th>Status</th><th>Count</th><th>Meaning</th></tr>\n"
    html += f"<tr><td><span class=\"tag tag-green\">Stable</span></td><td>{stable}</td><td>3/3 scores identical</td></tr>\n"
    html += f"<tr><td><span class=\"tag tag-yellow\">Majority</span></td><td>{majority}</td><td>2/3 scores agree</td></tr>\n"
    html += f"<tr><td><span class=\"tag tag-red\">Uncertain</span></td><td>{uncertain}</td><td>All 3 differ — needs arbitration</td></tr>\n"
    html += "</table>\n"

    if stability.get("arbitration_needed"):
        html += "<div class=\"regression-banner\"><strong>⚠️ Human arbitration needed for uncertain scores</strong></div>\n"

    html += "</div>\n"
    return html


def _baseline_section(baseline: dict) -> str:
    """Render baseline comparison section."""
    out = "<h2>Baseline Comparison (Skill vs Bare Model)</h2>\n<div class=\"panel\">\n"
    better = baseline.get("skill_better_count", 0)
    same = baseline.get("skill_same_count", 0)
    worse = baseline.get("skill_worse_count", 0)
    total = baseline.get("total_steps_compared", 0)

    out += f"<p><strong>Total steps compared:</strong> {total}</p>\n"
    out += "<table><tr><th>Result</th><th>Count</th><th>Percentage</th></tr>\n"
    pct_b = f"{better/total:.0%}" if total > 0 else "0%"
    pct_s = f"{same/total:.0%}" if total > 0 else "0%"
    pct_w = f"{worse/total:.0%}" if total > 0 else "0%"
    out += f"<tr><td><span class=\"tag tag-green\">Skill Better</span></td><td>{better}</td><td>{pct_b}</td></tr>\n"
    out += f"<tr><td>Skill Same</td><td>{same}</td><td>{pct_s}</td></tr>\n"
    out += f"<tr><td><span class=\"tag tag-red\">Skill Worse</span></td><td>{worse}</td><td>{pct_w}</td></tr>\n"
    out += "</table>\n"

    if worse > 0:
        out += "<div class=\"regression-banner\"><strong>⚠️ Skill performs WORSE than bare model in some steps:</strong><ul>\n"
        for item in baseline.get("skill_worse_steps", []):
            out += f"<li>{_esc(item.get('case', '?'))} / {_esc(item.get('step', '?'))}: {_esc(item.get('reason', ''))}</li>\n"
        out += "</ul></div>\n"

    out += f"<p><strong>Summary:</strong> {_esc(baseline.get('skill_value_summary', ''))}</p>\n"
    out += "</div>\n"
    return out


def _case_details_section(case_details: list) -> str:
    out = "<h2>Full Case Details</h2>\n"
    for case in case_details:
        out += f"<div class=\"panel\"><h3>{_esc(case.get('test_case_id', '?'))} — {_esc(case.get('name', ''))}</h3>\n"
        out += "<table><tr><th>Step</th><th>Comp</th><th>Corr</th><th>Qual</th><th>Expected</th><th>Actual</th></tr>\n"
        for step in case.get("steps", []):
            comp = step.get("completion", "?")
            corr = step.get("correctness", "?")
            qual = step.get("execution_quality", "?")
            expected = str(step.get("expected", "—"))[:80]
            actual = str(step.get("actual", "—"))[:80]
            out += f"<tr><td>{_esc(step.get('step', '?'))}</td><td>{_esc(comp)}</td><td>{_esc(corr)}</td><td>{_esc(qual)}</td><td>{_esc(expected)}</td><td>{_esc(actual)}</td></tr>\n"
            if step.get("low_score_reason"):
                out += f"<tr><td colspan=\"6\"><div class=\"reason\">{_esc(step['low_score_reason'])}</div></td></tr>\n"
        out += "</table></div>\n"
    return out


def _footer() -> str:
    return """
</div>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate HTML evaluation report")
    parser.add_argument("report", help="Path to report.json")
    parser.add_argument("--output", default=None, help="Output HTML path")
    args = parser.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    html = generate_html(report)

    if args.output:
        Path(args.output).write_text(html, encoding="utf-8")
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(html)


if __name__ == "__main__":
    main()
