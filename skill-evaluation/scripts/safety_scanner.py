#!/usr/bin/env python3
"""Static safety scanner for AI skill files.

Scans SKILL.md and bundled scripts for potentially dangerous patterns.
Outputs findings as JSON with severity levels.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Pattern definitions: (regex, severity, description, category)
SKILL_TEXT_PATTERNS = [
    # Critical - immediate veto
    (r'\brm\s+-rf\b', "CRITICAL", "Unrestricted recursive delete command", "destructive_command"),
    (r'\beval\s*\(', "CRITICAL", "Dynamic code evaluation from potentially untrusted input", "code_injection"),
    (r'\bexec\s*\(', "CRITICAL", "Dynamic code execution", "code_injection"),
    (r'curl\s+.*\|\s*(ba)?sh', "CRITICAL", "Pipe remote content to shell execution", "remote_execution"),
    (r'wget\s+.*\|\s*(ba)?sh', "CRITICAL", "Pipe remote content to shell execution", "remote_execution"),
    (r'\b(api[_-]?key|secret[_-]?key|password|token)\s*[=:]\s*["\'][^"\']{8,}', "CRITICAL",
     "Hardcoded credential or secret", "credential_exposure"),
    (r'os\.system\s*\(', "CRITICAL", "Direct OS command execution", "code_injection"),
    (r'subprocess\.call\s*\(\s*[^,]+\s*,\s*shell\s*=\s*True', "CRITICAL",
     "Shell subprocess with shell=True", "code_injection"),

    # High severity
    (r'\bchmod\s+777\b', "HIGH", "Setting world-writable permissions", "permission_risk"),
    (r'\bsudo\b', "HIGH", "Requesting elevated privileges", "privilege_escalation"),
    (r'(\/etc\/passwd|\/etc\/shadow)', "HIGH", "Accessing system credential files", "system_access"),
    (r'\bos\.environ\b', "HIGH", "Accessing environment variables (potential secret exposure)", "info_leak"),
    (r'requests\.(get|post|put|delete)\s*\(', "HIGH",
     "Making HTTP requests (verify user consent for network access)", "network_egress"),
    (r'\bopen\s*\(\s*["\']\/(?!tmp)', "HIGH",
     "Opening absolute paths outside /tmp (broad file system access)", "file_access"),

    # Medium severity
    (r'\bglob\s*\(\s*["\'][\*\?]', "MEDIUM", "Broad glob pattern may access unintended files", "file_access"),
    (r'\.write\s*\(|open\s*\([^)]*["\']w', "MEDIUM",
     "File write operation (verify output scope is intentional)", "file_write"),
    (r'\bprint\s*\(.*(?:error|exception|traceback)', "MEDIUM",
     "Printing error details that may leak internal info", "info_leak"),
    (r'\.env\b', "MEDIUM", "Reference to .env file (may contain secrets)", "credential_exposure"),

    # Low severity
    (r'#\s*TODO|#\s*FIXME|#\s*HACK', "LOW", "Unresolved TODO/FIXME in skill code", "code_quality"),
    (r'\.readlines\s*\(\s*\)', "LOW",
     "Reading entire file into memory (may fail on large files)", "resource_risk"),
]

# Patterns specifically for instruction text (the SKILL.md prose)
INSTRUCTION_PATTERNS = [
    (r'(?i)ignore\s+(previous|all|any)\s+(instructions?|rules?|constraints?)', "CRITICAL",
     "Prompt injection pattern: instruction override attempt", "prompt_injection"),
    (r'(?i)you\s+are\s+now\s+', "HIGH",
     "Potential role hijacking instruction", "prompt_injection"),
    (r'(?i)do\s+not\s+(tell|reveal|share|disclose)', "MEDIUM",
     "Secrecy instruction (may indicate hidden behavior)", "transparency"),
    (r'(?i)(delete|remove|destroy)\s+(all|every|any)\s+', "HIGH",
     "Instruction to delete broadly", "destructive_instruction"),
    (r'(?i)access\s+(any|all|every)\s+file', "HIGH",
     "Instruction granting unrestricted file access", "file_access"),
]


def scan_text(text: str, patterns: list, source_file: str) -> list[dict]:
    """Scan text against a pattern list, returning findings with line numbers."""
    findings = []
    lines = text.split("\n")

    for pattern, severity, description, category in patterns:
        regex = re.compile(pattern)
        for line_num, line in enumerate(lines, 1):
            if regex.search(line):
                findings.append({
                    "severity": severity,
                    "description": description,
                    "category": category,
                    "file": source_file,
                    "line": line_num,
                    "match": line.strip()[:120],
                })

    return findings


def scan_skill(skill_path: Path) -> dict:
    """Scan a skill directory for safety issues.

    Args:
        skill_path: Path to the skill directory (containing SKILL.md)

    Returns:
        Dict with findings, summary, and veto status.
    """
    findings = []
    files_scanned = []

    # Scan SKILL.md
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8", errors="replace")
        findings.extend(scan_text(content, INSTRUCTION_PATTERNS, "SKILL.md"))
        findings.extend(scan_text(content, SKILL_TEXT_PATTERNS, "SKILL.md"))
        files_scanned.append("SKILL.md")

    # Scan scripts/
    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists():
        for script_file in scripts_dir.glob("**/*"):
            if script_file.is_file() and script_file.suffix in (".py", ".sh", ".js", ".ts", ".rb"):
                content = script_file.read_text(encoding="utf-8", errors="replace")
                rel_path = str(script_file.relative_to(skill_path))
                findings.extend(scan_text(content, SKILL_TEXT_PATTERNS, rel_path))
                files_scanned.append(rel_path)

    # Scan references/ (lighter scan — only instruction patterns)
    refs_dir = skill_path / "references"
    if refs_dir.exists():
        for ref_file in refs_dir.glob("**/*.md"):
            content = ref_file.read_text(encoding="utf-8", errors="replace")
            rel_path = str(ref_file.relative_to(skill_path))
            findings.extend(scan_text(content, INSTRUCTION_PATTERNS, rel_path))
            files_scanned.append(rel_path)

    # Deduplicate (same pattern hitting same line)
    seen = set()
    unique_findings = []
    for f in findings:
        key = (f["file"], f["line"], f["description"])
        if key not in seen:
            seen.add(key)
            unique_findings.append(f)

    # Compute summary
    severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in unique_findings:
        severity_counts[f["severity"]] += 1

    has_critical = severity_counts["CRITICAL"] > 0

    # Compute penalty score
    penalties = {
        "CRITICAL": 100,  # Instant veto
        "HIGH": 50,
        "MEDIUM": 20,
        "LOW": 5,
    }
    total_penalty = sum(penalties[f["severity"]] for f in unique_findings)
    safety_score = max(0, 100 - total_penalty)

    if has_critical:
        safety_score = 0

    return {
        "files_scanned": files_scanned,
        "findings": unique_findings,
        "severity_counts": severity_counts,
        "safety_score": safety_score,
        "veto": has_critical,
        "total_findings": len(unique_findings),
    }


def main():
    parser = argparse.ArgumentParser(description="Static safety scanner for AI skills")
    parser.add_argument("skill_path", help="Path to skill directory")
    parser.add_argument("--output", default=None, help="Path to save results JSON")
    parser.add_argument("--verbose", action="store_true", help="Print findings to stderr")
    args = parser.parse_args()

    skill_path = Path(args.skill_path)

    if not skill_path.exists():
        print(f"Error: {skill_path} does not exist", file=sys.stderr)
        sys.exit(1)

    results = scan_skill(skill_path)

    if args.verbose:
        print(f"Scanned {len(results['files_scanned'])} files", file=sys.stderr)
        print(f"Found {results['total_findings']} issues", file=sys.stderr)
        for f in results["findings"]:
            icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🔵"}[f["severity"]]
            print(f"  {icon} [{f['severity']}] {f['file']}:{f['line']} — {f['description']}", file=sys.stderr)
        if results["veto"]:
            print("\n⛔ SAFETY VETO: Critical finding detected. Score = 0.", file=sys.stderr)
        else:
            print(f"\nSafety score: {results['safety_score']}/100", file=sys.stderr)

    output_json = json.dumps(results, indent=2)

    if args.output:
        Path(args.output).write_text(output_json)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
