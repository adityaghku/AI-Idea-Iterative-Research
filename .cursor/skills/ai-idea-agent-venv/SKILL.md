---
name: ai-idea-agent-venv
description: >-
  Requires activating or using the project virtual environment at `.venv` before
  any Python, pip, pytest, or module execution in this repository. Use when
  running terminal commands in ai_idea_agent, installing dependencies, running
  tests, scripts, or when the user mentions Python, venv, or virtualenv for this
  project.
---

# ai_idea_agent — Python via `.venv`

## Rule

For **any** shell command that invokes Python (`python`, `python3`, `pip`, `pytest`, `mypy`, `ruff`, etc.) in this repo, use the interpreter and tools from **`.venv`** at the project root (`ai_idea_agent/.venv`).

Do **not** rely on the system Python or a global interpreter unless the user explicitly asks.

## How to run commands


```bash
cd /path/to/ai_idea_agent
source .venv/bin/activate
python -m pytest tests/ -q
```