#!/usr/bin/env python3
"""
Dashboard generator for idea-harvester runs stored in SQLite.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from typing import Any, Optional


def _connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _mean(vals: list[float]) -> Optional[float]:
    if not vals:
        return None
    return sum(vals) / len(vals)


def load_run(conn: sqlite3.Connection, run_task_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM runs WHERE task_id=?", (run_task_id,)).fetchone()
    if row is None:
        raise ValueError(f"No run found for task_id={run_task_id}")
    return row


def load_iteration_scores(
    conn: sqlite3.Connection, run_task_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT iteration_number, avg_score, validation_score, status
        FROM iterations
        WHERE run_task_id=?
        ORDER BY iteration_number ASC
        """,
        (run_task_id,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "iteration_number": int(r["iteration_number"]),
                "avg_score": r["avg_score"],
                "validation_score": r["validation_score"],
                "status": r["status"],
            }
        )
    return out


def compute_plateau(
    scores: list[dict[str, Any]],
    plateau_window: int,
    min_improvement: float,
) -> dict[str, Any]:
    """
    Plateau logic:
    - Take last window average (only non-null avg_score values).
    - Compare to previous window average.
    - If improvement is <= min_improvement, treat as plateau.
    """
    cleaned = [
        (s["iteration_number"], s["avg_score"])
        for s in scores
        if s["avg_score"] is not None
    ]
    if len(cleaned) < plateau_window * 2:
        return {"plateau": False, "reason": "insufficient_history"}

    # last window
    last_vals = [v for _, v in cleaned[-plateau_window:]]
    prev_vals = [v for _, v in cleaned[-(plateau_window * 2) : -plateau_window]]
    last_avg = _mean(last_vals)
    prev_avg = _mean(prev_vals)
    if last_avg is None or prev_avg is None:
        return {"plateau": False, "reason": "null_avg"}
    improvement = last_avg - prev_avg
    plateau = improvement <= float(min_improvement)
    return {
        "plateau": plateau,
        "prev_avg": prev_avg,
        "last_avg": last_avg,
        "improvement": improvement,
        "plateau_window": plateau_window,
        "min_improvement": min_improvement,
    }


def load_top_ideas(
    conn: sqlite3.Connection, run_task_id: str, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          iteration_number,
          source_urls,
          idea_title,
          idea_summary,
          idea_payload,
          score,
          score_breakdown,
          evaluator_explain
        FROM ideas
        WHERE run_task_id=?
        ORDER BY score DESC, iteration_number ASC
        LIMIT ?
        """,
        (run_task_id, int(limit)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "iteration_number": int(r["iteration_number"]),
                "source_urls": json.loads(r["source_urls"]),
                "idea_title": r["idea_title"],
                "idea_summary": r["idea_summary"],
                "idea_payload": json.loads(r["idea_payload"]),
                "score": float(r["score"]),
                "score_breakdown": json.loads(r["score_breakdown"]),
                "evaluator_explain": r["evaluator_explain"],
            }
        )
    return out


def markdown_escape(s: str) -> str:
    # Basic escaping; good enough for a dashboard.
    return s.replace("|", "\\|")


def render_dashboard(
    run: sqlite3.Row,
    iteration_scores: list[dict[str, Any]],
    plateau_info: dict[str, Any],
    top_ideas: list[dict[str, Any]],
) -> str:
    goal = run["goal"]
    task_id = run["task_id"]
    max_iterations = int(run["max_iterations"])
    plateau_window = int(run["plateau_window"])
    min_improvement = float(run["min_improvement"])

    complete_count = sum(
        1 for it in iteration_scores if it["status"] in ("complete", "stopped")
    )
    active_count = sum(1 for it in iteration_scores if it["status"] == "active")

    lines: list[str] = []
    lines.append(f"# Idea Harvester Dashboard: {markdown_escape(goal)}")
    lines.append("")
    lines.append(f"**Task:** `{task_id}`")
    lines.append(
        f"**Iterations:** {len(iteration_scores)} | **Active:** {active_count} | **Finished:** {complete_count} (max {max_iterations})"
    )
    lines.append("")
    lines.append("## Iteration Avg Scores")
    if not iteration_scores:
        lines.append("_No iterations recorded yet._")
    else:
        for it in iteration_scores:
            val = it["avg_score"]
            vval = it.get("validation_score")
            status = it["status"]
            lines.append(
                f"- Iteration {it['iteration_number']}: avg={val if val is not None else 'null'}, validation={vval if vval is not None else 'null'} ({status})"
            )
    lines.append("")

    lines.append("## Plateau Check")
    lines.append(f"- plateau_window: {plateau_window}")
    lines.append(f"- min_improvement: {min_improvement}")
    if plateau_info.get("plateau"):
        lines.append("- result: plateau likely (stop condition met)")
    else:
        lines.append(
            f"- result: not plateau (reason: {plateau_info.get('reason') or 'score_improved'})"
        )
    if "improvement" in plateau_info:
        lines.append(f"- last_avg - prev_avg: {plateau_info['improvement']}")
    lines.append("")

    lines.append("## Top Ideas")
    if not top_ideas:
        lines.append("_No ideas stored yet._")
    else:
        lines.append("")
        lines.append("| # | Score | Iteration | Title | Sources | Justification |")
        lines.append("|---:|---:|---:|---|---|---|")
        for idx, idea in enumerate(top_ideas, start=1):
            sources = ", ".join(idea["source_urls"][:3])
            just = (idea["evaluator_explain"] or "").strip()
            if len(just) > 180:
                just = just[:177] + "..."
            lines.append(
                f"| {idx} | {idea['score']:.2f} | {idea['iteration_number']} | {markdown_escape(idea['idea_title'])} | {markdown_escape(sources)} | {markdown_escape(just)} |"
            )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generate dashboard for idea-harvester"
    )
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-task-id", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--out", default="idea-harvester-dashboard.md")
    args = parser.parse_args(argv)

    conn = _connect(args.db)
    try:
        run = load_run(conn, args.run_task_id)
        iteration_scores = load_iteration_scores(conn, args.run_task_id)
        plateau_info = compute_plateau(
            scores=iteration_scores,
            plateau_window=int(run["plateau_window"]),
            min_improvement=float(run["min_improvement"]),
        )
        top_ideas = load_top_ideas(conn, args.run_task_id, args.limit)
        md = render_dashboard(run, iteration_scores, plateau_info, top_ideas)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(args.out)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
