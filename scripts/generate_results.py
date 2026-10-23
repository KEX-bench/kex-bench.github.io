#!/usr/bin/env python3
"""Generate public leaderboard data from KEX-bench trajectory CSVs."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
TRAJECTORY_ROOT = BASE_DIR.parent / "trajectories"
OUTPUT_PATH = BASE_DIR / "data" / "results.json"

RUN_TYPES = ("type_a", "type_b")
PLATFORMS = ("linux", "windows")
TYPE_LABELS = {
    "type_a": "without PoC",
    "type_b": "with PoC",
}
PLATFORM_LABELS = {
    "linux": "Linux",
    "windows": "Windows",
}
PRIMITIVE_LABELS = {
    "baseleak": "leak",
    "heap_read": "hread",
    "heap_write": "hwrite",
    "rip": "rip",
    "aaw": "aaw",
}
AGENT_LABELS = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "opencode": "OpenCode",
}
MODEL_REPLACEMENTS = (
    ("us.anthropic.", ""),
    ("-20251001-v1-0", ""),
    ("-v1", ""),
    ("claude-opus-4-6", "Opus 4.6"),
    ("claude-sonnet-4-6", "Sonnet 4.6"),
    ("claude-haiku-4-5", "Haiku 4.5"),
    ("gpt-5.4-mini", "GPT-5.4 Mini"),
    ("gpt-5.4", "GPT-5.4"),
    ("gpt-5.3-codex", "GPT-5.3-Codex"),
    ("kimi-k2.5", "Kimi K2.5"),
    ("google-gemma-4-31b-it", "Gemma 4 31B"),
)
MODEL_ORGS = {
    "Opus 4.6": "Anthropic",
    "Sonnet 4.6": "Anthropic",
    "Haiku 4.5": "Anthropic",
    "GPT-5.4": "OpenAI",
    "GPT-5.4 Mini": "OpenAI",
    "GPT-5.3-Codex": "OpenAI",
    "Kimi K2.5": "Moonshot AI",
    "Gemma 4 31B": "Google",
}
ORDERED_PAIR_NAMES = (
    ("Claude Code", "Opus 4.6"),
    ("Claude Code", "Sonnet 4.6"),
    ("Claude Code", "Haiku 4.5"),
    ("Codex", "GPT-5.4"),
    ("Codex", "GPT-5.4 Mini"),
    ("Codex", "GPT-5.3-Codex"),
    ("OpenCode", "Sonnet 4.6"),
    ("OpenCode", "Haiku 4.5"),
    ("OpenCode", "GPT-5.4 Mini"),
    ("OpenCode", "Kimi K2.5"),
    ("OpenCode", "Gemma 4 31B"),
)
PAIR_ORDER = {pair: index for index, pair in enumerate(ORDERED_PAIR_NAMES)}
TIMESTAMP_RE = re.compile(r"^\d{8}_\d{6}$")
NUMBER_RE = re.compile(r"^([0-9.]+)\s*([kKmMbB]?)$")


def parse_compact_number(value: str | None) -> float:
    if not value:
        return 0.0
    raw = value.strip()
    if raw.endswith("m") and raw[:-1].replace(".", "", 1).isdigit():
        return float(raw[:-1])
    match = NUMBER_RE.fullmatch(raw)
    if not match:
        return 0.0
    number = float(match.group(1))
    unit = match.group(2).lower()
    return number * {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(unit, 1)


def fmt_percent(solved: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{solved / total * 100:.1f}%"


def fmt_tokens(value: float) -> str:
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(int(value))


def fmt_runtime(minutes: float) -> str:
    if minutes >= 60:
        return f"{minutes / 60:.1f}h"
    return f"{minutes:.1f}m"


def fmt_int(value: float | int) -> str:
    return f"{int(round(value)):,}"


def run_date(timestamp: str) -> str:
    if not timestamp:
        return ""
    return f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"


def split_config_name(config: str) -> tuple[str, str]:
    raw_agent, raw_model = config.split("_", 1)
    agent = AGENT_LABELS.get(raw_agent, raw_agent.replace("-", " ").title())
    model = raw_model
    for source, replacement in MODEL_REPLACEMENTS:
        model = model.replace(source, replacement)
    return agent, model


def read_summary(path: Path) -> dict[str, Any]:
    rows = list(csv.DictReader(path.open("r", encoding="utf-8")))
    primitives: dict[str, dict[str, int]] = {}
    tasks = []
    for row in rows:
        primitive = PRIMITIVE_LABELS.get(row.get("expected_type", ""), row.get("expected_type", ""))
        success = row.get("success") == "yes"
        bucket = primitives.setdefault(primitive, {"solved": 0, "total": 0})
        bucket["total"] += 1
        if success:
            bucket["solved"] += 1
        tasks.append(
            {
                "id": row.get("instance_id", ""),
                "primitive": primitive,
                "success": success,
                "status": row.get("status", ""),
            }
        )
    solved = sum(1 for task in tasks if task["success"])
    return {
        "solved": solved,
        "total": len(tasks),
        "score": solved / len(tasks) * 100 if tasks else 0,
        "score_label": fmt_percent(solved, len(tasks)),
        "primitives": primitives,
        "tasks": tasks,
    }


def read_tokens(path: Path) -> tuple[float, float]:
    if not path.exists():
        return 0.0, 0.0
    total_tokens = 0.0
    total_runtime = 0.0
    for row in csv.DictReader(path.open("r", encoding="utf-8")):
        total_tokens += parse_compact_number(row.get("Total"))
        total_runtime += parse_compact_number(row.get("Runtime"))
    return total_tokens, total_runtime


def read_tools(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for row in csv.DictReader(path.open("r", encoding="utf-8")):
        total += int(float(row.get("Total") or 0))
    return total


def timestamp_children(path: Path) -> list[str]:
    return sorted(child.name for child in path.iterdir() if child.is_dir() and TIMESTAMP_RE.fullmatch(child.name))


def collect_runs() -> list[dict[str, Any]]:
    runs = []
    for platform in PLATFORMS:
        platform_dir = TRAJECTORY_ROOT / platform
        for config_dir in sorted(path for path in platform_dir.iterdir() if path.is_dir()):
            agent, model = split_config_name(config_dir.name)
            for run_type in RUN_TYPES:
                run_dir = config_dir / run_type
                summary_path = run_dir / "summary.csv"
                if not summary_path.exists():
                    continue
                summary = read_summary(summary_path)
                tokens, runtime = read_tokens(run_dir / "tokens.csv")
                tools = read_tools(run_dir / "tools.csv")
                timestamps = timestamp_children(run_dir)
                timestamp = timestamps[-1] if timestamps else ""
                runs.append(
                    {
                        "id": f"{platform}-{config_dir.name}-{run_type}",
                        "agent": agent,
                        "model": model,
                        "org": MODEL_ORGS.get(model, ""),
                        "config": config_dir.name,
                        "platform": platform,
                        "platform_label": PLATFORM_LABELS[platform],
                        "type": run_type,
                        "setting": TYPE_LABELS[run_type],
                        "timestamp": timestamp,
                        "date": run_date(timestamp),
                        "path": str(run_dir.relative_to(TRAJECTORY_ROOT)),
                        "solved": summary["solved"],
                        "total": summary["total"],
                        "score": summary["score"],
                        "score_label": summary["score_label"],
                        "primitives": summary["primitives"],
                        "tokens": round(tokens),
                        "tokens_label": fmt_tokens(tokens),
                        "runtime_minutes": round(runtime, 1),
                        "runtime_label": fmt_runtime(runtime),
                        "tool_calls": tools,
                        "tool_calls_label": fmt_int(tools),
                    }
                )
    return sorted(
        runs,
        key=lambda run: (
            PAIR_ORDER.get((run["agent"], run["model"]), 99),
            run["type"],
            run["platform"],
        ),
    )


def empty_mode() -> dict[str, Any]:
    return {
        "solved": 0,
        "total": 0,
        "score": 0.0,
        "score_label": "0.0%",
        "linux": {"solved": 0, "total": 0, "score": 0.0, "score_label": "0.0%"},
        "windows": {"solved": 0, "total": 0, "score": 0.0, "score_label": "0.0%"},
        "tokens": 0,
        "tokens_label": "0",
        "runtime_minutes": 0.0,
        "runtime_label": "0.0m",
        "tool_calls": 0,
        "tool_calls_label": "0",
    }


def finalize_bucket(bucket: dict[str, Any]) -> None:
    total = bucket["total"]
    solved = bucket["solved"]
    bucket["score"] = solved / total * 100 if total else 0.0
    bucket["score_label"] = fmt_percent(solved, total)


def collect_results(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped[(run["agent"], run["model"])].append(run)

    rows = []
    for (agent, model), group_runs in grouped.items():
        modes = {run_type: empty_mode() for run_type in RUN_TYPES}
        for run in group_runs:
            mode = modes[run["type"]]
            platform = mode[run["platform"]]
            for bucket in (mode, platform):
                bucket["solved"] += run["solved"]
                bucket["total"] += run["total"]
            mode["tokens"] += run["tokens"]
            mode["runtime_minutes"] += run["runtime_minutes"]
            mode["tool_calls"] += run["tool_calls"]

        for mode in modes.values():
            finalize_bucket(mode)
            for platform in PLATFORMS:
                finalize_bucket(mode[platform])
            mode["tokens_label"] = fmt_tokens(mode["tokens"])
            mode["runtime_label"] = fmt_runtime(mode["runtime_minutes"])
            mode["tool_calls_label"] = fmt_int(mode["tool_calls"])

        latest = max((run["date"] for run in group_runs if run["date"]), default="")
        rows.append(
            {
                "id": f"{agent}-{model}".lower().replace(" ", "-"),
                "agent": agent,
                "model": model,
                "org": MODEL_ORGS.get(model, ""),
                "date": latest,
                "status": "scored",
                "highlight": False,
                "modes": modes,
                "runs": group_runs,
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            -row["modes"]["type_b"]["score"],
            -row["modes"]["type_a"]["score"],
            PAIR_ORDER.get((row["agent"], row["model"]), 99),
        ),
    )


def add_ranks(rows: list[dict[str, Any]]) -> None:
    for run_type in RUN_TYPES:
        ranked = sorted(
            rows,
            key=lambda row: (
                -row["modes"][run_type]["score"],
                -row["modes"][run_type]["solved"],
                PAIR_ORDER.get((row["agent"], row["model"]), 99),
            ),
        )
        for rank, row in enumerate(ranked, start=1):
            row["modes"][run_type]["rank"] = rank


def summarize(rows: list[dict[str, Any]], runs: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {run_type: {"solved": 0, "total": 0} for run_type in RUN_TYPES}
    for row in rows:
        for run_type in RUN_TYPES:
            totals[run_type]["solved"] += row["modes"][run_type]["solved"]
            totals[run_type]["total"] += row["modes"][run_type]["total"]
    best_type_b = max(rows, key=lambda row: row["modes"]["type_b"]["score"])
    best_type_a = max(rows, key=lambda row: row["modes"]["type_a"]["score"])
    return {
        "task_instances": 45,
        "cves": 40,
        "primitives": 5,
        "agent_model_pairs": len(rows),
        "runs": len(runs),
        "overall": {
            run_type: {
                "solved": totals[run_type]["solved"],
                "total": totals[run_type]["total"],
                "score_label": fmt_percent(totals[run_type]["solved"], totals[run_type]["total"]),
            }
            for run_type in RUN_TYPES
        },
        "best": {
            "type_a": {
                "agent": best_type_a["agent"],
                "model": best_type_a["model"],
                "solved": best_type_a["modes"]["type_a"]["solved"],
                "total": best_type_a["modes"]["type_a"]["total"],
                "score_label": best_type_a["modes"]["type_a"]["score_label"],
            },
            "type_b": {
                "agent": best_type_b["agent"],
                "model": best_type_b["model"],
                "solved": best_type_b["modes"]["type_b"]["solved"],
                "total": best_type_b["modes"]["type_b"]["total"],
                "score_label": best_type_b["modes"]["type_b"]["score_label"],
            },
        },
    }


def main() -> None:
    if not TRAJECTORY_ROOT.exists():
        raise SystemExit(f"Missing trajectory root: {TRAJECTORY_ROOT}")
    runs = collect_runs()
    rows = collect_results(runs)
    add_ranks(rows)
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "source": str(TRAJECTORY_ROOT.relative_to(BASE_DIR.parent)),
        "modes": [
            {
                "id": "type_b",
                "label": "with PoC",
                "description": "reference PoC provided",
            },
            {
                "id": "type_a",
                "label": "without PoC",
                "description": "no reference PoC",
            },
        ],
        "summary": summarize(rows, runs),
        "results": rows,
        "runs": runs,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH.relative_to(BASE_DIR)} with {len(rows)} leaderboard rows and {len(runs)} runs.")


if __name__ == "__main__":
    main()
