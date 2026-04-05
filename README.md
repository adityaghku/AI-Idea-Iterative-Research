# AI Idea Agent

A multi-agent AI system that continuously scrapes the internet for innovative application ideas. The agents collaborate to discover, extract, evaluate, and learn from sources, iteratively improving their search strategies.

## Architecture

| Agent | Responsibility |
|-------|----------------|
| **Orchestrator** | Coordinates workflow, routes messages, manages state |
| **Planner** | Generates search plans based on goals and learned criteria |
| **Researcher** | Finds candidate URLs using search APIs |
| **Scraper** | Extracts structured data from sources |
| **Evaluator** | Scores ideas using novelty, feasibility, market potential |
| **Critic** | Adversarial vetting to filter weak ideas |
| **Learner** | Analyzes results to update heuristics |

## Workflow

1. **Plan** — Planner creates search queries targeting user pain points
2. **Research** — Researcher finds relevant URLs
3. **Scrape** — Scraper extracts text/content (throttled to avoid rate limits)
4. **Evaluate** — Evaluator scores extracted content as ideas
5. **Critic** — Adversarial filter removes low-quality ideas
6. **Learn** — Learner updates knowledge base with validation
7. **Loop** — Repeats until convergence or max iterations

## Requirements

- Python 3.12+
- OpenAI API key (or compatible LLM)

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env with your API key
echo "OPENAI_API_KEY=sk-..." > .env
```

## Usage

```bash
# Run with default goal (mobile app ideas for solo founders)
python main.py

# Custom goal
python main.py --goal "Find B2B SaaS ideas for enterprise automation"

# Resume from previous run
python main.py --resume

# Adjust parameters
python main.py --max-iterations 10 --plateau-window 3
```

### Command Line Options

| Flag | Description | Default |
|------|-------------|---------|
| `--db` | SQLite database path | `idea_harvester.sqlite` |
| `--max-iterations` | Max iterations before stopping | `5` |
| `--plateau-window` | Window for plateau detection | `2` |
| `--min-improvement` | Min score improvement to continue | `0.0` |
| `--goal` | Goal text for this run | Built-in default |
| `--goal-file` | Read goal from file | - |
| `--resume` | Resume from existing run | `false` |
| `--verbose` | Enable verbose logging | `true` |

## Output

- **Database**: `idea_harvester.sqlite` — stores ideas, scores, runs, messages
- **Logs**: `logs/harvester_*.log` — execution logs

## Stopping

Create a `.idea-harvester-off` file to gracefully stop after current iteration:

```bash
touch .idea-harvester-off
```

Resume by removing the file and running with `--resume`.