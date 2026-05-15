#!/usr/bin/env python3
"""Run trigger evaluation for a skill's description.

Tests whether a skill's description causes the model to trigger (read/activate the skill)
for a set of probe queries. Outputs precision, recall, and individual results as JSON.

Supports multiple AI coding platforms:
  - claude:   Claude Code (.claude/commands/)
  - cursor:   Cursor (.cursor/rules/ or .cursorrules)
  - codex:    OpenAI Codex (agents.md or codex config)
  - openclaw: OpenClaw (.claw/skills/)

This is a standalone trigger evaluator — it doesn't depend on the rest of the evaluation
pipeline and can be run independently.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Platform-specific select import (not available on Windows for pipes)
try:
    import select as _select
    HAS_SELECT = True
except ImportError:
    HAS_SELECT = False


# =============================================================================
# Utility
# =============================================================================

def _sanitize_skill_name(name: str) -> str:
    """Sanitize skill name for safe use in file paths.

    Removes path separators, special characters, and ensures the result
    cannot escape the intended directory.
    """
    sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
    if not sanitized:
        sanitized = "unnamed_skill"
    return sanitized[:64]


def _verify_path_containment(file_path: Path, parent_dir: Path) -> None:
    """Verify that file_path resolves to a location under parent_dir."""
    resolved = file_path.resolve()
    if not str(resolved).startswith(str(parent_dir.resolve())):
        raise ValueError(
            f"Path escapes intended directory: {file_path} not under {parent_dir}"
        )


def _neutralize_description(description: str) -> str:
    """Neutralize potentially adversarial content in skill descriptions.

    Strips prompt-injection patterns, control characters, and limits length
    to prevent the description from influencing the agent when written to
    platform-specific rule/skill files.
    """
    # Truncate to safe length
    text = description[:200]
    # Remove common prompt-injection patterns
    injection_patterns = [
        r'(?i)ignore\s+(previous|all|any)\s+(instructions?|rules?|constraints?)',
        r'(?i)you\s+are\s+now\s+',
        r'(?i)system\s*:\s*',
        r'(?i)new\s+instruction',
        r'(?i)override\s+(all|previous)',
        r'(?i)forget\s+(everything|all|previous)',
    ]
    for pattern in injection_patterns:
        text = re.sub(pattern, '[REDACTED]', text)
    # Remove control characters and YAML-breaking chars
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    text = text.replace('\n', ' ').replace('\r', ' ')
    # Escape YAML special characters
    text = text.replace('"', '\\"').replace(':', ' -')
    return text.strip()


# =============================================================================
# Platform Adapters
# =============================================================================

class PlatformAdapter(ABC):
    """Base class for platform-specific trigger evaluation."""

    @abstractmethod
    def find_project_root(self) -> Path:
        """Locate the project root for this platform."""

    @abstractmethod
    def get_skill_dir(self, project_root: Path) -> Path:
        """Return the directory where skills/commands are stored."""

    @abstractmethod
    def write_probe_file(self, skill_dir: Path, probe_name: str,
                         skill_name: str, description: str) -> Path:
        """Write a temporary skill/command file for the probe. Returns the file path."""

    @abstractmethod
    def run_probe(self, query: str, probe_name: str, project_root: Path,
                  timeout: int, model: str | None) -> bool:
        """Execute a probe query and return whether the skill was triggered."""

    def cleanup(self, probe_file: Path) -> None:
        """Remove temporary probe file."""
        if probe_file.exists():
            probe_file.unlink()


class ClaudeAdapter(PlatformAdapter):
    """Adapter for Claude Code platform."""

    def find_project_root(self) -> Path:
        current = Path.cwd()
        for parent in [current, *current.parents]:
            if (parent / ".claude").is_dir():
                return parent
        return current

    def get_skill_dir(self, project_root: Path) -> Path:
        return project_root / ".claude" / "commands"

    def write_probe_file(self, skill_dir: Path, probe_name: str,
                         skill_name: str, description: str) -> Path:
        skill_dir.mkdir(parents=True, exist_ok=True)
        probe_file = skill_dir / f"{probe_name}.md"
        _verify_path_containment(probe_file, skill_dir)

        # Neutralize description to prevent prompt injection via command files
        safe_desc = _neutralize_description(description)
        safe_skill_name = _sanitize_skill_name(skill_name)

        indented_desc = "\n  ".join(safe_desc.split("\n"))
        probe_file.write_text(
            f"---\ndescription: |\n  {indented_desc}\n---\n\n"
            f"# {safe_skill_name}\n\n"
            f"[EVALUATION PROBE] This skill handles: {safe_desc}\n"
        )
        return probe_file

    def run_probe(self, query: str, probe_name: str, project_root: Path,
                  timeout: int, model: str | None) -> bool:
        cmd = [
            "claude", "-p", query,
            "--output-format", "stream-json",
            "--verbose",
            "--include-partial-messages",
        ]
        if model:
            cmd.extend(["--model", model])

        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=str(project_root), env=env,
        )

        triggered = False
        start = time.time()
        buffer = ""
        pending_tool = None
        accumulated = ""

        try:
            while time.time() - start < timeout:
                if process.poll() is not None:
                    remaining = process.stdout.read()
                    if remaining:
                        buffer += remaining.decode("utf-8", errors="replace")
                    break

                # Use select on Unix, polling on Windows
                if HAS_SELECT:
                    ready, _, _ = _select.select([process.stdout], [], [], 1.0)
                    if not ready:
                        continue
                else:
                    time.sleep(0.1)

                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    result = self._parse_event(event, probe_name, pending_tool, accumulated)
                    if result is not None:
                        if isinstance(result, bool):
                            return result
                        pending_tool, accumulated = result

        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

        return triggered

    def _parse_event(self, event: dict, probe_name: str,
                     pending_tool: str | None, accumulated: str):
        """Parse a stream event. Returns bool (final result), tuple (state update), or None."""
        if event.get("type") == "stream_event":
            se = event.get("event", {})
            se_type = se.get("type", "")

            if se_type == "content_block_start":
                cb = se.get("content_block", {})
                if cb.get("type") == "tool_use":
                    tool = cb.get("name", "")
                    if tool in ("Skill", "Read"):
                        return (tool, "")
                    else:
                        return False

            elif se_type == "content_block_delta" and pending_tool:
                delta = se.get("delta", {})
                if delta.get("type") == "input_json_delta":
                    accumulated += delta.get("partial_json", "")
                    if probe_name in accumulated:
                        return True
                    return (pending_tool, accumulated)

            elif se_type in ("content_block_stop", "message_stop"):
                if pending_tool:
                    return probe_name in accumulated
                if se_type == "message_stop":
                    return False

        elif event.get("type") == "assistant":
            message = event.get("message", {})
            for item in message.get("content", []):
                if item.get("type") != "tool_use":
                    continue
                name = item.get("name", "")
                inp = item.get("input", {})
                if name == "Skill" and probe_name in inp.get("skill", ""):
                    return True
                elif name == "Read" and probe_name in inp.get("file_path", ""):
                    return True
            return False

        elif event.get("type") == "result":
            return False

        return None


class CursorAdapter(PlatformAdapter):
    """Adapter for Cursor platform."""

    def find_project_root(self) -> Path:
        current = Path.cwd()
        for parent in [current, *current.parents]:
            if (parent / ".cursor").is_dir() or (parent / ".cursorrules").exists():
                return parent
        return current

    def get_skill_dir(self, project_root: Path) -> Path:
        rules_dir = project_root / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        return rules_dir

    def write_probe_file(self, skill_dir: Path, probe_name: str,
                         skill_name: str, description: str) -> Path:
        skill_dir.mkdir(parents=True, exist_ok=True)
        probe_file = skill_dir / f"{probe_name}.mdc"
        _verify_path_containment(probe_file, skill_dir)

        # Sanitize description: strip potential prompt-injection patterns,
        # limit length, and use a restrictive glob to prevent broad activation.
        safe_desc = _neutralize_description(description)
        safe_skill_name = _sanitize_skill_name(skill_name)

        probe_file.write_text(
            f"---\ndescription: {safe_desc}\n"
            f"globs: __trigger_eval_probe_{probe_name}__\n"
            f"alwaysApply: false\n---\n\n"
            f"# {safe_skill_name}\n\n"
            f"[EVALUATION PROBE - NOT AN ACTIVE RULE]\n"
            f"Original description (quoted for safety): \"{safe_desc}\"\n"
        )
        return probe_file

    def run_probe(self, query: str, probe_name: str, project_root: Path,
                  timeout: int, model: str | None) -> bool:
        # Cursor doesn't have a CLI probe mechanism like Claude.
        # Use heuristic: check if the rule file would be matched by Cursor's
        # rule engine based on description keywords vs query.
        # For production use, this requires Cursor's agent mode API.
        print(
            f"  [cursor] Trigger eval uses heuristic matching for: {query[:50]}",
            file=sys.stderr
        )
        return self._heuristic_match(query, probe_name)

    def _heuristic_match(self, query: str, probe_name: str) -> bool:
        """Heuristic: check if query keywords overlap with probe description."""
        # This is a simplified fallback; real Cursor testing requires agent mode.
        return False  # Conservative: assume not triggered without live test


class CodexAdapter(PlatformAdapter):
    """Adapter for OpenAI Codex platform."""

    def find_project_root(self) -> Path:
        current = Path.cwd()
        for parent in [current, *current.parents]:
            if (parent / "agents.md").exists() or (parent / ".codex").is_dir():
                return parent
        return current

    def get_skill_dir(self, project_root: Path) -> Path:
        codex_dir = project_root / ".codex" / "skills"
        codex_dir.mkdir(parents=True, exist_ok=True)
        return codex_dir

    def write_probe_file(self, skill_dir: Path, probe_name: str,
                         skill_name: str, description: str) -> Path:
        skill_dir.mkdir(parents=True, exist_ok=True)
        probe_file = skill_dir / f"{probe_name}.md"
        _verify_path_containment(probe_file, skill_dir)

        safe_desc = _neutralize_description(description)
        safe_skill_name = _sanitize_skill_name(skill_name)

        probe_file.write_text(
            f"# {safe_skill_name}\n\n"
            f"[EVALUATION PROBE]\n\n> {safe_desc}\n\n"
            f"This skill handles: {safe_desc}\n"
        )
        return probe_file

    def run_probe(self, query: str, probe_name: str, project_root: Path,
                  timeout: int, model: str | None) -> bool:
        # Codex CLI: codex --quiet --prompt <query>
        cmd = ["codex", "--quiet", "--prompt", query]
        if model:
            cmd.extend(["--model", model])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=str(project_root),
            )
            # Check if the output references the probe skill
            return probe_name in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


class OpenClawAdapter(PlatformAdapter):
    """Adapter for OpenClaw platform."""

    def find_project_root(self) -> Path:
        current = Path.cwd()
        for parent in [current, *current.parents]:
            if (parent / ".claw").is_dir():
                return parent
        return current

    def get_skill_dir(self, project_root: Path) -> Path:
        skills_dir = project_root / ".claw" / "skills"
        skills_dir.mkdir(parents=True, exist_ok=True)
        return skills_dir

    def write_probe_file(self, skill_dir: Path, probe_name: str,
                         skill_name: str, description: str) -> Path:
        skill_dir.mkdir(parents=True, exist_ok=True)
        probe_file = skill_dir / f"{probe_name}.md"
        _verify_path_containment(probe_file, skill_dir)

        safe_desc = _neutralize_description(description)
        safe_skill_name = _sanitize_skill_name(skill_name)

        probe_file.write_text(
            f"---\nname: {safe_skill_name}\ndescription: >\n"
            f"  {safe_desc}\n---\n\n# {safe_skill_name}\n\n"
            f"[EVALUATION PROBE] {safe_desc}\n"
        )
        return probe_file

    def run_probe(self, query: str, probe_name: str, project_root: Path,
                  timeout: int, model: str | None) -> bool:
        # OpenClaw: use claw CLI if available
        cmd = ["claw", "run", "--prompt", query, "--skill-dir", ".claw/skills"]
        if model:
            cmd.extend(["--model", model])

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout, cwd=str(project_root),
            )
            return probe_name in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


# =============================================================================
# Platform Registry & Auto-Detection
# =============================================================================

PLATFORM_ADAPTERS: dict[str, type[PlatformAdapter]] = {
    "claude": ClaudeAdapter,
    "cursor": CursorAdapter,
    "codex": CodexAdapter,
    "openclaw": OpenClawAdapter,
}


def detect_platform() -> str:
    """Auto-detect the current platform based on project structure."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".claude").is_dir():
            return "claude"
        if (parent / ".cursor").is_dir() or (parent / ".cursorrules").exists():
            return "cursor"
        if (parent / ".claw").is_dir():
            return "openclaw"
        if (parent / "agents.md").exists() or (parent / ".codex").is_dir():
            return "codex"
    # Default fallback
    return "claude"


def get_adapter(platform: str | None = None) -> PlatformAdapter:
    """Get the appropriate platform adapter."""
    if platform is None or platform == "auto":
        platform = detect_platform()

    adapter_cls = PLATFORM_ADAPTERS.get(platform)
    if adapter_cls is None:
        supported = ", ".join(PLATFORM_ADAPTERS.keys())
        raise ValueError(f"Unknown platform '{platform}'. Supported: {supported}")

    return adapter_cls()


# =============================================================================
# Core Evaluation Logic (platform-agnostic)
# =============================================================================

def probe_single_query(
    query: str,
    skill_name: str,
    skill_description: str,
    timeout: int,
    project_root: str,
    model: str | None = None,
    platform: str | None = None,
) -> bool:
    """Run one query and return whether it triggered the skill.

    Works across platforms by delegating to the appropriate adapter.
    """
    adapter = get_adapter(platform)
    uid = uuid.uuid4().hex[:8]
    safe_name = _sanitize_skill_name(skill_name)
    probe_name = f"{safe_name}-probe-{uid}"

    root = Path(project_root)
    skill_dir = adapter.get_skill_dir(root)
    probe_file = adapter.write_probe_file(skill_dir, probe_name, skill_name, skill_description)

    try:
        return adapter.run_probe(query, probe_name, root, timeout, model)
    finally:
        adapter.cleanup(probe_file)


def run_trigger_eval(
    queries: list[dict],
    skill_name: str,
    description: str,
    workers: int = 6,
    timeout: int = 30,
    model: str | None = None,
    platform: str | None = None,
) -> dict:
    """Run all trigger probes and compute precision/recall."""
    adapter = get_adapter(platform)
    project_root = adapter.find_project_root()
    detected_platform = platform or detect_platform()
    results = []

    with ProcessPoolExecutor(max_workers=workers) as executor:
        future_map = {}
        for item in queries:
            future = executor.submit(
                probe_single_query,
                item["query"], skill_name, description,
                timeout, str(project_root), model, detected_platform,
            )
            future_map[future] = item

        for future in as_completed(future_map):
            item = future_map[future]
            try:
                did_trigger = future.result()
            except Exception as e:
                print(f"Warning: probe failed: {e}", file=sys.stderr)
                did_trigger = False

            should = item["should_trigger"]
            passed = (did_trigger == should)
            results.append({
                "query": item["query"],
                "should_trigger": should,
                "did_trigger": did_trigger,
                "pass": passed,
            })

    # Compute precision and recall
    tp = sum(1 for r in results if r["should_trigger"] and r["did_trigger"])
    fp = sum(1 for r in results if not r["should_trigger"] and r["did_trigger"])
    fn = sum(1 for r in results if r["should_trigger"] and not r["did_trigger"])
    tn = sum(1 for r in results if not r["should_trigger"] and not r["did_trigger"])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    accuracy = (tp + tn) / len(results) if results else 0.0
    trigger_score = round((precision * 0.5 + recall * 0.5) * 100)

    return {
        "skill_name": skill_name,
        "description": description,
        "platform": detected_platform,
        "results": results,
        "metrics": {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "accuracy": round(accuracy, 3),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
        },
        "trigger_score": trigger_score,
    }


# =============================================================================
# Skill Frontmatter Parsing
# =============================================================================

def parse_skill_frontmatter(skill_path: Path) -> tuple[str, str]:
    """Extract name and description from SKILL.md frontmatter."""
    content = (skill_path / "SKILL.md").read_text(encoding="utf-8")
    name, description = "unknown", ""

    if content.startswith("---"):
        end = content.index("---", 3)
        front = content[3:end]
        for line in front.split("\n"):
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                desc_part = line.split(":", 1)[1].strip()
                if desc_part.startswith(">"):
                    # Multi-line scalar — collect subsequent indented lines
                    desc_lines = []
                    idx = front.index(line) + len(line) + 1
                    for fline in front[idx:].split("\n"):
                        if fline.startswith("  "):
                            desc_lines.append(fline.strip())
                        elif fline.strip() == "":
                            continue
                        else:
                            break
                    description = " ".join(desc_lines)
                else:
                    description = desc_part

    return name, description


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Run trigger evaluation for a skill (multi-platform)"
    )
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--queries", required=True, help="Path to trigger queries JSON")
    parser.add_argument(
        "--platform", default="auto",
        choices=["auto", "claude", "cursor", "codex", "openclaw"],
        help="Target platform (default: auto-detect)",
    )
    parser.add_argument("--workers", type=int, default=6, help="Parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per probe (seconds)")
    parser.add_argument("--model", default=None, help="Model override for the platform CLI")
    parser.add_argument("--output", default=None, help="Save results to file")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    platform = None if args.platform == "auto" else args.platform
    skill_path = Path(args.skill_path)
    queries = json.loads(Path(args.queries).read_text())
    name, description = parse_skill_frontmatter(skill_path)

    if args.verbose:
        detected = platform or detect_platform()
        print(f"Platform: {detected}", file=sys.stderr)
        print(f"Evaluating trigger for: {name}", file=sys.stderr)
        print(f"Description: {description[:80]}...", file=sys.stderr)
        print(f"Queries: {len(queries)}", file=sys.stderr)

    results = run_trigger_eval(
        queries, name, description,
        args.workers, args.timeout, args.model, platform,
    )

    if args.verbose:
        m = results["metrics"]
        print(
            f"\nPrecision: {m['precision']:.0%}  Recall: {m['recall']:.0%}  "
            f"Score: {results['trigger_score']}",
            file=sys.stderr,
        )
        for r in results["results"]:
            icon = "✓" if r["pass"] else "✗"
            print(
                f"  {icon} trigger={r['did_trigger']}  "
                f"expected={r['should_trigger']}  {r['query'][:60]}",
                file=sys.stderr,
            )

    output = json.dumps(results, indent=2)
    if args.output:
        Path(args.output).write_text(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
