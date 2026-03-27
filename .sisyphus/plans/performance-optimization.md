# Performance Optimization for AI Idea Harvester

## TL;DR

> **Quick Summary**: Optimize agent pipeline for speed through parallelization, early filtering, and caching. Target 50-70% reduction in iteration time by parallelizing LLM calls, adding content pre-filtering, and implementing caching.**Deliverables**:
> - Async evaluation with parallel LLM calls
> - Early filtering to reduce LLM calls by 30-50%
> - LLM response caching with TTL
> - Performance benchmarks
> - Unit tests for evaluator, researcher, scraper

> **Estimated Effort**: Medium
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Test infrastructure → Async conversion → Filtering → Caching

---

## Context

### Original Request
User asked about token usage and LLM calls per iteration, then requested optimizationfocus on "Performance & Speed" - parallelization, early filtering, caching for faster iteration cycles.

### Interview Summary
**Key Discussions**:
- Evaluator is the bottleneck: sequential LLM calls per URL
- Researcher runs sequential DuckDuckGo searches
- Scraper processes URLs sequentially with 300s throttle
- LLM client already has async support
- No test infrastructure for evaluator/researcher/scraper

**Research Findings**:
- Evaluator (evaluator.py:40-45): Sequentialfor-loop calling LLM per content item
- Researcher (researcher.py:48-56): Sequential DDG searches
- Scraper (scraper.py:76-92): Sequential URL fetch with blocking throttle
- LLM client (llm_client.py:89-127): Already async-ready but agents use sync wrappers
- Database: No connection pooling, individual inserts instead of batch

### Metis Review
**Identified Gaps** (addressed):
- No test safety net → Add test infrastructure first
- External rate limits unknown → Add configurable concurrency limits
- Behavior preservation unclear → Verify output format unchanged
- No performance baseline → Add benchmarks

---

## Work Objectives

### Core Objective
Reduce iteration time by 50-70% through parallelization and caching, while preserving exact output format and behavior.

### Concrete Deliverables
- Async evaluator with parallel LLM calls (biggest impact)
- Async researcher with parallel searches
- Async scraper with concurrent fetching
- Early filtering to skip low-quality content before LLM
- LLM response cache with TTL
- Performance benchmarks using pytest-benchmark

### Definition of Done- [ ] `pytest tests/` passes with all new tests
- [ ] `pytest tests/test_performance.py --benchmark-only` shows measurable improvement
- [ ] `python main.py --max-iterations 1` completes successfully
- [ ] Output format unchanged: `idea-harvester.json`, `idea-harvester-top10.json`

### Must Have
- Parallel LLM calls in evaluator (asyncio.gather)
- Configurable concurrency limits for external APIs
- Early filtering before LLM evaluation
- Performance benchmarks with baseline comparison

### Must NOT Have (Guardrails)
- No changes to evaluation criteria or scoring algorithm
- No schema changes to SQLite database
- No changes to agent communication protocol
- No new dependencies without explicit approval
- No criteria requiring "user manually tests"
- No changes to output file formats

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: NO (only test_llm.py)
- **Automated tests**: Test infrastructure to be created as part of this work
- **Framework**: pytest + pytest-benchmark
- **Test approach**: Tests after implementation (unit tests + benchmarks)

### QA Policy
Every task includes agent-executed QA scenarios using:
- **pytest**: Unit tests with mocked dependencies
- **pytest-benchmark**: Performance measurement with baseline comparison
- **main.py --test-run**: End-to-end integration test

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — Test Infrastructure):
├── Task 1: Create pytest configuration and conftest.py [quick]
├── Task 2: Create mock fixtures for LLM, DDG, HTTP [quick]
├── Task 3: Write evaluator unit tests [unspecified-high]
├── Task 4: Write researcher unit tests [unspecified-high]
└── Task 5: Write scraper unit tests [unspecified-high]

Wave 2 (After Wave 1 — Parallelization):
├── Task 6: Convert evaluator to async with parallel LLM calls [deep]
├── Task 7: Convert researcher to async with parallel searches [deep]
├── Task 8: Convert scraper to async with concurrent fetching [deep]
└── Task 9: Add configurable concurrency limits [quick]

Wave 3 (After Wave 2 — Filtering & Caching):
├── Task 10: Add early filtering before LLM evaluation [unspecified-high]
├── Task 11: Add LLM response cache with TTL [quick]
└── Task 12: Add performance benchmarks [unspecified-high]

Wave FINAL (After ALL tasks — Verification):
├── Task F1: Performance benchmark comparison [oracle]
├── Task F2: Unit test verification [unspecified-high]
└── Task F3: Integration test with mock LLM [unspecified-high]

Critical Path: T1-T5 → T6-T9 → T10-T12 → F1-F3
Parallel Speedup: ~60% faster than sequential
```

### Dependency Matrix

- **1-5**: No dependencies (can start immediately)
- **6**: Depends on 3 (evaluator tests written)
- **7**: Depends on 4 (researcher tests written)
- **8**: Depends on 5 (scraper tests written)
- **9**: Depends on 6, 7, 8 (async conversion complete)
- **10**: Depends on 6 (evaluator async)
- **11**: Depends on 6 (evaluator async)
- **12**: Depends on 9 (all async conversions)
- **F1-F3**: Depend on 1-12 (all implementation complete)

### Agent Dispatch Summary

- **Wave 1**: 5 tasks — T1-T2 → `quick`, T3-T5 → `unspecified-high`
- **Wave 2**: 4 tasks — T6-T8 → `deep`, T9 → `quick`
- **Wave 3**: 3 tasks — T10 → `unspecified-high`, T11 → `quick`, T12 → `unspecified-high`
- **Final**: 3 tasks — F1 → `oracle`, F2-T3 → `unspecified-high`

---

## TODOs

- [x] 1. Create pytest configuration and conftest.py

  **What to do**:
  - Create `pytest.ini` with minimal configuration (testpaths, python_files, python_functions)
  - Create `tests/conftest.py` with shared fixtures for temp directories, mock databases
  - Create `tests/__init__.py` to make tests directory a package
  - Configure pytest-benchmark in pytest.ini

  **Recommended Agent Profile**:
  - Category: `quick`
  - Reason: Single configuration file creation
  - Skills: [] (no special skills needed)

  **Parallelization**: Can start immediately, no dependencies

  **References**:
  - `pytest.ini` standard configuration
  - `tests/conftest.py` pattern for shared fixtures

  **Acceptance Criteria**:
  - [ ] `pytest --collect-only` succeeds from project root
  - [ ] `pytest -v` runs without configuration errors

  **QA Scenarios**:
  ```
  Scenario: pytest configuration loaded
    Tool: Bash
    Steps:
      1. Run `pytest --collect-only` from project root
      2. Assert no configuration errors
    Expected Result: pytest collects tests without errors
    Evidence: .sisyphus/evidence/task-01-pytest-config.txt
  ```

  **Commit**: YES
  - Message: `test(infra): add pytest configuration`
  - Files: pytest.ini, tests/conftest.py, tests/__init__.py

---

- [x] 2. Create mock fixtures for LLM, DuckDuckGo, HTTP responses

  **What to do**:
  - Create `tests/fixtures/llm_fixtures.py` with mock LLM responses
  - Create `tests/fixtures/http_fixtures.py` with mock HTTP responses forscraping
  - Create `tests/fixtures/ddg_fixtures.py` with mock DuckDuckGo search results
  - Create `tests/fixtures/__init__.py` to export fixtures
  - Use `pytest.fixture` decorators with appropriate scopes

  **Recommended Agent Profile**:
  - Category: `quick`
  - Reason: Creating mock data structures
  - Skills: [] (no special skills needed)

  **Parallelization**: Can start immediately, no dependencies

  **References**:
  - `agents/llm_client.py` lines 89-127: LLM client interface to mock
  - `agents/researcher.py` lines 91-108: DDGS interface to mock
  - `agents/scraper.py` lines 140-200: HTTP response patterns to mock

  **Acceptance Criteria**:
  - [ ] Mock LLM fixture returns valid JSON matching evaluator expectations
  - [ ] Mock DDG fixture returns list of URLs
  - [ ] Mock HTTP fixture returns HTML content with extractable text

  **QA Scenarios**:
  ```
  Scenario: LLM mock returns valid response
    Tool: Bash
    Steps:
      1. Run `python -c "from tests.fixtures.llm_fixtures import mock_llm_response; print(mock_llm_response())"`
      2. Assert JSON output contains 'ideas' array
    Expected Result: Valid JSON with ideas array
    Evidence: .sisyphus/evidence/task-02-llm-mock.json
  ```

  **Commit**: YES
  - Message: `test(fixtures): add mock fixtures for LLM, DDG, HTTP`
  - Files: tests/fixtures/*.py

---

- [x] 3. Write evaluator unit tests

  **What to do**:
  - Create `tests/test_evaluator.py`
  - Test `_extract_ideas()` with mocked LLM responses
  - Test score calculation and ranking
  - Test edge cases: empty content, malformed responses, timeout handling
  - Use fixtures from task 2 for mock responses

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Reason: Requires understanding evaluator logic and LLM interaction
  - Skills: [] (no special skills needed)

  **Parallelization**: Can start after task 2

  **References**:
  - `agents/evaluator.py` lines 40-165: Main evaluation logic
  - `agents/evaluator.py` lines 79-85: Content validation to test
  - `agents/evaluator.py` lines 87-165: LLM extraction to mock

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_evaluator.py -v` passes all tests
  - [ ] Tests cover: normal case, empty content, malformed LLM response, timeout

  **QA Scenarios**:
  ```
  Scenario: Evaluator tests pass
    Tool: Bash
    Steps:
      1. Run `pytest tests/test_evaluator.py -v`
      2. Assert all tests pass
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-03-evaluator-tests.txt
  ```

  **Commit**: YES
  - Message: `test(agents): add unit tests for evaluator`
  - Files: tests/test_evaluator.py

---

- [x] 4. Write researcher unit tests

  **What to do**:
  - Create `tests/test_researcher.py`
  - Test `research()` with mocked DDG responses
  - Test URL deduplication and filtering
  - Test edge cases: no results, rate limiting, timeout
  - Use fixtures from task 2 for mock DDG responses

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Reason: Requires understanding researcher logic and DDG interaction
  - Skills: [] (no special skills needed)

  **Parallelization**: Can start after task 2

  **References**:
  - `agents/researcher.py` lines 30-89: Main research logic
  - `agents/researcher.py` lines 60-68: URL filtering to test
  - `agents/researcher.py` lines 91-108: DDGS search to mock

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_researcher.py -v` passes all tests
  - [ ] Tests cover: normal case, empty results, duplicate URLs, timeout

  **QA Scenarios**:
  ```
  Scenario: Researcher tests pass
    Tool: Bash
    Steps:
      1. Run `pytest tests/test_researcher.py -v`
      2. Assert all tests pass
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-04-researcher-tests.txt
  ```

  **Commit**: YES
  - Message: `test(agents): add unit tests for researcher`
  - Files: tests/test_researcher.py

---

- [x] 5. Write scraper unit tests

  **What to do**:
  - Create `tests/test_scraper.py`
  - Test `scrape()` with mocked HTTP responses
  - Test content extraction quality scoring
  - Test edge cases: no content, timeout, malformed HTML
  - Use fixtures from task 2 for mock HTTP responses

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Reason: Requires understanding scraper logic and HTTP interaction
  - Skills: [] (no special skills needed)

  **Parallelization**: Can start after task 2

  **References**:
  - `agents/scraper.py` lines 30-200: Main scraping logic
  - `agents/scraper.py` lines 119-125: Quality score calculation
  - `agents/scraper.py` lines 140-200: Content extraction

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_scraper.py -v` passes all tests
  - [ ] Tests cover: normal case, no content, timeout, malformed HTML

  **QA Scenarios**:
  ```
  Scenario: Scraper tests pass
    Tool: Bash
    Steps:
      1. Run `pytest tests/test_scraper.py -v`
      2. Assert all tests pass
    Expected Result: All tests pass
    Evidence: .sisyphus/evidence/task-05-scraper-tests.txt
  ```

  **Commit**: YES
  - Message: `test(agents): add unit tests for scraper`
  - Files: tests/test_scraper.py

---

- [x] 6. Convert evaluator to async with parallel LLM calls

  **What to do**:
  - Convert `Evaluator.evaluate()` to async
  - Use `asyncio.gather()` to parallelize `_extract_ideas()` calls across content items
  - Add semaphore-based rate limiting for concurrent LLM calls (default:5 concurrent)
  - Update orchestrator to await async evaluator
  - Preserve exact output format

  **Must NOT do**:
  - Do not change evaluation criteria or scoring algorithm
  - Do not change output format

  **Recommended Agent Profile**:
  - Category: `deep`
  - Reason: Core architecture change requiring careful async handling
  - Skills: [] (no special skills needed)

  **Parallelization**: Depends on task 3 (evaluator tests)

  **References**:
  - `agents/llm_client.py` lines 89-127: Async pattern to follow
  - `agents/llm_client.py` lines 179-184: Context manager pattern
  - `agents/evaluator.py` lines 40-65: Main evaluate() to convert
  - `agents/evaluator.py` lines 87-165: LLM extraction to parallelize

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_evaluator.py -v` still passes after conversion
  - [ ] Multiple content items processed concurrently (not sequentially)
  - [ ] Output format unchanged: same `EvaluatorOutput` structure

  **QA Scenarios**:
  ```
  Scenario: Async evaluator processes multiple items in parallel
    Tool: Bash
    Steps:
      1. Run unit test with timing assertions
      2. Assert total time < (N items * time_per_item)
    Expected Result: Parallel processing faster than sequential
    Evidence: .sisyphus/evidence/task-06-async-eval-timing.txt

  Scenario: Evaluator output format unchanged
    Tool: Bash
    Steps:
      1. Run `python main.py --max-iterations 1`
      2. Check `idea-harvester.json` structure
    Expected Result: JSON contains 'top_ideas' with correct schema
    Evidence: .sisyphus/evidence/task-06-output-format.json
  ```

  **Commit**: YES
  - Message: `refactor(evaluator): convert to async with parallel LLM calls`
  - Files: agents/evaluator.py, agents/orchestrator.py

---

- [x] 7. Convert researcher to async with parallel searches

  **What to do**:
  - Convert `Researcher.research()` to async
  - Use `asyncio.gather()` with semaphore to parallelize DDG searches
  - Add configurable concurrency limit (default: 3 concurrent)
  - Use `aiohttp` instead of `requests` for async HTTP
  - Update orchestrator to await async researcher

  **Must NOT do**:
  - Do not change search query logic
  - Do not change output format

  **Recommended Agent Profile**:
  - Category: `deep`
  - Reason: Requires async HTTP client migration
  - Skills: [] (no special skills needed)

  **Parallelization**: Depends on task 4 (researcher tests)

  **References**:
  - `agents/researcher.py` lines 30-89: Main research logic to convert
  - `agents/researcher.py` lines 91-108: DDGS interface to async-ify
  - `agents/llm_client.py` lines 89-127: Async pattern to follow

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_researcher.py -v` still passes
  - [ ] Multiple queries processed concurrently
  - [ ] Output format unchanged: same `ResearcherOutput` structure

  **QA Scenarios**:
  ```
  Scenario: Async researcher processes queries in parallel
    Tool: Bash
    Steps:
      1. Run unit test with timing assertions
      2. Assert search time < (N queries * time_per_query)
    Expected Result: Parallel search faster than sequential
    Evidence: .sisyphus/evidence/task-07-async-research-timing.txt
  ```

  **Commit**: YES
  - Message: `refactor(researcher): convert to async with parallel searches`
  - Files: agents/researcher.py, agents/orchestrator.py

---

- [x] 8. Convert scraper to async with concurrent fetching

  **What to do**:
  - Convert `Scraper.scrape()` to async
  - Use `asyncio.gather()` with semaphore for concurrent URL fetching
  - Replace `time.sleep()` with async-friendly rate limiting
  - Use `aiohttp` instead of `requests` for async HTTP
  - Use `asyncio.Semaphore` for per-domain rate limiting
  - Update orchestrator to await async scraper

  **Must NOT do**:
  - Do not change content extraction logic
  - Do not remove rate limiting (convert to async version)

  **Recommended Agent Profile**:
  - Category: `deep`
  - Reason: Requires async HTTP migration and rate limiting redesign
  - Skills: [] (no special skills needed)

  **Parallelization**: Depends on task 5 (scraper tests)

  **References**:
  - `agents/scraper.py` lines 30-200: Main scraping logic to convert
  - `agents/scraper.py` lines 59-67: Rate limiting to convert to async
  - `agents/config.py` line 35: `DEFAULT_SCRAPER_COOLDOWN_SECONDS`

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_scraper.py -v` still passes
  - [ ] Multiple URLs fetched concurrently (not sequentially)
  - [ ] Rate limiting preserved (async semaphore instead of sleep)
  - [ ] Output format unchanged: same `ScraperOutput` structure

  **QA Scenarios**:
  ```
  Scenario: Async scraper fetches URLs concurrently
    Tool: Bash
    Steps:
      1. Run unit test with timing assertions
      2. Assert fetch time < (N URLs * time_per_url)
    Expected Result: Concurrent fetching faster than sequential
    Evidence: .sisyphus/evidence/task-08-async-scrape-timing.txt
  ```

  **Commit**: YES
  - Message: `refactor(scraper): convert to async with concurrent fetching`
  - Files: agents/scraper.py, agents/orchestrator.py

---

- [ ] 9. Add configurable concurrency limits

  **What to do**:
  - Add to `config.py`: `MAX_LLM_CONCURRENCY`, `MAX_SEARCH_CONCURRENCY`, `MAX_FETCH_CONCURRENCY`
  - Add default values: LLM=5, Search=3, Fetch=3
  - Thread concurrency limits through to async functions
  - Add to `RunConfig` dataclass for runtime configuration

  **Recommended Agent Profile**:
  - Category: `quick`
  - Reason: Configuration addition
  - Skills: [] (no special skills needed)

  **Parallelization**: Depends on tasks 6, 7, 8 (async conversions complete)

  **References**:
  - `agents/config.py`: Configuration patterns
  - `agents/config.py` lines 34-39: Constants to extend

  **Acceptance Criteria**:
  - [ ] Concurrency limits configurable via `RunConfig`
  - [ ] Default values applied when not specified
  - [ ] Each agent respects its concurrency limit

  **QA Scenarios**:
  ```
  Scenario: Concurrency limits applied
    Tool: Bash
    Steps:
      1. Run `python -c "from agents import RunConfig; c = RunConfig(..., max_llm_concurrency=3); print(c)"`
      2. Assert concurrency fields present
    Expected Result: Config contains concurrency limits
    Evidence: .sisyphus/evidence/task-09-config.txt
  ```

  **Commit**: YES
  - Message: `feat(config): add configurable concurrency limits`
  - Files: agents/config.py

---

- [ ] 10. Add early filtering before LLM evaluation

  **What to do**:
  - Create `agents/filter.py` with `pre_filter_content()` function
  - Add filtering criteria:
    - Minimum content length (increase from 50 to 200 chars)
    - Keyword relevance check (AI, startup, product, idea keywords)
    - Language detection (English-only filter)
    - Boilerplate ratio check (navigation/footer content)
  - Call filter in ` evaluator._extract_ideas()` before LLM call
  - Log filtered items for transparency

  **Must NOT do**:
  - Do not filter out potentially valuable content
  - Do not change scoring logic

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Reason: Requires balancing filtering vs quality
  - Skills: [] (no special skills needed)

  **Parallelization**: Depends on task 6 (evaluator async)

  **References**:
  - `agents/evaluator.py` lines 79-85: Current minimal filtering
  - `agents/scraper.py` lines 119-125: Quality score patterns
  - `db/idea_harvester_db.py` lines 686-744: URL filtering patterns

  **Acceptance Criteria**:
  - [ ] Content filtered before LLM call reduces evaluation count
  - [ ] Filter preserves high-quality content
  - [ ] Filter logs show items filtered and reason

  **QA Scenarios**:
  ```
  Scenario: Content filter reduces LLM calls
    Tool: Bash
    Steps:
      1. Run main.py with test data
      2. Check logs for "filtered before LLM" messages
    Expected Result: Fewer LLM calls than content items
    Evidence: .sisyphus/evidence/task-10-filter-stats.txt

  Scenario: High-quality content not filtered
    Tool: Bash
    Steps:
      1. Run unit test with known-good content
      2. Assert content passes filter
    Expected Result: Good content not filtered
    Evidence: .sisyphus/evidence/task-10-filter-quality.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): add early filtering before LLM evaluation`
  - Files: agents/filter.py, agents/evaluator.py

---

- [ ] 11. Add LLM response cache with TTL

  **What to do**:
  - Create `agents/cache.py` with `ResponseCache` class
  - Use in-memory cache with TTL (default: 1 hour)
  - Cache by content hash (similar to `idea_fingerprint`)
  - Add cache hit/miss metrics logging
  - Integrate into evaluator before LLM call

  **Must NOT do**:
  - Do not cache across different runs (scope to run_task_id)
  - Do not cache malformed responses

  **Recommended Agent Profile**:
  - Category: `quick`
  - Reason: Standalone caching module
  - Skills: [] (no special skills needed)

  **Parallelization**: Depends on task 6 (evaluator async)

  **References**:
  - `db/idea_harvester_schema.sql` lines 83-98: Fingerprint pattern
  - `agents/evaluator.py` lines 87-165: Where to add cache lookup

  **Acceptance Criteria**:
  - [ ] Cache stores responses with TTL
  - [ ] Cache hit avoids LLM call
  - [ ] Cache miss triggers LLM call and stores result

  **QA Scenarios**:
  ```
  Scenario: Cache hit avoids LLM call
    Tool: Bash
    Steps:
      1. Run main.py twice with same content
      2. Check logs for "cache hit" messages
    Expected Result: Second run shows cache hits
    Evidence: .sisyphus/evidence/task-11-cache-hit.txt

  Scenario: Cache expires after TTL
    Tool: Bash
    Steps:
      1. Set TTL to 1 second
      2. Wait 2 seconds
      3. Check cache miss
    Expected Result: Expired content shows cache miss
    Evidence: .sisyphus/evidence/task-11-cache-expire.txt
  ```

  **Commit**: YES
  - Message: `feat(agents): add LLM response cache with TTL`
  - Files: agents/cache.py, agents/evaluator.py

---

- [ ] 12. Add performance benchmarks

  **What to do**:
  - Create `tests/test_performance.py` using pytest-benchmark
  - Add benchmarks for:
    - Evaluator: sequential vs parallel LLM calls
    - Researcher: sequential vs parallel searches
    - Scraper: sequential vs concurrent fetching
  - Add baseline comparison feature
  - Document expected improvement (50-70%)

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
  - Reason: Requires understanding all async conversions
  - Skills: [] (no special skills needed)

  **Parallelization**: Depends on task 9 (all async conversions with limits)

  **References**:
  - `pytest-benchmark` documentation
  - `tests/test_evaluator.py`, `tests/test_researcher.py`, `tests/test_scraper.py` for test patterns

  **Acceptance Criteria**:
  - [ ] `pytest tests/test_performance.py --benchmark-only` runs successfully
  - [ ] Benchmarks show measurable improvement over baseline
  - [ ] Results include timing comparison

  **QA Scenarios**:
  ```
  Scenario: Benchmarks run successfully
    Tool: Bash
    Steps:
      1. Run `pytest tests/test_performance.py --benchmark-only`
      2. Assert benchmarks complete without errors
    Expected Result: All benchmarks complete
    Evidence: .sisyphus/evidence/task-12-benchmark-results.txt

  Scenario: Performance improvement measurable
    Tool: Bash
    Steps:
      1. Run benchmarks with baseline comparison
      2. Assert improvement >= 50%
    Expected Result: Measurable speedup
    Evidence: .sisyphus/evidence/task-12-improvement.txt
  ```

  **Commit**: YES
  - Message: `test(perf): add performance benchmarks`
  - Files: tests/test_performance.py

---

## Final Verification Wave

**Performance Benchmark Verification**:
- Run `pytest tests/test_performance.py --benchmark-only`
- Compare against baseline (recorded before optimization)
- Verify ≥50% improvement in iteration time

**Unit Test Verification**:
- Run `pytest tests/test_evaluator.py tests/test_researcher.py tests/test_scraper.py`
- All tests pass with mocked dependencies

**Integration Test Verification**:
- Run `python main.py --max-iterations 1` with mock LLM
- Verify output format unchanged in `idea-harvester.json`

---

## Commit Strategy

- **1**: `test(infra): add pytest configuration and fixtures` — pytest.ini, conftest.py
- **2-5**: `test(agents): add unit tests for evaluator, researcher, scraper` — tests/
- **6-8**: `refactor(agents): convert to async for parallelization` — agents/
- **9**: `feat(config): add configurable concurrency limits` — agents/config.py
- **10-11**: `feat(agents): add early filtering and caching` — agents/
- **12**: `test(perf): add performance benchmarks` — tests/test_performance.py

---

## Success Criteria

### Verification Commands
```bash
# All unit tests pass
pytest tests/test_evaluator.py tests/test_researcher.py tests/test_scraper.py -v

# Performance benchmarks show improvement
pytest tests/test_performance.py --benchmark-only --benchmark-compare

# Integration test completes
python main.py --max-iterations 1

# Output format preserved
python -c "import json; d=json.load(open('idea-harvester.json')); assert 'top_ideas' in d"
```

### Final Checklist
- [ ] All unit tests pass
- [ ] Performance improved by ≥50%
- [ ] Integration test passes
- [ ] Output format unchanged
- [ ] No new dependencies added