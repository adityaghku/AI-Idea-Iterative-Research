# Multi-Agent AI Idea Harvester: Iterative Reasoning Refactor

## TL;DR

> **Quick Summary**: Fix dashboard bug, add scraper prioritization, then refactor multi-agent idea harvester from linear extraction to iterative reasoning by adding Chain-of-Thought (CoT) fields, evidence-based auditing, pain-driven planning, and adversarial vetting.
> 
> **Deliverables**:
> - Fixed `dashboard.py` score_breakdown UndefinedError
> - Updated `agents/scraper.py` with Reddit/X URL prioritization
> - Updated `agents/config.py` with `thinking`/`reasoning` fields in all output schemas
> - Updated `agents/planner.py` with pain-driven prompts and CoT reasoning
> - Updated `agents/evaluator.py` with citations requirement for scores>70
> - Updated `agents/tagger.py` with CoT reasoning field
> - New `agents/critic.py` for adversarial idea vetting
> - Updated `agents/orchestrator.py` with Stage.CRITIC pipeline integration
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: NO - sequential (each task builds on previous)
> **Critical Path**: Config → Planner → Evaluator → Tagger → Critic → Orchestrator

---

## Context

### Original Request
User wants to refactor the Multi-Agent AI Idea Harvester to follow 2026 best practices for autonomous reasoning. The system should move from "linear extraction" to "iterative reasoning."

### Interview Summary
**Key Discussions**:
- **CoT Requirement**: All Planner, Evaluator, Tagger outputs must include `thinking`/`reasoning` field at TOP of JSON schema
- **Evidence-Based Auditing**: Evaluator must provide `citations` for scores >70; cap at 50 if no evidence
- **Pain-Driven Planning**: Planner queries should focus on user friction/pains, not generic "AI startup ideas"
- **CriticAgent Creation**: New adversarial agent that vets "Strong" ideas and finds failure reasons
- **Orchestrator Update**: Insert CriticAgent after Evaluator; Learner only processes vetted ideas

### Research Findings
- **Current Schema**: PlannerOutput has no thinking field; Idea dataclass has no citations field
- **Current Prompts**: Planner uses sector-based queries ("find AI startup ideas in [Sector]")
- **Current Pipeline**: PLANNER → RESEARCHER → SCRAPER → EVALUATOR → TAGGER → LEARNER → FINALIZE
- **Evaluator Concurrency**: Set to 1 (previously 5) to prevent LLM overload
- **Stage Enum**: Located in `config.py` lines 9-17

---

## Work Objectives

### Core Objective
Transform the multi-agent idea harvester from a linear extraction pipeline to an iterative reasoning system with visible chain-of-thought, evidence-based evaluation, and adversarial vetting.

### Concrete Deliverables
- [ ] `agents/config.py`: Add `thinking: str` field to PlannerOutput, EvaluatorOutput, TaggerOutput; Add `citations: list[str]` to Idea; Add CriticInput/CriticOutput dataclasses; Add Stage.CRITIC
- [ ] `agents/planner.py`: Add reasoning to prompt; Change queries from sector-based to pain-driven
- [ ] `agents/evaluator.py`: Add reasoning/citations to prompt; Enforce citation requirement for scores >70
- [ ] `agents/tagger.py`: Add reasoning to prompt
- [ ] `agents/critic.py`: NEW FILE - adversarial vetting agent
- [ ] `agents/orchestrator.py`: Add Stage.CRITIC to enum; Initialize CriticAgent; Route after EVALUATOR

### Definition of Done
- [ ] All agents produce JSON with `thinking`/`reasoning` field as first field
- [ ] Evaluator caps score at 50 when no citations provided for high scores
- [ ] Planner generates pain/friction focused queries
- [ ] CriticAgent receives Evaluator's "Strong" ideas and produces failure analyses
- [ ] Orchestrator passes only vetted ideas to Learner

### Must Have
- `thinking`/`reasoning` field at TOP of JSON schema (not buried in nested object)
- Citations field for Evaluator ideas with score >70
- Pain-driven query generation in Planner
- CriticAgent that outputs 3-5 failure reasons per idea
- Stage.CRITIC inserted after EVALUATOR in pipeline

### Must NOT Have (Guardrails)
- NO changes to database schema (ideas table structure stays same)
- NO changes to Scraper or Researcher agents
- NO breaking changes to existing API/CLI interface
- NO AI-generatedslop like excessive comments or generic variable names

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest available)
- **Automated tests**: Tests-after (no TDD for this refactor)
- **Framework**: pytest
- **Agent-Executed QA**: ALWAYS (mandatory for all tasks)

### QA Policy
Every task MUST include agent-executed QA scenarios.

---

## Execution Strategy

### Sequential Execution (Each task builds on previous)

```
Pre-Req 0: Fix dashboard score_breakdown bug (BLOCKING)
  ↓
Pre-Req 0b: Add Reddit/X prioritization to scraper
  ↓
Task 1: Update config.py dataclasses (foundation)
  ↓
Task 2: Update planner.py with CoT + pain-driven queries
  ↓
Task 3: Update evaluator.py with CoT + citations
  ↓
Task 4: Update tagger.py with CoT
  ↓
Task 5: Create critic.py (new agent)
  ↓
Task 6: Update orchestrator.py to integrate CriticAgent
  ↓
Task 7: Integration test + verification
```

### Dependency Matrix

- **Task0**: —— Dashboard (blocking)
- **Task0b**: —— Scraper (NICE-TO-HAVE)
- **Task1**: — — 2-6, config
- **Task2**: 1 — —
- **Task3**: 1 — 6
- **Task4**: 1 — —
- **Task5**: 1 — 6
- **Task6**: 3, 5 — 7
- **Task7**: 6 — final

---

## TODOs

### Pre-Requisite: Fix Dashboard Bug (BLOCKING)

- [x] 0. Fix Dashboard score_breakdown UndefinedError

  **What to do**:
  - In `dashboard.py` line 856-860, change empty dict `{}` to dict with default values
  - Update `parse_idea()` to return `{"novelty": 0, "feasibility": 0, "market_potential": 0}` instead of `{}`
  - This ensures template access `idea.score_breakdown.novelty` works even for ideas without breakdown data

  **Must NOT do**:
  - Do NOT change the template (bracket notation would be more defensive but requires more changes)
  - Do NOT modify `score_breakdown` structure in database

  **References**:
  - `dashboard.py:856-860` - `parse_idea()` function
  - `dashboard.py:451-453` - template using dot notation

  **Acceptance Criteria**:
  - [ ] `parse_idea()` returns dict with default `novelty`, `feasibility`, `market_potential` keys
  - [ ] Dashboard loads without Jinja2 UndefinedError
  - [ ] Ideas without score_breakdown still display correctly

  **QA Scenarios**:
  ```
  Scenario: Dashboard loads with empty score_breakdown
    Tool: Bash (python3)
    Steps:
      1. Run dashboard app
      2. Navigate to main page
      3. Verify no UndefinedError
    Expected Result: Dashboard renders successfully
    Evidence: .sisyphus/evidence/task-0-dashboard-fix.txt
  ```

---

### Pre-Requisite: Add Reddit/X Prioritization to Scraper

- [x] 0b. Add URL Priority Scoring for Reddit and X

  **What to do**:
  - Add a `_get_url_priority()` method to `ScraperAgent` that scores URLs
  - Reddit URLs (reddit.com) get +2 priority
  - X/Twitter URLs (x.com, twitter.com) get +2 priority
  - Other URLs get baseline priority
  - Sort `urls` by priority score before `[:5]` slice (line 76)
  - Add logging to show prioritized URLs

  **Priority Logic**:
  ```python
  def _get_url_priority(self, url: str) -> int:
      """Higher score = higher priority."""
      if "reddit.com" in url:
          return 2
      if "x.com" in url or "twitter.com" in url:
          return 2
      return 1  # baseline
  ```
  **Must NOT do**:
  - Do NOT change the URL fetching logic
  - Do NOT increase the 5-URL limit
  - Do NOT remove existing deduplication

  **References**:
  - `agents/scraper.py:71-76` - URL processing logic
  - `agents/scraper.py:57-69` - `scrape()` method start

  **Acceptance Criteria**:
  - [ ] `_get_url_priority()` method added to ScraperAgent
  - [ ] URLs sorted by priority before scraping
  - [ ] Reddit and X URLs appear first in scrape order
  - [ ] Logging shows prioritized order

  **QA Scenarios**:
  ```
  Scenario: Reddit URLs prioritized over other URLs
    Tool: Bash (python3)
    Steps:
      1. Create ScraperInput with mixed URLs: [generic, reddit, generic]
      2. Call ScraperAgent.scrape()
      3. Verify Reddit URL is processed first
    Expected Result: Reddit URLs appear first in processing order
    Evidence: .sisyphus/evidence/task-0b-priority-test.log
  ```

---

- [x] 1. Update config.py with Thinking Fields and Critic Dataclasses

  **What to do**:
  - Add `thinking: str` field to `PlannerOutput` (after line 58)
  - Add `thinking: str` field to each `Idea` in `EvaluatorOutput` (line 141-149)
  - Add `citations: list[str]` field to `Idea` dataclass (line 141-149)
  - Add `thinking: str` field to `TaggerOutput` (line 188-197)
  - Add new `CriticInput` dataclass with `run_task_id`, `iteration_number`, `ideas: list[Idea]`
  - Add new `CriticOutput` dataclass with `vetted_ideas: list[dict]`, `thinking: str`
  - Add `CRITIC = "critic"` to Stage enum (line 14, after EVALUATOR)
  - Update `to_dict()` methods to include new fields

  **Must NOT do**:
  - Do NOT change existing field names or types
  - Do NOT modify database schema
  - Do NOT change Idea.__init__ signature (keep backward compatibility)

  **References**:
  - `agents/config.py:9-17` - Stage enum location
  - `agents/config.py:57-70` - PlannerOutput dataclass
  - `agents/config.py:141-164` - Idea dataclass
  - `agents/config.py:188-197` - TaggerOutput dataclass
  - `agents/config.py:209-231` - LearnerOutput as reference for new dataclass structure

  **Acceptance Criteria**:
  - [ ] `PlannerOutput` has `thinking: str` field
  - [ ] `Idea` has `thinking: str` and `citations: list[str]` fields
  - [ ] `TaggerOutput` has `thinking: str` field
  - [ ] `CriticInput` and `CriticOutput` dataclasses exist
  - [ ] `Stage.CRITIC` exists in enum
  - [ ] All `to_dict()` methods include new fields
  - [ ] Python imports succeed: `from agents.config import PlannerOutput, Idea, TaggerOutput, CriticInput, CriticOutput, Stage`

  **QA Scenarios**:
  ```
  Scenario: Config imports correctly
    Tool: Bash (python3 -c)
    Preconditions: Virtual environment activated
    Steps:
      1. Run: python3 -c "from agents.config import PlannerOutput, Idea, TaggerOutput, CriticInput, CriticOutput, Stage; print('OK')"
    Expected Result: Output contains "OK"
    Evidence: .sisyphus/evidence/task-1-import-test.txt
  ```

- [x] 2. Refactor Planner to Pain-Driven Queries with CoT

  **What to do**:
  - Update `_build_prompt()` method (line 78-167) to instruct model to think out loud
  - Add reasoning section at START of JSON output schema
  - Change query focus from "AI startup ideas in [Sector]" to "user pains/friction in [Domain]"
  - Add examples of pain-driven queries
  - Update `_validate_plan()` to extract and validate `thinking` field
  - Ensure `thinking` is included in `PlannerOutput` construction (line 40-45)

  **Pain-Driven Query Examples**:
  - OLD: "AI startup ideas in healthcare"
  - NEW: "what tasks do doctors hate doing manually that could be automated"
  - OLD: "AI applications for finance"
  - NEW: "frustrating manual workflows in accounting that waste time"

  **Must NOT do**:
  - Do NOT remove learned criteria context (keep `evaluation_criteria` in prompt)
  - Do NOT change `PlannerInput` structure
  - Do NOT change method signatures

  **References**:
  - `agents/planner.py:78-167` - _build_prompt method to modify
  - `agents/planner.py:40-45` - PlannerOutput construction
  - `agents/planner.py:169-184` - _validate_plan method to update

  **Acceptance Criteria**:
  - [ ] Prompt instructs model to "think out loud about user pains and friction"
  - [ ] JSON schema has `thinking` as FIRST field
  - [ ] Prompt includes pain-driven query examples
  - [ ] `_validate_plan()` extracts `thinking` field
  - [ ] `PlannerOutput` is constructed with `thinking` field populated
  - [ ] Queries focus on specific user problems, not generic startup concepts

  **QA Scenarios**:
  ```
  Scenario: Planner generates pain-driven queries
    Tool: Bash (python3)
    Preconditions: Config changes from Task 1 applied
    Steps:
      1. Create test input with goal "Find AI automation opportunities"
      2. Call PlannerAgent.plan() with the input
      3. Check that search_queries contain pain/friction keywords
      4. Verify thinking field is populated in output
    Expected Result: thinking field exists, queries mention "frustration", "manual", "waste", or similar pain words
    Evidence: .sisyphus/evidence/task-2-planner-output.json
  ```

- [x] 3. Update Evaluator with CoT and Citations

  **What to do**:
  - Update `_llm_extract_ideas_with_criteria()` prompt (line 122-179) to require reasoning
  - Add `thinking` as FIRST field in JSON schema
  - Add `citations: list[str]` field after detailed scores
  - Add logic to cap score at 50 if score > 70 and citations is empty
  - Update Idea construction (line 245-261) to include thinking and citations
  - Update `_build_criteria_prompt()` to mention citation requirement

  **Citation Logic**:
  ```python
  # In idea construction:  if score > 70 and not citations:
      score = min(score, 50)  # Cap at 50 if no evidence
  ```

  **Must NOT do**:
  - Do NOT change the weighted score calculation logic
  - Do NOT remove detailed_scores mapping (keep backward compatibility)
  - Do NOT change async signature of `evaluate()`

  **References**:
  - `agents/evaluator.py:100-186` - _llm_extract_ideas_with_criteria method
  - `agents/evaluator.py:245-261` - Idea construction
  - `agents/evaluator.py:267-300` - _build_criteria_prompt method
  - `agents/config.py:141-164` - Idea dataclass (updated in Task 1)

  **Acceptance Criteria**:
  - [ ] Prompt instructs model to "think out loud" as first output
  - [ ] JSON schema has `thinking` as FIRST field
  - [ ] JSON schema has `citations` field after detailed_scores
  - [ ] Score is capped at 50 if score > 70 and citations empty
  - [ ] `Idea` object includes `thinking` and `citations` fields
  - [ ] Prompt mentions "for scores above 70, you MUST provide citations"

  **QA Scenarios**:
  ```
  Scenario: Evaluator caps high scores without citations
    Tool: Bash (python3)
    Preconditions: Config changes applied, evaluator updated
    Steps:
      1. Create mock content with hypothetical high-potential idea
      2. Call EvaluatorAgent._llm_extract_ideas_with_criteria()
      3. Check that ideas with score > 70 have citations OR score is capped
    Expected Result: If score > 70 and citations empty, score <= 50
    Evidence: .sisyphus/evidence/task-3-evaluator-test.json
  
  Scenario: Evaluator includes thinking in output
    Tool: Bash (python3)
    Steps:
      1. Call EvaluatorAgent.evaluate() with sample content
      2. Verify thinking field exists in each Idea
    Expected Result: All returned ideas have non-empty thinking field
    Evidence: .sisyphus/evidence/task-3-thinking-test.json
  ```

- [x] 4. Update Tagger with CoT

  **What to do**:
  - Update `_tag_batch()` prompt (line 130-160) to require reasoning
  - Add `thinking` as FIRST field in JSON schema before the array
  - Change JSON structure to object with `thinking` and `tagged_ideas` fields
  - Update validation to extract thinking field
  - Ensure `TaggerOutput` includes thinking field

  **JSON Structure Change**:
  ```json
  {
    "thinking": "Analysis of the ideas and why I chose these tags...",
    "tagged_ideas": [
      { "idea_title": "...", "tags": [...], ... }
    ]
  }
  ```

  **Must NOT do**:
  - Do NOT change batch processing logic
  - Do NOT change tag categories (keep DEFAULT_TAG_CATEGORIES)
  - Do NOT change async signature

  **References**:
  - `agents/tagger.py:117-198` - _tag_batch method to modify
  - `agents/tagger.py:77-111` - execute method (returns TaggerOutput)
  - `agents/config.py:188-197` - TaggerOutput dataclass (updated in Task 1)

  **Acceptance Criteria**:
  - [ ] Prompt instructs model to "think about the categorization strategy"
  - [ ] JSON schema has `thinking` as FIRST field
  - [ ] Response structure changed from array to object with `thinking` and `tagged_ideas`
  - [ ] `TaggerOutput` includes thinking field
  - [ ] `_tag_batch()` extracts thinking field from response

  **QA Scenarios**:
  ```
  Scenario: Tagger includes thinking in output
    Tool: Bash (python3)
    Preconditions: Config and other agents updated
    Steps:
      1. Call TaggerAgent.execute() with sample ideas
      2. Verify thinking field exists in TaggerOutput
    Expected Result: thinking field exists and is non-empty
    Evidence: .sisyphus/evidence/task-4-tagger-test.json
  ```

- [x] 5. Create CriticAgent for Adversarial Vetting

  **What to do**:
  - Create new file `agents/critic.py`
  - Implement `CriticAgent` class with `vet(input_data: CriticInput) -> CriticOutput` method
  - Build prompt that acts as "Adversarial Red Teamer"
  - For each "Strong" idea (verdict="Strong" or score>=75), find 3-5 failure reasons:
    - Market risk: "Why won't customers pay?"
    - Platform risk: "What if the AI platform changes?"
    - Technical debt: "What's hard to maintain?"
    - Competition risk: "Who else is doing this?"
    - Timing risk: "Why is now the wrong time?"
  - Output `vetted_ideas` with failure reasons; ideas that survive get `verdict: "vetted"`
  - Include `thinking` field in output

  **CriticAgent Structure**:
  ```python
  class CriticAgent:
      def __init__(self, db_path: str = DEFAULT_DB_PATH):
          self.db_path = db_path
          self.logger = get_logger()
      
      def vet(self, input_data: CriticInput) -> CriticOutput:
          """Vet ideas by finding failure reasons."""
          # Filter to Strong ideas
          # For each, find 3-5 failure reasons
          # Return vetted list with failure analyses
  ```

  **Prompt Template**:
  ```
  You are an adversarial red teamer. Your job is to find reasons why this idea WILL FAIL.
  
  For each "Strong" idea, identify 3-5 failure reasons covering:
  - Market risk: Why won't customers pay? Is the market too small?
  - Platform risk: What if the AI platform changes? API costs increase?
  - Technical debt: What's hard to build? What breaks at scale?
  - Competition risk: Who else is doing this? Why would they win?
  - Timing risk: Why is now the wrong time? What needs to happen first?
  
  Be harsh. Be critical. Find the weaknesses.
  ```

  **Must NOT do**:
  - Do NOT modify existing agents
  - Do NOT access database for this agent (stateless)
  - Do NOT change verdict for non-Strong ideas (pass through)

  **References**:
  - `agents/evaluator.py` - Reference for LLM integration pattern
  - `agents/config.py:209-231` - LearnerInput/Output as reference for dataclass structure
  - `agents/planner.py` - Reference for agent class structure

  **Acceptance Criteria**:
  - [ ] `agents/critic.py` file created
  - [ ] `CriticAgent` class with `vet(input_data: CriticInput) -> CriticOutput` method
  - [ ] Prompt instructs model to "find reasons this will FAIL"
  - [ ] For Strong ideas, outputs 3-5 failure reasons
  - [ ] Non-Strong ideas pass through unchanged
  - [ ] Output includes `thinking` field
  - [ ] Python imports succeed: `from agents.critic import CriticAgent`

  **QA Scenarios**:
  ```
  Scenario: CriticAgent finds failure reasons for Strong ideas
    Tool: Bash (python3)
    Preconditions: critic.py created
    Steps:
      1. Create CriticInput with one Strong idea (score=85)
      2. Call CriticAgent.vet()
      3. Verify output has failure_reasons with 3-5 items
    Expected Result: failure_reasons has length >= 3
    Evidence: .sisyphus/evidence/task-5-critic-test.json
  
  Scenario: CriticAgent passes through non-Strong ideas
    Tool: Bash (python3)
    Steps:
      1. Create CriticInput with one Marginal idea (score=50)
      2. Call CriticAgent.vet()
      3. Verify idea passes through unchanged
    Expected Result: idea in output unchanged, no failure_reasons added
    Evidence: .sisyphus/evidence/task-5-critic-passthrough.json
  ```

- [x] 6. Update Orchestrator to Integrate CriticAgent

  **What to do**:
  - Add `from .critic import CriticAgent` import (after line 49)
  - Add `CriticInput` to imports from config
  - Initialize `CriticAgent` in `self.agents` dict (line 75-82)
  - Add Stage.CRITIC to stages list (line212-218), after EVALUATOR
  - Add `_build_stage_input` case for `Stage.CRITIC` (after line 370)
  - Add `_execute_agent` case for `Stage.CRITIC` (after line 470)
  - Modify `_build_stage_input` for `Stage.LEARNER` to receive vetted ideas from Critic

  **Pipeline Change**:
  ```
  OLD: PLANNER → RESEARCHER → SCRAPER → EVALUATOR → LEARNER
  NEW: PLANNER → RESEARCHER → SCRAPER → EVALUATOR → CRITIC → LEARNER
  ```

  **Stage Input Flow**:
  ```python
  # In _build_stage_input for Stage.CRITIC:
  elif stage == Stage.CRITIC:
      evaluator_data = get_knowledge(...)
      return {
          "run_task_id": self.config.run_task_id,
          "iteration_number": iteration_number,
          "ideas": evaluator_data.get("ideas", []),
      }
  
  # In _build_stage_input for Stage.LEARNER (modified):
  elif stage == Stage.LEARNER:
      critic_data = get_knowledge(..., f"critic_output_{iteration_number}")
      evaluator_data = get_knowledge(..., f"evaluator_output_{iteration_number}")
      # Use vetted ideas from critic if available, else evaluator ideas
      ideas = critic_data.get("vetted_ideas", []) if critic_data else evaluator_data.get("ideas", [])
  ```

  **Must NOT do**:
  - Do NOT change database access patterns
  - Do NOT modify other stage handlers
  - Do NOT break backward compatibility with existing runs

  **References**:
  - `agents/orchestrator.py:9-23` - Imports section
  - `agents/orchestrator.py:75-82` - agents dict initialization
  - `agents/orchestrator.py:212-218` - stages list
  - `agents/orchestrator.py:298-396` - _build_stage_input method
  - `agents/orchestrator.py:398-535` - _execute_agent method

  **Acceptance Criteria**:
  - [ ] `CriticAgent` imported and initialized in orchestrator
  - [ ] `Stage.CRITIC` added to stages list after `EVALUATOR`
  - [ ] `_build_stage_input` has case for `Stage.CRITIC`
  - [ ] `_execute_agent` has case for `Stage.CRITIC`
  - [ ] `Stage.LEARNER` receives vetted ideas from Critic (not rawfrom Evaluator)
  - [ ] Pipeline prints "[6/7] Critic: Vetting ideas..."
  - [ ] Critic output stored to knowledge (`critic_output_{iteration}`)

  **QA Scenarios**:
  ```
  Scenario: Orchestrator runs Critic stage
    Tool: Bash (python3)
    Preconditions: All agents updated
    Steps:
      1. Create Orchestrator instance
      2. Mock a minimal run iteration
      3. Verify Critic stage is called after Evaluator
    Expected Result: Output shows "Critic: Vetting ideas..." stage
    Evidence: .sisyphus/evidence/task-6-orchestrator-run.log
  
  Scenario: Learner receives vetted ideas
    Tool: Bash (python3)
    Steps:
      1. Mock evaluator output with Strong idea
      2. Run Critic stage
      3. Check Learner input has vetted ideas from Critic
    Expected Result: Learner input ideas comefrom critic_output, not evaluator_output
    Evidence: .sisyphus/evidence/task-6-learner-input.json
  ```

- [x] 7. Integration Test and Verification

  **What to do**:
  - Run full pipeline test with sample goal
  - Verify all agents produce outputs with `thinking` field
  - Verify Evaluator caps high scores without citations
  - Verify Critic vettes Strong ideas
  - Verify Learner receives vetted ideas
  - Check database stores thinking/citations correctly

  **Test Script**:
  ```python
  # test_integration.py
  from agents.orchestrator import Orchestrator
  
  orch = Orchestrator(goal="Find AI automation opportunities for small businesses")
  orch.initialize()
  # Run 1 iteration
  orch._run_iteration(1)
  # Verify outputs in database
  ```

  **Must NOT do**:
  - Do NOT modify production database (use test database)
  - Do NOT skip any verification step

  **References**:
  - `agents/orchestrator.py:206-232` - _run_iteration method
  - `tests/` directory if exists for test patterns

  **Acceptance Criteria**:
  - [ ] Full pipeline runs without errors
  - [ ] All agent outputs have `thinking` field
  - [ ] Evaluator outputs have `citations` field (or capped scores)
  - [ ] Critic produces `vetted_ideas` with failure reasons
  - [ ] Learner receives vetted ideas
  - [ ] Database stores all new fields correctly

  **QA Scenarios**:
  ```
  Scenario: Full pipeline integration test
    Tool: Bash (python3)
    Preconditions: All code changes applied
    Steps:
      1. Set up test database
      2. Run Orchestrator for 1 iteration
      3. Query database for thinking fields
      4. Query database for citations fields
      5. Query database for critic output
    Expected Result: All fields populated correctly
    Evidence: .sisyphus/evidence/task-7-integration-test.log
  
  Scenario: Thinking fields flow through pipeline
    Tool: Bash (python3)
    Steps:
      1. Run pipeline
      2. Check planner_output_X has thinking field
      3. Check evaluator_output_X ideas have thinking field
      4. Check tagger_output_X has thinking field
      5. Check critic_output_X has thinking field
    Expected Result: All outputs have non-empty thinking field
    Evidence: .sisyphus/evidence/task-7-thinking-flow.json
  ```

---

## Final Verification Wave

- [x] F1. **Plan Compliance Audit** — `oracle`
  Verify all Must Have items implemented, all Must NOT Have avoided, all acceptance criteria met.

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `python3 -m py_compile agents/*.py`, check for lint issues, verify no `as any` or type ignore comments.

- [x] F3. **Real Manual QA** — `unspecified-high`
  Run full pipeline with test goal, verify all stages execute, check database outputs.

- [x] F4. **Scope Fidelity Check** — `deep`
  Verify all 5 tasks from user request implemented, no scope creep, no missing features.

---

## Commit Strategy

- **1**: `refactor(config): add thinking/citations fields and CriticAgent dataclasses` — agents/config.py
- **2**: `refactor(planner): add CoT reasoning and pain-driven queries` — agents/planner.py
- **3**: `refactor(evaluator): add CoT reasoning and citation requirement` — agents/evaluator.py
- **4**: `refactor(tagger): add CoT reasoning field` — agents/tagger.py
- **5**: `feat(critic): add CriticAgent for adversarial idea vetting` — agents/critic.py
- **6**: `refactor(orchestrator): integrate CriticAgent into pipeline` — agents/orchestrator.py
- **7**: `test: verify iterative reasoning refactor integration` — test files if any

---

## Success Criteria

### Verification Commands
```bash
# Import verification
python3 -c "from agents.config import PlannerOutput, Idea, TaggerOutput, CriticInput, CriticOutput, Stage; print('Config OK')"

# Agent imports
python3 -c "from agents.planner import PlannerAgent; from agents.evaluator import EvaluatorAgent; from agents.tagger import TaggerAgent; from agents.critic import CriticAgent; print('Agents OK')"

# Orchestrator import
python3 -c "from agents.orchestrator import Orchestrator; print('Orchestrator OK')"
```

### Final Checklist
- [x] All Must Have items present
- [x] All Must NOT Have items absent
- [x] All tests pass
- [x] Thinking fields in all agent outputs
- [x] Citations field in Evaluator ideas
- [x] CriticAgent vets Strong ideas
- [x] Pipeline includes CRITIC stage after EVALUATOR