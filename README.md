# AI Idea Iterative Research (Postgres)

Async multi-agent pipeline for generating and evaluating product ideas on top of a
single Postgres backend.

## Runtime Architecture

The active runtime is a 7-step async pipeline:

1. `ScoutAgent` collects problem signals.
2. `SynthesizerAgent` creates idea candidates with deterministic source-signal links and structured business fields.
3. `AnalyserAgent` scores ideas and stores structured subscores.
4. `DeepDiveAgent` adds market, pricing, validation, and feasibility enrichment.
5. `CriticAgent` records adversarial concerns including monetization and validation blockers.
6. `LibrarianAgent` performs embedding-based dedupe while preserving business fields.
7. `PortfolioAgent` turns recurring crossed-out rationale into compact next-run guidance.

## Postgres Data Model

Core entities:
- `signals`
- `ideas`
- `idea_signals` (Idea<->Signal graph edges)
- `analyses`, `enrichments`, `critiques`
- `pipeline_runs`, `agent_runs`, `feedback_events`, `portfolio_memories`

Graph and embedding entities:
- `idea_embeddings` (pgvector embedding per idea)
- `idea_relations` (Idea<->Idea edges, e.g. `duplicate_of`, `similar_to`)
- `signal_relations` (Signal<->Signal edges)

## Requirements

- Python 3.12+
- Docker + Docker Compose (for local Postgres + pgvector)
- OpenCode server/API for LLM calls (`OPENCODE_BASE_URL`, optional auth)

## Setup

```bash
pip install -r requirements.txt
docker compose up -d
```

Example `.env`:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/idea_harvester
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:postgres@localhost:5432/idea_harvester
OPENCODE_BASE_URL=http://localhost:4096
```

## Usage

```bash
# Run pipeline once
python main.py

# Run pipeline with multiple iterations
python main.py -n 5
python main.py --max-iterations 10
```

## Dashboard

To visualize results:

```bash
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

Dashboard notes:
- Crossing out an idea now records explicit negative feedback with a required reason.
- Saving an idea remains a workflow/bookmark action and is not part of the learning signal.
- Portfolio guidance appears in the dashboard overview once the pipeline has written `portfolio_memories`.

## Notes

- `init_db()` creates the pgvector extension and tables automatically.