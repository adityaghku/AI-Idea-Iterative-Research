# Idea Harvester Quickstart

This quickstart assumes you have OpenCode running.

## 1) Load the skill

From the `ai_idea_agent/` directory:

```bash
skill idea-harvester
```

If your OpenCode environment requires explicit skill loading only, load `idea-harvester` (and optionally `autoresearch` too).

## 2) Start the loop

Use the slash command:

```text
/idea-harvester
```

The agent will create `idea-harvester.md` if missing, initialize `idea_harvester.sqlite`, enqueue iteration 1 (planner → … → learner), and then iterate.

## 3) Pause / resume

Pause:

```text
/idea-harvester off
```

Resume:

```text
/idea-harvester
```

The queue state is stored in `idea_harvester.sqlite`, so resume should pick up pending messages.

## 4) Dashboard

Generate a markdown report:

```text
/idea-harvester dashboard
```

This creates `idea-harvester-dashboard.md`.

## 5) Final output

At stop (max iterations or plateau), the agent should write:
- `idea-harvester-top10.json`
- `idea-harvester-top10.md`

