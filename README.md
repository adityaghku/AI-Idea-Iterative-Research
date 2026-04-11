# AI Idea Iterative Research (Postgres)

Async multi-agent pipeline for generating and evaluating product ideas on top of a
single Postgres backend.

## Runtime Architecture

The active runtime is a 6-step async pipeline:

1. `ScoutAgent` collects problem signals.
2. `SynthesizerAgent` creates idea candidates with deterministic source-signal links.
3. `AnalyserAgent` scores ideas and stores assumptions/metadata.
4. `DeepDiveAgent` adds market/feasibility enrichment.
5. `CriticAgent` records adversarial concerns.
6. `LibrarianAgent` performs embedding-based dedupe (`0.95` threshold).

## Postgres Data Model

Core entities:
- `signals`
- `ideas`
- `idea_signals` (Idea<->Signal graph edges)
- `analyses`, `enrichments`, `critiques`

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

## Notes

- `init_db()` creates the pgvector extension and tables automatically.