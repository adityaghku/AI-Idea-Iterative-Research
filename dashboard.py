#!/usr/bin/env python3
"""Minimal Flask dashboard for viewing Idea Harvester results."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template_string, jsonify, request

from db.idea_harvester_db import get_all_ideas, get_ideas_by_tags, get_all_tags, get_idea_stats, _connect

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
        .tabs {
            display: flex;
            gap: 10px;
            margin: 20px 0;
        }
        .tab {
            padding: 10px 20px;
            background: white;
            border: 2px solid #007bff;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
        }
        .tab:hover {
            background: #e7f3ff;
        }
        .tab.active {
            background: #007bff;
            color: white;
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
        .tag-filter {
            background: white;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .tag-filter h3 {
            margin: 0 0 10px 0;
            color: #333;
            font-size: 14px;
        }
        .tag-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        .tag-chip {
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            background: #e7f3ff;
            border: 1px solid #007bff;
            border-radius: 20px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .tag-chip:hover {
            background: #cce5ff;
        }
        .tag-chip.selected {
            background: #007bff;
            color: white;
        }
        .tag-chip .count {
            margin-left: 6px;
            font-size: 11px;
            opacity: 0.7;
        }
        .clear-filters {
            background: #dc3545;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            margin-left: 10px;
        }
        .clear-filters:hover {
            background: #c82333;
        }
        .filter-controls {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-top: 10px;
        }
        .match-toggle {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }
        .match-toggle input {
            cursor: pointer;
        }
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
        }
        .idea-tags {
            margin-top: 8px;
        }
        .idea-tag {
            display: inline-block;
            background: #e7f3ff;
            color: #007bff;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            margin-right: 4px;
        }
        .hidden {
            display: none;
        }
        .chart-container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .chart-title {
            margin: 0 0 15px 0;
            color: #333;
            font-size: 16px;
            font-weight: 600;
        }
        .bar-chart {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .bar-row {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .bar-label {
            width: 120px;
            font-size: 13px;
            color: #333;
            text-align: right;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .bar-track {
            flex: 1;
            height: 24px;
            background: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
        }
        .bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #007bff, #0056b3);
            border-radius: 4px;
            transition: width 0.3s ease;
        }
        .bar-value {
            width: 50px;
            font-size: 13px;
            color: #666;
            text-align: right;
        }
        .line-chart {
            position: relative;
            height: 200px;
            background: #f8f9fa;
            border-radius: 4px;
            padding: 20px;
            margin-top: 10px;
        }
        .line-chart-svg {
            width: 100%;
            height: 100%;
        }
        .category-section {
            margin-bottom: 30px;
        }
        .category-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e9ecef;
        }
        .category-badge {
            background: #007bff;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }
        .category-count {
            color: #666;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Idea Harvester Dashboard</h1>
        
        {% if runs %}
        <div class="tabs">
            <div class="tab {% if view == 'all' %}active{% endif %}" onclick="switchView('all')">All Ideas</div>
            <div class="tab {% if view == 'run' %}active{% endif %}" onclick="switchView('run')">By Run</div>
            <div class="tab {% if view == 'trends' %}active{% endif %}" onclick="switchView('trends')">Trends</div>
            <div class="tab {% if view == 'top' %}active{% endif %}" onclick="switchView('top')">Top</div>
        </div>

        <div id="tag-filter-section" class="tag-filter {% if view != 'all' %}hidden{% endif %}">
            <h3>Filter by Tags</h3>
            <div id="tag-list" class="tag-list">
                <span class="loading">Loading tags...</span>
            </div>
            <div class="filter-controls">
                <div class="match-toggle">
                    <input type="checkbox" id="match-all" onchange="applyFilters()">
                    <label for="match-all">Match all selected tags (AND)</label>
                </div>
                <button id="clear-filters" class="clear-filters hidden" onclick="clearFilters()">Clear Filters</button>
            </div>
        </div>

        <div class="run-selector {% if view != 'run' %}hidden{% endif %}">
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

        {% if view == 'trends' %}
        <div class="chart-container">
            <h3 class="chart-title">📊 Tag Distribution (Top 20)</h3>
            <div id="tag-distribution" class="bar-chart">
                <div class="loading">Loading...</div>
            </div>
        </div>

        <div class="chart-container">
            <h3 class="chart-title">📈 Ideas Over Time</h3>
            <div id="ideas-over-time" class="bar-chart">
                <div class="loading">Loading...</div>
            </div>
        </div>

        <div class="chart-container">
            <h3 class="chart-title">📉 Average Score Trend</h3>
            <div id="score-trend" class="bar-chart">
                <div class="loading">Loading...</div>
            </div>
        </div>
        {% elif view == 'top' %}
        <div id="top-by-category">
            <div class="loading">Loading top ideas by category...</div>
        </div>
        {% else %}
        <div class="stats">
            <div class="stat-card">
                <h3>{% if view == 'all' %}Total Unique Ideas{% else %}Total Ideas{% endif %}</h3>
                <div class="value" id="stat-total">{{ stats.total_ideas }}</div>
            </div>
            <div class="stat-card">
                <h3>Average Score</h3>
                <div class="value" id="stat-avg">{{ stats.avg_score }}</div>
            </div>
            {% if view == 'all' %}
            <div class="stat-card">
                <h3>Merged Ideas</h3>
                <div class="value" id="stat-merged">{{ stats.merged_ideas }}</div>
            </div>
            {% else %}
            <div class="stat-card">
                <h3>Iterations</h3>
                <div class="value">{{ stats.iterations }}</div>
            </div>
            {% endif %}
            <div class="stat-card">
                <h3>Top Score</h3>
                <div class="value" id="stat-top">{{ stats.top_score }}</div>
            </div>
        </div>

        <div class="section">
            <h2>🏆 {% if view == 'all' %}All Ideas{% else %}Top Ideas{% endif %}</h2>
            <div id="ideas-container">
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
                    {% if idea.tags %}
                    <div class="idea-tags">
                        {% for tag in idea.tags %}
                        <span class="idea-tag">{{ tag }}</span>
                        {% endfor %}
                    </div>
                    {% endif %}
                    <div class="source-url">
                        <strong>Sources:</strong><br>
                        {% for url in idea.source_urls %}
                        <a href="{{ url }}" target="_blank">{{ url }}</a><br>
                        {% endfor %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        {% if view == 'run' %}
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
        {% endif %}
        {% endif %}
        {% else %}
        <div class="no-data">
            <h2>No data found</h2>
            <p>Run the idea harvester first to generate data:</p>
            <code>python3 main.py --goal "Your goal here"</code>
        </div>
        {% endif %}
    </div>

    <script>
        let selectedTags = [];
        let allTags = [];
        
        function switchView(view) {
            window.location.href = '/?view=' + view;
        }
        
        function changeRun(runId) {
            window.location.href = '/?run=' + runId + '&view=run';
        }
        
        async function loadTags() {
            try {
                const response = await fetch('/api/tags');
                allTags = await response.json();
                renderTags();
            } catch (error) {
                console.error('Error loading tags:', error);
                document.getElementById('tag-list').innerHTML = '<span style="color: #dc3545;">Error loading tags</span>';
            }
        }
        
        function renderTags() {
            const container = document.getElementById('tag-list');
            if (allTags.length === 0) {
                container.innerHTML = '<span style="color: #666;">No tags available</span>';
                return;
            }
            
            container.innerHTML = allTags.map(tag => 
                '<div class="tag-chip ' + (selectedTags.includes(tag.name) ? 'selected' : '') + '" onclick="toggleTag(\'' + tag.name + '\')">' +
                tag.name + '<span class="count">(' + tag.usage_count + ')</span>' +
                '</div>'
            ).join('');
            
            updateClearButton();
        }
        
        function toggleTag(tagName) {
            const index = selectedTags.indexOf(tagName);
            if (index === -1) {
                selectedTags.push(tagName);
            } else {
                selectedTags.splice(index, 1);
            }
            renderTags();
            applyFilters();
        }
        
        function updateClearButton() {
            const btn = document.getElementById('clear-filters');
            if (selectedTags.length > 0) {
                btn.classList.remove('hidden');
            } else {
                btn.classList.add('hidden');
            }
        }
        
        function clearFilters() {
            selectedTags = [];
            renderTags();
            applyFilters();
        }
        
        async function applyFilters() {
            const matchAll = document.getElementById('match-all').checked;
            const container = document.getElementById('ideas-container');
            container.innerHTML = '<div class="loading">Loading ideas...</div>';
            
            let url = '/api/ideas/all?limit=50';
            if (selectedTags.length > 0) {
                url += '&tags=' + encodeURIComponent(selectedTags.join(','));
                if (matchAll) {
                    url += '&match_all=true';
                }
            }
            
            try {
                const response = await fetch(url);
                const ideas = await response.json();
                renderIdeas(ideas);
                updateStats(ideas);
            } catch (error) {
                console.error('Error loading ideas:', error);
                container.innerHTML = '<div class="loading" style="color: #dc3545;">Error loading ideas</div>';
            }
        }
        
        function renderIdeas(ideas) {
            const container = document.getElementById('ideas-container');
            if (ideas.length === 0) {
                container.innerHTML = '<div class="no-data"><p>No ideas found matching the selected filters.</p></div>';
                return;
            }
            
            container.innerHTML = ideas.map(idea => {
                const tagsHtml = idea.tags && idea.tags.length > 0 
                    ? '<div class="idea-tags">' + idea.tags.map(t => '<span class="idea-tag">' + t + '</span>').join('') + '</div>'
                    : '';
                
                const breakdown = idea.score_breakdown || {};
                const breakdownHtml = 'Novelty: ' + (breakdown.novelty || 'N/A') + ' | ' +
                    'Feasibility: ' + (breakdown.feasibility || 'N/A') + ' | ' +
                    'Market: ' + (breakdown.market_potential || 'N/A');
                
                const sourcesHtml = idea.source_urls && idea.source_urls.length > 0
                    ? idea.source_urls.map(u => '<a href="' + u + '" target="_blank">' + u + '</a>').join('<br>')
                    : 'No sources';
                
                return '<div class="idea-card">' +
                    '<h3>' + idea.idea_title + '</h3>' +
                    '<span class="score">' + idea.score + '/100</span>' +
                    '<div class="score-breakdown">' + breakdownHtml + '</div>' +
                    '<p><strong>Summary:</strong> ' + (idea.idea_summary || 'No summary') + '</p>' +
                    '<div class="explanation">' + (idea.evaluator_explain || 'No explanation') + '</div>' +
                    tagsHtml +
                    '<div class="source-url"><strong>Sources:</strong><br>' + sourcesHtml + '</div>' +
                    '</div>';
            }).join('');
        }
        
        function updateStats(ideas) {
            if (ideas.length === 0) {
                document.getElementById('stat-total').textContent = '0';
                document.getElementById('stat-avg').textContent = '0';
                document.getElementById('stat-top').textContent = '0';
                return;
            }
            
            const total = ideas.length;
            const avg = ideas.reduce((sum, i) => sum + i.score, 0) / total;
            const top = Math.max(...ideas.map(i => i.score));
            
            document.getElementById('stat-total').textContent = total;
            document.getElementById('stat-avg').textContent = avg.toFixed(1);
            document.getElementById('stat-top').textContent = top.toFixed(1);
        }
        
        // Trends view functions
        async function loadTrends() {
            await Promise.all([
                loadTagDistribution(),
                loadIdeasOverTime(),
                loadScoreTrend()
            ]);
        }
        
        function renderBarChart(containerId, data, maxVal) {
            const container = document.getElementById(containerId);
            if (data.length === 0) {
                container.innerHTML = '<div class="no-data"><p>No data available</p></div>';
                return;
            }
            
            const max = maxVal || Math.max(...data.map(d => d.value));
            container.innerHTML = data.map(item => {
                const width = (item.value / max) * 100;
                return '<div class="bar-row">' +
                    '<div class="bar-label" title="' + item.label + '">' + item.label + '</div>' +
                    '<div class="bar-track"><div class="bar-fill" style="width: ' + width + '%;"></div></div>' +
                    '<div class="bar-value">' + item.value + '</div>' +
                    '</div>';
            }).join('');
        }
        
        async function loadTagDistribution() {
            try {
                const response = await fetch('/api/tags');
                const tags = await response.json();
                const top20 = tags.slice(0, 20).map(t => ({ label: t.name, value: t.usage_count }));
                renderBarChart('tag-distribution', top20);
            } catch (error) {
                console.error('Error loading tag distribution:', error);
                document.getElementById('tag-distribution').innerHTML = '<div class="loading" style="color: #dc3545;">Error loading data</div>';
            }
        }
        
        async function loadIdeasOverTime() {
            try {
                const response = await fetch('/api/trends/ideas-over-time');
                const data = await response.json();
                renderBarChart('ideas-over-time', data.map(d => ({ label: d.run_id.slice(0, 20), value: d.idea_count })));
            } catch (error) {
                console.error('Error loading ideas over time:', error);
                document.getElementById('ideas-over-time').innerHTML = '<div class="loading" style="color: #dc3545;">Error loading data</div>';
            }
        }
        
        async function loadScoreTrend() {
            try {
                const response = await fetch('/api/trends/score-trend');
                const data = await response.json();
                renderBarChart('score-trend', data.map(d => ({ label: d.run_id.slice(0, 20), value: d.avg_score.toFixed(1) })));
            } catch (error) {
                console.error('Error loading score trend:', error);
                document.getElementById('score-trend').innerHTML = '<div class="loading" style="color: #dc3545;">Error loading data</div>';
            }
        }
        
        // Top by category view functions
        async function loadTopByCategory() {
            try {
                const response = await fetch('/api/top-by-category');
                const data = await response.json();
                renderTopByCategory(data);
            } catch (error) {
                console.error('Error loading top by category:', error);
                document.getElementById('top-by-category').innerHTML = '<div class="loading" style="color: #dc3545;">Error loading data</div>';
            }
        }
        
        function renderTopByCategory(categories) {
            const container = document.getElementById('top-by-category');
            if (Object.keys(categories).length === 0) {
                container.innerHTML = '<div class="no-data"><p>No categorized ideas found.</p></div>';
                return;
            }
            
            const categoryOrder = ['industry', 'technology', 'business_model', 'founder_fit'];
            const categoryLabels = {
                'industry': 'Industry',
                'technology': 'Technology',
                'business_model': 'Business Model',
                'founder_fit': 'Founder Fit'
            };
            
            let html = '';
            for (const cat of categoryOrder) {
                if (!categories[cat] || categories[cat].length === 0) continue;
                
                html += '<div class="section">' +
                    '<div class="category-header">' +
                    '<span class="category-badge">' + categoryLabels[cat] + '</span>' +
                    '<span class="category-count">' + categories[cat].length + ' ideas</span>' +
                    '</div>';
                
                for (const idea of categories[cat]) {
                    const tagsHtml = idea.tags && idea.tags.length > 0
                        ? '<div class="idea-tags">' + idea.tags.map(t => '<span class="idea-tag">' + t + '</span>').join('') + '</div>'
                        : '';
                    
                    html += '<div class="idea-card">' +
                        '<h3>' + idea.idea_title + '</h3>' +
                        '<span class="score">' + idea.score + '/100</span>' +
                        '<p><strong>Summary:</strong> ' + (idea.idea_summary || 'No summary') + '</p>' +
                        tagsHtml +
                        '</div>';
                }
                
                html += '</div>';
            }
            
            container.innerHTML = html;
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            {% if view == 'all' %}
            loadTags();
            {% elif view == 'trends' %}
            loadTrends();
            {% elif view == 'top' %}
            loadTopByCategory();
            {% endif %}
        });
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
            else {"novelty": 0, "feasibility": 0, "market_potential": 0}
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

    view = request.args.get("view", "all")
    
    if view == "all":
        stats_data = get_idea_stats(DB_PATH)
        ideas = get_all_ideas(DB_PATH, limit=50)
        
        stats = {
            "total_ideas": stats_data.get("unique_ideas", 0),
            "avg_score": 0,
            "merged_ideas": stats_data.get("merged_ideas", 0),
            "top_score": 0,
        }
        
        if ideas:
            stats["avg_score"] = round(sum(i.get("score", 0) for i in ideas) / len(ideas), 1)
            stats["top_score"] = round(max(i.get("score", 0) for i in ideas), 1)
        
        return render_template_string(
            DASHBOARD_TEMPLATE,
            runs=runs,
            current_run=runs[0]["task_id"] if runs else None,
            view="all",
            top_ideas=ideas,
            stats=stats,
        )
    
    # View: run
    run_id = request.args.get("run", runs[0]["task_id"])
    data = get_run_data(run_id)

    if not data:
        return render_template_string(DASHBOARD_TEMPLATE, runs=[])

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
        view="run",
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


@app.route("/api/ideas/all")
def api_all_ideas():
    """API endpoint for all ideas across runs (non-merged only)."""
    tags_param = request.args.get("tags", "")
    match_all = request.args.get("match_all", "false").lower() == "true"
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    if tags_param:
        tag_names = [t.strip() for t in tags_param.split(",") if t.strip()]
        ideas = get_ideas_by_tags(
            DB_PATH,
            tag_names=tag_names,
            match_all=match_all,
            limit=limit,
            offset=offset,
        )
    else:
        ideas = get_all_ideas(DB_PATH, limit=limit, offset=offset)

    return jsonify(ideas)


@app.route("/api/tags")
def api_tags():
    """API endpoint for all tags with usage counts."""
    category = request.args.get("category")

    conn = _connect(DB_PATH)
    try:
        tags = get_all_tags(conn, category=category)
        return jsonify(tags)
    finally:
        conn.close()


@app.route("/api/trends/ideas-over-time")
def api_ideas_over_time():
    """API endpoint for ideas count per run."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.task_id, COUNT(i.idea_id) as idea_count
            FROM runs r
            LEFT JOIN ideas i ON r.task_id = i.run_task_id AND i.canonical_idea_id IS NULL
            GROUP BY r.task_id
            ORDER BY r.created_at ASC
            """
        )
        rows = cursor.fetchall()
        return jsonify([{"run_id": r["task_id"], "idea_count": r["idea_count"]} for r in rows])
    finally:
        conn.close()


@app.route("/api/trends/score-trend")
def api_score_trend():
    """API endpoint for average score per run."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.task_id, AVG(i.score) as avg_score
            FROM runs r
            LEFT JOIN ideas i ON r.task_id = i.run_task_id AND i.canonical_idea_id IS NULL
            GROUP BY r.task_id
            ORDER BY r.created_at ASC
            """
        )
        rows = cursor.fetchall()
        return jsonify([{"run_id": r["task_id"], "avg_score": r["avg_score"] or 0} for r in rows])
    finally:
        conn.close()


@app.route("/api/top-by-category")
def api_top_by_category():
    """API endpoint for top ideas grouped by tag category."""
    categories = ["industry", "technology", "business_model", "founder_fit"]
    result = {}

    conn = _connect(DB_PATH)
    try:
        for cat in categories:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT i.idea_id, i.idea_title, i.idea_summary, i.score,
                       GROUP_CONCAT(DISTINCT t.name) as tags
                FROM ideas i
                JOIN idea_tags it ON i.idea_id = it.idea_id
                JOIN tags t ON it.tag_id = t.tag_id
                WHERE t.category = ? AND i.canonical_idea_id IS NULL
                GROUP BY i.idea_id
                ORDER BY i.score DESC
                LIMIT 5
                """,
                (cat,),
            )
            rows = cursor.fetchall()
            result[cat] = [
                {
                    "idea_id": r["idea_id"],
                    "idea_title": r["idea_title"],
                    "idea_summary": r["idea_summary"],
                    "score": r["score"],
                    "tags": r["tags"].split(",") if r["tags"] else [],
                }
                for r in rows
            ]
        return jsonify(result)
    finally:
        conn.close()


if __name__ == "__main__":
    print("Starting Idea Harvester Dashboard...")
    print("Open http://127.0.0.1:8133 in your browser")
    print("Press Ctrl+C to stop")
    app.run(debug=True, host="0.0.0.0", port=8133)
