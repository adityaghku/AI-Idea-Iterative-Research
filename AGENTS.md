# AI Idea Iterative Research - Agent Instructions

## Setup & Environment

### Prerequisites
- Python 3.12+
- Docker + Docker Compose
- OpenCode server/API (`OPENCODE_BASE_URL` environment variable)

### Initial Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start Postgres with pgvector
docker compose up -d

# Create .env file with required variables (see README.md for template)
```

### Environment Variables
Required in `.env`:
- `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/idea_harvester`
- `DATABASE_URL_SYNC=postgresql+psycopg2://postgres:postgres@localhost:5432/idea_harvester`
- `OPENCODE_MODEL=deepseek/deepseek-chat` (or your preferred model)
- `OPENCODE_PROVIDER_ID=deepseek`
- `OPENCODE_MODEL_ID=deepseek-chat`

## Development Commands

### Running the Pipeline
```bash
# Single iteration
python main.py

# Multiple iterations
python main.py -n 5
python main.py --max-iterations 10
```

### Database Management
```bash
# Reset database (drops and recreates)
./scripts/reset_db.sh

# Initialize database tables (run after reset)
python -c "import asyncio; from db import init_db; asyncio.run(init_db())"
```

### Dashboard
```bash
# Start Streamlit dashboard
./scripts/start_dashboard.sh

# Or manually
cd dashboard
pip install -r requirements.txt
streamlit run app.py
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_embeddings.py

# Run with verbose output
pytest -v
```

## Architecture Notes

### 7-Stage Pipeline Flow
1. **ScoutAgent** - Collects problem signals and stores optional business metadata such as payment context, workaround cost, urgency, and model-provided relevance.
2. **SynthesizerAgent** - Creates idea candidates with signal links plus explicit monetization fields (`monetization_hypothesis`, `payer`, `pricing_model`, `wedge`, `why_now`).
3. **AnalyserAgent** - Scores ideas and stores both top-level score and structured subscores (`demand`, `gtm`, `build_risk`, `retention`, `monetization`, `validation`).
4. **DeepDiveAgent** - Adds market/feasibility enrichment plus pricing landscape, paid alternatives, switching-cost notes, and validation tests.
5. **CriticAgent** - Records adversarial concerns including monetization and validation blockers using the full enrichment payload.
6. **LibrarianAgent** - Embedding-based deduplication (threshold=0.7) that preserves the business fields when merging ideas.
7. **PortfolioAgent** - Distills recurring crossed-out rationale into compact next-run guidance for scout, synthesizer, and analyser.

### Database Schema
- Core: `signals`, `ideas`, `idea_signals`, `analyses`, `enrichments`, `critiques`
- Run/learning: `pipeline_runs`, `agent_runs`, `feedback_events`, `portfolio_memories`
- Graph: `idea_relations`, `signal_relations`
- Embeddings: `idea_embeddings` (pgvector)
- Dashboard cross-outs create explicit `feedback_events` with a required `reason_code`; `is_saved` remains workflow state and should not be treated as a training label.

### Key Dependencies
- `opencode-ai==0.1.0a36` - LLM client with custom session handling
- `pgvector==0.4.2` - Vector embeddings
- `langchain==1.2.15` - Agent framework
- `streamlit==1.56.0` - Dashboard

## Code Conventions

### Async Patterns
- Use `asyncio` throughout - no `asyncio.run()` wrappers in library code
- Database sessions: `get_session()` returns async session
- Agent methods are async and return lists of created objects

### Testing Constraints
- Tests verify no `asyncio.run()` in library code (`test_async_contract.py`)
- Use `pytest-asyncio` for async tests
- Test data is isolated per test

### Logging
- Structured JSON logging for LLM calls
- Logger via `utils.logger.get_logger(__name__)`

## Common Tasks

### Adding New Agent
1. Create file in `agents/` directory
2. Inherit from existing agent pattern
3. Implement async `run()` method
4. Update `main.py` pipeline if needed

### Database Schema Changes
1. Modify models in `db/db.py`
2. Prefer additive `ALTER TABLE ... IF NOT EXISTS` upgrades via `init_db()` / `init_db_sync()` for backwards-compatible changes
3. Run `reset_db.sh` only when you intentionally want a clean rebuild
4. Test both pipeline runtime and dashboard startup, because the dashboard reads ORM fields directly

### LLM Prompt Changes
- Prompts stored in `prompts/` directory
- Use `utils.prompts_utils` for template loading
- Keep prompt contracts aligned with persisted schema fields; do not add prompt keys without updating the corresponding agent parser/persistence
- Test with different signal types and with portfolio guidance present

### Feedback and Learning
- Only explicit crossed-out rationale should feed the learning loop
- Crossed-out feedback should always include a reason code; optional text is for auditability, not raw prompt injection
- Portfolio guidance should summarize recurring rejection patterns, not one-off comments

## Troubleshooting

### Database Connection Issues
- Verify Docker container is running: `docker ps`
- Check `.env` file has correct DATABASE_URL
- Run `reset_db.sh` if schema is corrupted

### LLM API Issues
- Verify `OPENCODE_BASE_URL` is accessible
- Check OpenCode server logs for session creation errors
- LLM client has workaround for session creation JSON body

### Pipeline Timeouts
- DeepDiveAgent has 900s timeout for web searches
- Consider reducing batch sizes or iteration counts
- Check network connectivity for external API calls