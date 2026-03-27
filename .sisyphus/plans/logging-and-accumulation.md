# Logging and Output Management Improvements

## TL;DR

> **Quick Summary**: Implement three related features to improve observability and output management: accumulation mode for stacking results across runs, verbose flag for controlling log output, and structured JSON logging for dashboard integration.
> 
> **Deliverables**:
> - Accumulation mode (merge ideas across runs)
> - Verbose logging control (default True)
> - Structured JSON logging for dashboard
> 
> **Estimated Effort**: Quick (3 related tasks)
> **Parallel Execution**: NO - sequential (A → B → C)
> **Critical Path**: A → B → C

---

## Context

### Original Request
User requested three features:
1. Keep run structure but make results stack (accumulate across runs)
2. --verbose flag as default (can be turned off)
3. Organize logging well for dashboard viewing

### Interview Summary
**Key Discussions**:
- Accumulation: Load existing ideas from idea-harvester.json, merge new ideas, deduplicate by title
- Verbose: Default True, use --no-verbose to disable, ERROR level when disabled
- Dashboard logging: JSON-structured logs with event type, URL, query, iteration

**Technical Decisions**:
- Accumulation merges on title (deduplicate)
- Keep top 20 when accumulating (vs top 10 in single run)
- Structured logs use JSON format for dashboard parsing
- Verbose affects logging level, not structured format

---

## Work Objectives

### Core Objective
Improve observability and output management for continuous iteration on accumulated history.

### Concrete Deliverables
1. Accumulation mode - ideas stack across runs
2. Verbose flag - control log verbosity
3. Structured logging - JSON format for dashboard

### Definition of Done
- [ ] Multiple runs accumulate ideas in idea-harvester.json
- [ ] --no-verbose reduces output to ERROR level
- [ ] Dashboard can parse structured JSON logs
- [ ] All existing tests pass

---

## TODOs

- [x] 1. Implement Accumulation Mode (Option A)

  **What to do**:
  - Modify `orchestrator._finalize()` to load existing ideas from idea-harvester.json
  - Merge new ideas with existing, deduplicate by idea_title
  - Keep top 20 ideas instead of top 10
  - Pass accumulated history to planner in `_build_stage_input()`

  **Must NOT do**:
  - Do not change run_task_id behavior (keep current run structure)
  - Do not modify database schema

  **Recommended Agent Profile**:
  - Category: `quick`
  - Reason: Single-file modification with clear logic
  - Skills: []

  **Parallelization**: Can start immediately

  **References**:
  - `agents/orchestrator.py:535-568` - _finalize() method to modify
  - `agents/orchestrator.py:245-280` - _build_stage_input() to add history

  **Acceptance Criteria**:
  - [ ] First run creates idea-harvester.json
  - [ ] Second run loads existing ideas and appends new ones
  - [ ] Duplicate titles are merged (keep highest score)
  - [ ] Top 20 ideas retained (not top 10)

  **QA Scenarios**:
  ```
  Scenario: First run creates file
    Tool: Bash
    Steps:
      1. Run `rm -f idea-harvester.json`
      2. Run `python main.py --max-iterations 1`
      3. Check `idea-harvester.json` exists and has top_ideas array
    Expected Result: File created with ideas
    Evidence: .sisyphus/evidence/task-01-first-run.json
  ```

  **Commit**: YES
  - Message: `feat(orchestrator): implement accumulation mode for ideas`
  - Files: agents/orchestrator.py

---

- [ ] 2. Implement Verbose Flag (Option B)

  **What to do**:
  - Add `--verbose` argument to main.py (default True, `--no-verbose` to disable)
  - Modify `setup_logging()` in logger.py to accept verbose parameter
  - Add `DEFAULT_VERBOSE = True` constant to config.py
  - When verbose=False, set logging level to ERROR

  **Must NOT do**:
  - Do not remove existing INFO logs
  - Do not change structured log format

  **Recommended Agent Profile**:
  - Category: `quick`
  - Reason: Simple argument and logging configuration
  - Skills: []

  **Parallelization**: Depends on Task 1 (can run in parallel)

  **References**:
  - `main.py:69-118` - Argument parsing to modify
  - `agents/logger.py:10-30` - setup_logging() to modify
  - `agents/config.py:34-40` - Constants section

  **Acceptance Criteria**:
  - [ ] `python main.py` shows INFO logs (default verbose=True)
  - [ ] `python main.py --no-verbose` shows only ERROR logs
  - [ ] `python main.py --verbose` explicitly enabled works

  **QA Scenarios**:
  ```
  Scenario: Verbose shows INFO logs
    Tool: Bash
    Steps:
      1. Run `python main.py --max-iterations 1 2>&1 | grep "\[INFO\]"`
      2. Assert INFO logs present
    Expected Result: INFO logs visible
    Evidence: .sisyphus/evidence/task-02-verbose.txt
  ```

  **Commit**: YES
  - Message: `feat(logging): add --verbose flag with default True`
  - Files: main.py, agents/logger.py, agents/config.py

---

- [ ] 3. Implement Structured Dashboard Logging (Option C)

  **What to do**:
  - Add structured JSON logging helper to logger.py
  - In researcher.py: Log every URL discovered with source query
  - In scraper.py: Log every URL scraped with content length and quality
  - In evaluator.py: Log filtering decisions (content rejected, reason)
  - In llm_client.py: Log prompt length and response length (already started)
  - Format: `{"event": "...", "url": "...", "iteration": N, ...}`

  **Must NOT do**:
  - Do not break existing log format for non-verbose mode
  - Do not log sensitive LLM responses

  **Recommended Agent Profile**:
  - Category: `quick`
  - Reason: Adding structured log calls to multiple files
  - Skills: []

  **Parallelization**: Depends on Task 2 (logging infrastructure)

  **References**:
  - `agents/researcher.py:70-140` - URL discovery logging
  - `agents/scraper.py:80-160` - Scraping logging
  - `agents/evaluator.py:85-100` - Filtering logging
  - `agents/llm_client.py:145-185` - LLM logging (already has some)

  **Acceptance Criteria**:
  - [ ] URL discoveries logged with `{"event": "url_discovered", ...}`
  - [ ] Scraped URLs logged with `{"event": "url_scraped", "chars": N, ...}`
  - [ ] Filtered content logged with `{"event": "content_filtered", "reason": "..."}`
  - [ ] LLM calls logged with `{"event": "llm_call", "prompt_chars": N, "response_chars": N}`

  **QA Scenarios**:
  ```
  Scenario: Structured logs are valid JSON
    Tool: Bash
    Steps:
      1. Run `python main.py --max-iterations 1 2>&1 | grep '{"event"'`
      2. Pipe to `python -m json.tool` to validate
    Expected Result: All structured logs are valid JSON
    Evidence: .sisyphus/evidence/task-03-json-logs.txt
  ```

  **Commit**: YES
  - Message: `feat(logging): add structured JSON logging for dashboard`
  - Files: agents/logger.py, agents/researcher.py, agents/scraper.py, agents/evaluator.py, agents/llm_client.py

---

## Final Verification Wave

**Integration Test Verification**:
- Run `python main.py --max-iterations 2` twice
- Verify second run accumulates ideas from first run
- Verify verbose output shows structured JSON logs
- Run `python main.py --no-verbose --max-iterations 1`
- Verify minimal output

---

## Commit Strategy

- **1**: `feat(orchestrator): implement accumulation mode for ideas` — agents/orchestrator.py
- **2**: `feat(logging): add --verbose flag with default True` — main.py, agents/logger.py, agents/config.py
- **3**: `feat(logging): add structured JSON logging for dashboard` — agents/logger.py, agents/researcher.py, agents/scraper.py, agents/evaluator.py, agents/llm_client.py

---

## Success Criteria

### Verification Commands
```bash
# Test accumulation mode
python main.py --max-iterations 1  # Creates initial file
python main.py --max-iterations 1  # Should accumulate

# Test verbose flag
python main.py --no-verbose --max-iterations 1  # Minimal output
python main.py --verbose --max-iterations 1      # Full output

# Test structured logs
python main.py --max-iterations 1 2>&1 | grep '{"event"' | python -m json.tool
```

### Final Checklist
- [ ] Accumulation mode works across multiple runs
- [ ] Verbose flag controls logging level
- [ ] Structured logs are valid JSON
- [ ] All existing tests pass