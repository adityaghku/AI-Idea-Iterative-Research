#!/usr/bin/env python3
"""Minimal Flask dashboard for viewing Idea Harvester results."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

# Database path
DB_PATH = "idea_harvester.sqlite"

# HTML Template
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Idea Harvester Dashboard</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-card h3 {
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
            color: #007bff;
        }
        .section {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section h2 {
            margin-top: 0;
            color: #333;
        }
        .idea-card {
            border-left: 4px solid #007bff;
            padding: 15px;
            margin: 15px 0;
            background: #f8f9fa;
            border-radius: 0 8px 8px 0;
        }
        .idea-card h3 {
            margin: 0 0 10px 0;
            color: #333;
        }
        .score {
            display: inline-block;
            background: #007bff;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
        }
        .score-breakdown {
            margin: 10px 0;
            font-size: 14px;
            color: #666;
        }
        .explanation {
            margin-top: 10px;
            padding: 10px;
            background: white;
            border-radius: 4px;
            white-space: pre-wrap;
            font-size: 13px;
            line-height: 1.5;
        }
        .source-url {
            font-size: 12px;
            color: #666;
            word-break: break-all;
        }
        .run-selector {
            margin: 20px 0;
        }
        select {
            padding: 10px;
            font-size: 16px;
            border: 2px solid #007bff;
            border-radius: 4px;
            background: white;
        }
        .refresh-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            margin-left: 10px;
        }
        .refresh-btn:hover {
            background: #218838;
        }
        .no-data {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Idea Harvester Dashboard</h1>
        
        {% if runs %}
        <div class="run-selector">
            <label for="run-select">Select Run: </label>
            <select id="run-select" onchange="changeRun(this.value)">
                {% for run in runs %}
                <option value="{{ run.task_id }}" {% if run.task_id == current_run %}selected{% endif %}>
                    {{ run.task_id }} - {{ run.goal[:50] }}{% if run.goal|length > 50 %}...{% endif %}
                </option>
                {% endfor %}
            </select>
            <button class="refresh-btn" onclick="location.reload()">Refresh</button>
        </div>

        <div class="stats">
            <div class="stat-card">
                <h3>Total Ideas</h3>
                <div class="value">{{ stats.total_ideas }}</div>
            </div>
            <div class="stat-card">
                <h3>Average Score</h3>
                <div class="value">{{ stats.avg_score }}</div>
            </div>
            <div class="stat-card">
                <h3>Iterations</h3>
                <div class="value">{{ stats.iterations }}</div>
            </div>
            <div class="stat-card">
                <h3>Top Score</h3>
                <div class="value">{{ stats.top_score }}</div>
            </div>
        </div>

        <div class="section">
            <h2>🏆 Top Ideas</h2>
            {% for idea in top_ideas %}
            <div class="idea-card">
                <h3>{{ idea.idea_title }}</h3>
                <span class="score">{{ idea.score }}/100</span>
                <div class="score-breakdown">
                    Novelty: {{ idea.score_breakdown.novelty }} | 
                    Feasibility: {{ idea.score_breakdown.feasibility }} | 
                    Market: {{ idea.score_breakdown.market_potential }}
                </div>
                <p><strong>Summary:</strong> {{ idea.idea_summary }}</p>
                <div class="explanation">{{ idea.evaluator_explain }}</div>
                <div class="source-url">
                    <strong>Sources:</strong><br>
                    {% for url in idea.source_urls %}
                    <a href="{{ url }}" target="_blank">{{ url }}</a><br>
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="section">
            <h2>Iteration History</h2>
            <table>
                <thead>
                    <tr>
                        <th>Iteration</th>
                        <th>Average Score</th>
                        <th>Validation Score</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for iter in iterations %}
                    <tr>
                        <td>{{ iter.iteration_number }}</td>
                        <td>{{ iter.avg_score or 'N/A' }}</td>
                        <td>{{ iter.validation_score or 'N/A' }}</td>
                        <td>{{ iter.status }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>🎯 Current Goal</h2>
            <p>{{ goal }}</p>
        </div>
        {% else %}
        <div class="no-data">
            <h2>No data found</h2>
            <p>Run the idea harvester first to generate data:</p>
            <code>python3 main.py --goal "Your goal here"</code>
        </div>
        {% endif %}
    </div>

    <script>
        function changeRun(runId) {
            window.location.href = '/?run=' + runId;
        }
    </script>
</body>
</html>
"""


def get_db_connection():
    """Create a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_runs():
    """Get all runs from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT task_id, goal FROM runs ORDER BY created_at DESC")
    runs = cursor.fetchall()
    conn.close()
    return runs


def get_run_data(run_task_id: str):
    """Get data for a specific run."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get run info
    cursor.execute("SELECT * FROM runs WHERE task_id = ?", (run_task_id,))
    run = cursor.fetchone()

    if not run:
        conn.close()
        return None

    # Get top ideas
    cursor.execute(
        """
        SELECT * FROM ideas 
        WHERE run_task_id = ? 
        ORDER BY score DESC 
        LIMIT 10
    """,
        (run_task_id,),
    )
    ideas = cursor.fetchall()

    # Get iterations
    cursor.execute(
        """
        SELECT iteration_number, avg_score, validation_score, status 
        FROM iterations 
        WHERE run_task_id = ? 
        ORDER BY iteration_number
    """,
        (run_task_id,),
    )
    iterations = cursor.fetchall()

    conn.close()

    return {
        "run": run,
        "ideas": ideas,
        "iterations": iterations,
    }


def parse_idea(idea_row):
    """Parse idea row into dict."""
    return {
        "idea_title": idea_row["idea_title"],
        "idea_summary": idea_row["idea_summary"],
        "score": idea_row["score"],
        "score_breakdown": (
            json.loads(idea_row["score_breakdown"])
            if idea_row["score_breakdown"]
            else {}
        ),
        "evaluator_explain": idea_row["evaluator_explain"],
        "source_urls": (
            json.loads(idea_row["source_urls"]) if idea_row["source_urls"] else []
        ),
    }


@app.route("/")
def dashboard():
    """Main dashboard view."""
    runs = get_all_runs()

    if not runs:
        return render_template_string(DASHBOARD_TEMPLATE, runs=[])

    # Get selected run (or most recent)
    run_id = runs[0]["task_id"]

    data = get_run_data(run_id)

    if not data:
        return render_template_string(DASHBOARD_TEMPLATE, runs=[])

    # Calculate stats
    ideas = [parse_idea(idea) for idea in data["ideas"]]
    avg_score = sum(i["score"] for i in ideas) / len(ideas) if ideas else 0
    top_score = max(i["score"] for i in ideas) if ideas else 0

    stats = {
        "total_ideas": len(ideas),
        "avg_score": round(avg_score, 1),
        "iterations": len(data["iterations"]),
        "top_score": round(top_score, 1),
    }

    return render_template_string(
        DASHBOARD_TEMPLATE,
        runs=runs,
        current_run=run_id,
        top_ideas=ideas,
        iterations=data["iterations"],
        stats=stats,
        goal=data["run"]["goal"],
    )


@app.route("/api/runs")
def api_runs():
    """API endpoint for all runs."""
    runs = get_all_runs()
    return jsonify([{"task_id": r["task_id"], "goal": r["goal"]} for r in runs])


@app.route("/api/run/<run_task_id>/ideas")
def api_ideas(run_task_id: str):
    """API endpoint for ideas."""
    data = get_run_data(run_task_id)
    if not data:
        return jsonify({"error": "Run not found"}), 404

    ideas = [parse_idea(idea) for idea in data["ideas"]]
    return jsonify(ideas)


if __name__ == "__main__":
    print("Starting Idea Harvester Dashboard...")
    print("Open http://127.0.0.1:8133 in your browser")
    print("Press Ctrl+C to stop")
    app.run(debug=True, host="0.0.0.0", port=8133)
