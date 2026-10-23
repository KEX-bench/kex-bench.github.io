#!/usr/bin/env python3
"""Build KEX-bench with the SEC-bench website templates and static results."""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape


BASE_DIR = Path(__file__).resolve().parent
MODES = ("type_b", "type_a")
ORG_LOGOS = {
    "Anthropic": "https://avatars.githubusercontent.com/u/76263028?s=200&v=4",
    "OpenAI": "https://avatars.githubusercontent.com/u/14957082?s=200&v=4",
    "Google": "https://avatars.githubusercontent.com/u/1342004?s=200&v=4",
    "Moonshot AI": "https://statics.moonshot.cn/moonshot-ai/assets/static/kimi-icon.ByIGCGon.webp",
}


def load_json(name: str) -> dict:
    return json.loads((BASE_DIR / "data" / name).read_text(encoding="utf-8"))


def asset_url(name: str) -> str:
    digest = hashlib.sha256((BASE_DIR / name).read_bytes()).hexdigest()[:12]
    return f"/{name}?v={digest}"


def format_tokens(value: int) -> str:
    for threshold, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= threshold:
            return f"{value / threshold:.1f}{suffix}"
    return str(value)


def format_runtime(minutes: float) -> str:
    return f"{minutes / 60:.1f}h" if minutes >= 60 else f"{minutes:.1f}m"


def highlight_citation(value: str, format_id: str) -> str:
    lines = []
    for line in value.splitlines():
        escaped = html.escape(line)
        field = re.match(r"^(\s*)([a-z]+)(\s*=\s*)(.*)$", escaped)
        if field:
            indent, name, operator, content = field.groups()
            escaped = f'{indent}<span class="bib-field">{name}</span>{operator}<span class="bib-value">{content}</span>'
        elif line.startswith("@"):
            escaped = f'<span class="bib-type">{escaped}</span>'
        lines.append(escaped)
    return "\n".join(lines)


def aggregate_runs(runs: list[dict]) -> dict:
    solved = sum(run["solved"] for run in runs)
    total = sum(run["total"] for run in runs)
    score = solved / total * 100 if total else 0
    tokens = sum(run["tokens"] for run in runs)
    runtime = sum(run["runtime_minutes"] for run in runs)
    tools = sum(run["tool_calls"] for run in runs)
    return {
        "solved": solved,
        "total": total,
        "score": score,
        "score_label": f"{score:.1f}%",
        "tokens": tokens,
        "tokens_label": format_tokens(tokens),
        "runtime_minutes": runtime,
        "runtime_label": format_runtime(runtime),
        "tool_calls": tools,
        "tool_calls_label": f"{tools:,}",
    }


def prepare_leaderboards(config: dict, snapshot: dict) -> list[dict]:
    leaderboards = []
    for target in config["targets"]:
        rows = []
        for source in snapshot["results"]:
            runs = [run for run in source["runs"] if target["name"] == "overall" or run["platform"] == target["name"]]
            modes = {}
            for mode in MODES:
                mode_runs = [run for run in runs if run["type"] == mode]
                bucket = dict(source["modes"][mode]) if target["name"] == "overall" else aggregate_runs(mode_runs)
                bucket["date"] = max((run["date"] for run in mode_runs), default="")
                # Platform contributions share the Overall denominator, as in SEC-bench.
                bucket["projects"] = [
                    {"name": platform, "label": platform.title(),
                     "width": source["modes"][mode][platform]["solved"] / bucket["total"] * 100,
                     "title": f'{platform.title()}: {source["modes"][mode][platform]["solved"]}/{source["modes"][mode][platform]["total"]}'}
                    for platform in ("linux", "windows")
                ] if target["name"] == "overall" else []
                modes[mode] = bucket
            rows.append({
                **source, "modes": modes, "runs": runs,
                "open_source": source["model"] in {"Kimi K2.5", "Gemma 4 31B"},
                "details_url": f'/{target["name"]}/{source["id"]}/',
                "org_logo": ORG_LOGOS[source["org"]],
            })
        for mode in MODES:
            # Preserve existing overall ranks; rank platform subsets by success.
            if target["name"] != "overall":
                ranked = sorted(rows, key=lambda row: row["modes"][mode]["score"], reverse=True)
                for rank, row in enumerate(ranked, 1):
                    row["modes"][mode]["rank"] = rank
        rows.sort(key=lambda row: row["modes"]["type_b"]["rank"])
        leaderboards.append({**target, "results": rows})
    return leaderboards


def main() -> None:
    config = load_json("leaderboards.json")
    snapshot = load_json("results.json")
    leaderboards = prepare_leaderboards(config, snapshot)
    env = Environment(
        loader=FileSystemLoader(BASE_DIR / "templates"),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["asset_url"] = asset_url
    env.filters["highlight_citation"] = highlight_citation
    output = BASE_DIR / "dist"
    if output.exists():
        shutil.rmtree(output)
    output.mkdir()
    for folder in ("css", "js", "img"):
        source = BASE_DIR / folder
        if source.exists():
            shutil.copytree(source, output / folder)
    (output / "data").mkdir()
    shutil.copy2(BASE_DIR / "data/results.json", output / "data/results.json")
    (output / ".nojekyll").touch()
    context = {
        "site": config["site"],
        "config": config,
        "leaderboards": leaderboards,
        "current_year": date.today().year,
        "generated_at": snapshot["generated_at"],
    }

    def render(template: str, path: str, **values) -> None:
        destination = output / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(env.get_template(template).render(**context, **values), encoding="utf-8")

    for target in config["targets"]:
        path = "index.html" if target["name"] == "overall" else f'{target["name"]}/index.html'
        render("index.html", path, active_target=target["name"], page_path="/" if target["name"] == "overall" else f'/{target["name"]}/')
    for leaderboard in leaderboards:
        for row in leaderboard["results"]:
            render("run_detail.html", row["details_url"].strip("/") + "/index.html",
                   detail=row, target=leaderboard, page_path=row["details_url"])
    render("pages/citations.html", "citations.html", page_path="/citations.html", citations=[{
        "id": "kexbench", "label": "KEX-bench", "heading": config["citation"]["title"],
        "description": config["site"]["venue"],
        "formats": [{"id": "bibtex", "label": "BibTeX", "text": config["citation"]["text"]}],
    }])
    print(f"Built {len(leaderboards)} leaderboards and {sum(len(lb['results']) for lb in leaderboards)} run detail pages in {output}")


if __name__ == "__main__":
    main()
