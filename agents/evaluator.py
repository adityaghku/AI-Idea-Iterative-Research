"""Evaluator agent - scores ideas using learned criteria from internet research."""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

from .config import (
    EvaluatorInput,
    EvaluatorOutput,
    Idea,
    IdeaScore,
    DEFAULT_DB_PATH,
)
from .meta_learning import MetaLearningAgent
from .llm_client import async_llm_complete_json
from .logger import get_logger, log_structured
from .filter import ContentFilter
from .cache import ResponseCache


# Source window: long articles keep head + tail so scoring sees intro and conclusion.
_SOURCE_HEAD_CHARS = 2400
_SOURCE_TAIL_CHARS = 1200
_SOURCE_MAX_SINGLE = 5200

# Shown in structured explanation blocks; other non-empty fields are appended generically.
_EXPLAINER_HANDLED_KEYS = frozenset(
    {
        "idea_title",
        "idea_summary",
        "thinking",
        "detailed_scores",
        "total_score",
        "citations",
        "strengths",
        "risks",
        "advice",
        "verdict",
        "red_flags",
        "target_market",
        "problem_solved",
        "business_plan",
        "competitors",
        "tags",
    }
)


def _source_excerpt(text: str) -> str:
    """Prefer head + tail for long text so the model sees how the piece ends."""
    t = (text or "").strip()
    if len(t) <= _SOURCE_MAX_SINGLE:
        return t
    head = t[:_SOURCE_HEAD_CHARS]
    tail = t[-_SOURCE_TAIL_CHARS:]
    return (
        f"{head}\n\n[... middle of article omitted for length ...]\n\n"
        f"{tail}"
    )


def _scoring_rubric_prompt() -> str:
    return """
=== SCORING RUBRIC (0–100 integers) ===
Apply consistently. total_score should reflect detailed_scores and the criteria above.

detailed_scores (include all that apply; use null only if not assessable):
- problem_clarity: Is the problem and mobile user clearly defined?
- mobile_native_advantage: Does this leverage mobile-specific features (camera, GPS, sensors, offline) or is it just a website wrapper?
- solo_founder_feasibility: Realistic scope for a solo developer to build and launch on app stores?
- monetization_clarity: Plausible mobile monetization path (freemium, subscriptions, in-app purchases)?
- market_timing, distribution_path, defensibility, technical_feasibility: as relevant.

Anchors (per dimension): 0–30 weak, 31–55 mixed, 56–75 solid, 76–90 strong, 91+ exceptional (rare).

total_score: Weight the dimensions by importance in the LEARNED CRITERIA; stay consistent with detailed_scores.

If total_score > 70, citations MUST include short verbatim quotes copied from the SOURCE EXCERPT below (evidence for strong scores).
If you cannot quote the source, keep total_score at or below 70.

=== ANTI-HALLUCINATION ===
- Ground claims in the SOURCE EXCERPT; label speculation as such in strengths/risks.
- Do not invent metrics, users, funding, or competitor names not present in the source unless clearly marked as hypothetical.
- When a FAILURE PATTERN matches, list it in red_flags (non-empty when clearly applicable).
"""


class EvaluatorAgent:
    """Scores ideas using dynamically learned criteria about startup success."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, max_concurrent: int = 1):
        self.db_path = db_path
        self.max_concurrent = max_concurrent
        self.meta_learning = MetaLearningAgent(db_path=db_path)
        self.logger = get_logger()

    async def evaluate(self, input_data: EvaluatorInput) -> EvaluatorOutput:
        """Evaluate extracted content and score ideas using learned criteria."""
        self.logger.info(
            f"[iter {input_data.iteration_number}] Evaluator starting: {len(input_data.extracted_content)} content items"
        )

        evaluation_criteria = self.meta_learning.research_startup_criteria(
            input_data.run_task_id
        )

        all_ideas = []
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def extract_with_semaphore(content_item: dict[str, Any]) -> list[Idea]:
            async with semaphore:
                return await self._extract_ideas(
                    content_item,
                    input_data.run_task_id,
                    evaluation_criteria,
                    input_data.iteration_number,
                )

        tasks = [extract_with_semaphore(item) for item in input_data.extracted_content]
        results = await asyncio.gather(*tasks)

        for result in results:
            all_ideas.extend(cast(list[Idea], result))

        top_ideas = all_ideas[:15]

        high_scoring = [i for i in top_ideas if i.score >= 75]
        low_scoring = [i for i in top_ideas if i.score < 60]
        self.meta_learning.update_criteria_from_results(
            input_data.run_task_id,
            [i.to_dict() for i in high_scoring],
            [i.to_dict() for i in low_scoring],
        )

        summary = f"Evaluated {len(input_data.extracted_content)} sources, extracted {len(all_ideas)} ideas, selected top {len(top_ideas)}"
        self.logger.info(
            f"[iter {input_data.iteration_number}] Evaluator complete: {len(top_ideas)} ideas"
        )

        return EvaluatorOutput(
            ideas=top_ideas,
            iteration_summary=summary,
        )

    async def _extract_ideas(
        self,
        content_item: dict[str, Any],
        run_task_id: str,
        evaluation_criteria: dict[str, Any],
        iteration_number: int = 0,
    ) -> list[Idea]:
        """Extract and score ideas from content using learned criteria."""

        content = content_item.get("content", {})
        url = content_item.get("url", "")

        text = content.get("text", "")
        if not text:
            return []

        is_worthy, reason = ContentFilter.is_content_worthy(text, url)
        if not is_worthy:
            self.logger.info(f"Filtered content from {url}: {reason}")
            log_structured(
                "content_filtered", url=url, reason=reason, iteration=iteration_number
            )
            return []

        return await self._llm_extract_ideas_with_criteria(
            text, url, evaluation_criteria
        )

    async def _llm_extract_candidates(
        self,
        excerpt: str,
        criteria_context: str,
        url: str,
    ) -> list[dict[str, Any]]:
        """Phase 1: extract grounded candidate mobile app ideas (no numeric scoring)."""
        prompt = f"""{criteria_context}
You extract mobile app ideas that are actually supported by the source text.

FOCUS ON MOBILE APPS: These should be ideas specifically for iOS/Android mobile applications, not web SaaS or desktop software.

SOURCE URL (reference only; do not treat URL content as extra facts): {url}

SOURCE EXCERPT:
\"\"\"
{excerpt}
\"\"\"

Return a JSON array with 1–3 items. Each item is an object. Required:
- "idea_title": short name for the mobile app
- "idea_summary": what the mobile app does (grounded in the excerpt)

Encouraged:
- "supporting_quotes": array of short verbatim phrases copied from the SOURCE EXCERPT
- "mobile_features": which mobile features it would use (camera, GPS, notifications, offline, sensors)
- Any other brief fields you find useful (e.g. "notes", "assumptions") — only if grounded or clearly labeled as inference.

Rules:
- Do not invent funding, metrics, named users, or competitors not in the excerpt.
- Skip ideas that are not meaningfully present in the text.
- Ensure ideas are appropriate for mobile apps (not web SaaS or desktop software).

Output JSON only: an array."""

        raw = await async_llm_complete_json(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.28,
        )
        if isinstance(raw, dict):
            raw = raw.get("ideas", raw.get("candidates", []))
        if not isinstance(raw, list):
            self.logger.warning(
                "Extract phase: expected JSON array, got %s",
                type(raw).__name__,
            )
            return []
        out: list[dict[str, Any]] = [x for x in raw if isinstance(x, dict)]
        return out

    async def _llm_evaluate_candidates(
        self,
        excerpt: str,
        url: str,
        candidates: list[dict[str, Any]],
        criteria_context: str,
        rubric: str,
    ) -> list[dict[str, Any]]:
        """Phase 2: score and enrich; model may add any helpful fields."""
        import json

        candidates_json = json.dumps(candidates, ensure_ascii=False, indent=2)
        prompt = f"""{criteria_context}
{rubric}

SOURCE URL: {url}

SOURCE EXCERPT:
\"\"\"
{excerpt}
\"\"\"

CANDIDATES (from extraction; refine, merge, or drop weak items as needed):
{candidates_json}

Return a JSON array of evaluated ideas. For each idea include at least:
- idea_title, idea_summary
- detailed_scores (object with numeric 0–100 fields; include ai_advantage, solo_founder_feasibility, monetization_clarity, and other dimensions you assessed)
- total_score (0–100 integer)
- strengths, risks, advice (arrays of strings)
- verdict (short string)
- red_flags (array; use non-empty entries when failure patterns apply)
- citations: array of short verbatim quotes from SOURCE EXCERPT supporting scores above 70

You may add any additional top-level fields useful for downstream use (e.g. open_questions, go_to_market_hypothesis, differentiation) — avoid empty filler.

Output JSON only: an array."""

        raw = await async_llm_complete_json(
            prompt=prompt,
            max_tokens=6000,
            temperature=0.22,
        )
        if isinstance(raw, dict):
            raw = raw.get("ideas", raw.get("evaluated_ideas", [raw]))
        if not isinstance(raw, list):
            self.logger.warning(
                "Evaluate phase: expected JSON array, got %s",
                type(raw).__name__,
            )
            return []
        return [x for x in raw if isinstance(x, dict)]

    async def _llm_extract_ideas_with_criteria(
        self,
        text: str,
        url: str,
        evaluation_criteria: dict[str, Any],
    ) -> list[Idea]:
        """Two-phase: extract candidates, then score with criteria + rubric."""

        content_hash = ResponseCache.content_hash(text)
        cache = ResponseCache.get_instance()

        is_hit, cached_ideas = cache.get(content_hash)
        if is_hit:
            self.logger.info(f"Cache hit for {url[:80]}...")
            return cached_ideas

        self.logger.info(f"Cache miss for {url[:80]}...")

        excerpt = _source_excerpt(text)
        criteria_context = self._build_criteria_prompt(evaluation_criteria)
        rubric = _scoring_rubric_prompt()

        candidates = await self._llm_extract_candidates(
            excerpt, criteria_context, url
        )
        if not candidates:
            return []

        ideas_data = await self._llm_evaluate_candidates(
            excerpt, url, candidates, criteria_context, rubric
        )
        if not ideas_data:
            return []

        ideas = self._build_ideas_from_responses(
            ideas_data, candidates, url
        )

        cache.set(content_hash, ideas)
        return ideas

    def _build_ideas_from_responses(
        self,
        ideas_data: list[dict[str, Any]],
        candidates: list[dict[str, Any]],
        url: str,
    ) -> list[Idea]:
        ideas: list[Idea] = []
        for idx, idea_data in enumerate(ideas_data):
            extraction = None
            if idx < len(candidates):
                extraction = candidates[idx]
            elif idea_data.get("idea_title"):
                for c in candidates:
                    if c.get("idea_title") == idea_data.get("idea_title"):
                        extraction = c
                        break

            detailed = idea_data.get("detailed_scores")
            if not isinstance(detailed, dict):
                detailed = {}

            novelty = detailed.get("mobile_native_advantage")
            feasibility = detailed.get("solo_founder_feasibility")
            market_potential = detailed.get("monetization_clarity")

            if novelty is None or feasibility is None or market_potential is None:
                missing = []
                if novelty is None:
                    missing.append("mobile_native_advantage")
                if feasibility is None:
                    missing.append("solo_founder_feasibility")
                if market_potential is None:
                    missing.append("monetization_clarity")
                self.logger.warning(
                    "Missing evaluation scores for idea: %s", missing
                )

            score_breakdown = IdeaScore(
                novelty=novelty if novelty is not None else 0,
                feasibility=feasibility if feasibility is not None else 0,
                market_potential=market_potential if market_potential is not None else 0,
            )

            total_score = idea_data.get("total_score", score_breakdown.total())
            try:
                total_score = int(total_score)
            except (TypeError, ValueError):
                total_score = score_breakdown.total()

            thinking = str(idea_data.get("thinking", "") or "")
            citations = idea_data.get("citations", [])
            if citations is None:
                citations = []
            if not isinstance(citations, list):
                citations = [str(citations)]
            else:
                citations = [str(c) for c in citations if c is not None]

            if total_score > 70 and not citations:
                self.logger.warning(
                    "Score capped to 70 for '%s' - no citations provided",
                    idea_data.get("idea_title", "Untitled"),
                )
                total_score = 70

            explanation_parts = self._format_evaluator_explanation(idea_data)

            idea_payload: dict[str, Any] = {
                "evaluation_method": "learned_criteria_two_phase",
                "extraction": extraction,
            }
            for k, v in idea_data.items():
                idea_payload[k] = v

            idea = Idea(
                thinking=thinking,
                idea_title=str(idea_data.get("idea_title") or "Untitled"),
                idea_summary=str(idea_data.get("idea_summary") or ""),
                source_urls=[url],
                score=int(total_score),
                score_breakdown=score_breakdown,
                evaluator_explain="\n".join(explanation_parts),
                citations=citations,
                idea_payload=idea_payload,
            )
            ideas.append(idea)

        return ideas

    def _format_evaluator_explanation(self, idea_data: dict[str, Any]) -> list[str]:
        """Human-readable summary; only includes sections that have content."""
        parts: list[str] = []
        if idea_data.get("verdict"):
            parts.append(f"Verdict: {idea_data.get('verdict')}")
            parts.append("")

        if idea_data.get("target_market"):
            parts.append(f"Target Market: {idea_data.get('target_market')}")
            parts.append("")

        if idea_data.get("problem_solved"):
            parts.append(f"Problem Solved: {idea_data.get('problem_solved')}")
            parts.append("")

        strengths = idea_data.get("strengths") or []
        if strengths:
            parts.append("Strengths:")
            parts.extend(f"  + {s}" for s in strengths)
            parts.append("")

        risks = idea_data.get("risks") or []
        if risks:
            parts.append("Risks:")
            parts.extend(f"  - {r}" for r in risks)
            parts.append("")

        if idea_data.get("advice"):
            parts.append(f"Advice: {idea_data.get('advice')}")
            parts.append("")

        red_flags = idea_data.get("red_flags") or []
        if red_flags:
            parts.append("Red Flags Detected:")
            parts.extend(f"  - {rf}" for rf in red_flags)
            parts.append("")

        bp = idea_data.get("business_plan")
        if isinstance(bp, dict) and bp:
            parts.append("Business Plan:")
            if bp.get("pricing_model"):
                parts.append(f"  Pricing: {bp.get('pricing_model')}")
            if bp.get("revenue_streams"):
                rs = bp.get("revenue_streams")
                if isinstance(rs, list):
                    parts.append(f"  Revenue: {', '.join(str(x) for x in rs)}")
            if bp.get("key_features"):
                kf = bp.get("key_features")
                if isinstance(kf, list):
                    parts.append(f"  Features: {', '.join(str(x) for x in kf)}")
            if bp.get("launch_strategy"):
                parts.append(f"  Launch: {bp.get('launch_strategy')}")
            if bp.get("customer_acquisition"):
                parts.append(f"  Acquisition: {bp.get('customer_acquisition')}")
            parts.append("")

        competitors = idea_data.get("competitors")
        if competitors:
            if isinstance(competitors, list):
                parts.append(f"Competitors: {', '.join(str(c) for c in competitors)}")
            else:
                parts.append(f"Competitors: {competitors}")
            parts.append("")

        extras = {
            k: v
            for k, v in idea_data.items()
            if k not in _EXPLAINER_HANDLED_KEYS
            and v not in (None, "", [], {})
        }
        for key in sorted(extras.keys()):
            val = extras[key]
            if isinstance(val, (dict, list)):
                parts.append(f"{key}:")
                try:
                    parts.append(json.dumps(val, ensure_ascii=False, indent=2)[:1200])
                except (TypeError, ValueError):
                    parts.append(str(val)[:800])
            else:
                parts.append(f"{key}: {val}")
            parts.append("")

        while parts and parts[-1] == "":
            parts.pop()
        return parts

    def _build_criteria_prompt(self, criteria: dict[str, Any]) -> str:
        """Build prompt section for evaluation criteria + market context."""

        lines = [
            "=== LEARNED STARTUP SUCCESS CRITERIA ===",
            "",
            "Success Factors (with relative importance):",
        ]

        for factor in criteria.get("success_factors", [])[:8]:
            lines.append(
                f"\n{factor['factor']} (Importance: {factor['importance']}, "
                f"Weight: {factor.get('weight', 0.1):.0%})"
            )
            lines.append(f"  Description: {factor['description']}")
            lines.append("  What to look for:")
            for indicator in factor.get("indicators", [])[:3]:
                lines.append(f"    - {indicator}")

        lines.extend(
            [
                "",
                "FAILURE PATTERNS TO AVOID (Red Flags):",
            ]
        )

        for pattern in criteria.get("failure_patterns", [])[:6]:
            lines.append(
                f"\n- {pattern['pattern']} (Severity: {pattern['red_flag_level']})"
            )
            lines.append(f"  {pattern['description']}")
            lines.append("  Warning signs:")
            for sign in pattern.get("warning_signs", [])[:3]:
                lines.append(f"    - {sign}")

        mi = criteria.get("market_insights") or {}
        if mi:
            lines.extend(["", "MARKET INSIGHTS (use to calibrate timing and differentiation):"])
            for key in sorted(mi.keys()):
                val = mi[key]
                if isinstance(val, list):
                    lines.append(f"- {key}: {', '.join(str(x) for x in val[:12])}")
                elif val:
                    lines.append(f"- {key}: {val}")

        lines.extend(
            [
                "",
                "=== END CRITERIA ===",
            ]
        )

        return "\n".join(lines)
