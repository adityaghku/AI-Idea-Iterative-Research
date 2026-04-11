"""Deep Dive agent - enriches top ideas with research."""

from __future__ import annotations

import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Enrichment, Idea
from utils.llm_client import async_llm_complete_json
from utils.logger import get_logger
from utils.prompts_utils import load_prompt

logger = get_logger(__name__)


class DeepDiveAgent:
    """Agent 4: Enriches top ideas with competitors, app landscape, tech stack."""

    PASSES = 3

    async def run(self, session: AsyncSession, ideas: list[Idea]) -> list[Enrichment]:
        """Run deep dive to enrich top ideas."""
        prompt_template = load_prompt("deep_dive.md")
        logger.info(
            "Deep Dive starting for %d ideas with %d passes each",
            len(ideas),
            self.PASSES,
        )

        enrichments = []
        for idx, idea in enumerate(ideas, start=1):
            logger.info("Deep Dive idea %d/%d: %s", idx, len(ideas), idea.title)
            idea_text = f"""Title: {idea.title}
Problem: {idea.problem}
Target User: {idea.target_user}
Solution: {idea.solution}"""

            pass_outputs: list[dict] = []
            previous_output: dict = {}
            for pass_number in range(1, self.PASSES + 1):
                prior_context = "No prior pass outputs."
                if previous_output:
                    prior_context = json.dumps(previous_output, ensure_ascii=True)
                refinement_directive = self._build_refinement_directive(
                    previous_output=previous_output,
                    pass_number=pass_number,
                )

                prompt = f"""{prompt_template}

Idea:
{idea_text}

Deep-dive pass: {pass_number} of {self.PASSES}
Prior accepted output (JSON):
{prior_context}
Refinement directive:
{refinement_directive}
"""
                logger.debug("Enriching pass %d/%d: %s", pass_number, self.PASSES, idea.title)
                result = await async_llm_complete_json(
                    prompt,
                    max_tokens=3000,
                    temperature=0.3,
                    agent_name="deep_dive",
                    pass_number=pass_number,
                )
                pass_candidate = result if isinstance(result, dict) else {}
                gated_output, issues = self._apply_quality_gates(
                    output=pass_candidate,
                    previous_output=previous_output,
                    pass_number=pass_number,
                )
                if issues:
                    logger.warning(
                        "Deep dive quality gate issues (idea=%s pass=%d): %s",
                        idea.title,
                        pass_number,
                        "; ".join(issues),
                    )

                if gated_output:
                    previous_output = self._merge_outputs(previous_output, gated_output)
                    logger.info(
                        "Deep Dive pass %d/%d accepted for '%s'",
                        pass_number,
                        self.PASSES,
                        idea.title,
                    )
                pass_outputs.append(previous_output)

            enrich_data = self._aggregate_pass_outputs(pass_outputs)
            competitor_names, competitor_details = self._normalize_competitors(
                enrich_data.get("competitors", [])
            )

            enrichment = await session.scalar(
                select(Enrichment).where(Enrichment.idea_id == idea.id)
            )
            if not enrichment:
                enrichment = Enrichment(
                    idea_id=idea.id,
                    feasibility="unknown",
                )
                session.add(enrichment)

            enrichment.competitors = competitor_names
            enrichment.competitor_details = competitor_details
            enrichment.app_landscape = enrich_data.get("app_landscape", {})
            enrichment.monetization_strategies = enrich_data.get("monetization_strategies", [])
            enrichment.tech_stack = enrich_data.get("tech_stack", [])
            enrichment.feasibility = enrich_data.get("feasibility", "unknown")
            enrichment.confidence = enrich_data.get("confidence")
            enrichment.evidence_snippets = enrich_data.get("evidence_snippets", [])
            enrichment.risks = enrich_data.get("risks", [])
            enrichment.go_to_market_hypotheses = enrich_data.get("go_to_market_hypotheses", [])
            enrichment.additional_notes = enrich_data.get("additional_notes")
            enrichments.append(enrichment)

            idea.status = "enriched"
            logger.info(
                "Deep Dive finalized '%s': competitors=%d evidence=%d risks=%d confidence=%s",
                idea.title,
                len(enrichment.competitors or []),
                len(enrichment.evidence_snippets or []),
                len(enrichment.risks or []),
                enrichment.confidence,
            )

        await session.commit()
        logger.info("Completed %d enrichments", len(enrichments))
        return enrichments

    def _aggregate_pass_outputs(self, pass_outputs: list[dict]) -> dict:
        """Merge pass outputs with later passes taking precedence."""
        final = {
            "competitors": [],
            "app_landscape": {},
            "monetization_strategies": [],
            "tech_stack": [],
            "feasibility": "unknown",
            "confidence": None,
            "evidence_snippets": [],
            "risks": [],
            "go_to_market_hypotheses": [],
            "additional_notes": None,
        }
        for output in pass_outputs:
            if not isinstance(output, dict):
                continue
            for key in final.keys():
                if key in output and output[key] not in (None, "", []):
                    final[key] = output[key]
        return final

    def _normalize_competitors(self, competitors_raw: list) -> tuple[list[str], list[dict]]:
        """Normalize competitors into names and structured details."""
        names: list[str] = []
        details: list[dict] = []
        for comp in competitors_raw or []:
            if isinstance(comp, dict):
                name = str(comp.get("name", "")).strip()
                summary = str(comp.get("summary", "")).strip()
                url = str(comp.get("url", "")).strip()
            else:
                name = str(comp).strip()
                summary = ""
                url = ""
            if not name:
                continue
            if not summary:
                summary = "A competitor in this problem space."
            details.append({
                "name": name,
                "summary": summary,
                "url": url or None,
            })
            names.append(name)
        return names, details

    def _build_refinement_directive(self, previous_output: dict, pass_number: int) -> str:
        if pass_number == 1:
            return (
                "Generate a strong baseline output with high-confidence competitor and "
                "evidence coverage."
            )
        gaps = self._identify_gaps(previous_output)
        if not gaps:
            return (
                "Refine quality only: tighten evidence quality, remove weak claims, and "
                "improve competitor summaries/URLs."
            )
        return (
            "Improve only missing/weak areas from prior output. Do not repeat unchanged sections. "
            f"Priority gaps: {', '.join(gaps)}."
        )

    def _identify_gaps(self, output: dict) -> list[str]:
        gaps: list[str] = []
        if not output.get("competitors"):
            gaps.append("competitors")
        if not output.get("evidence_snippets"):
            gaps.append("evidence_snippets")
        if not output.get("risks"):
            gaps.append("risks")
        if not output.get("go_to_market_hypotheses"):
            gaps.append("go_to_market_hypotheses")
        confidence = output.get("confidence")
        if not isinstance(confidence, (int, float)):
            gaps.append("confidence")
        return gaps

    def _apply_quality_gates(
        self,
        output: dict,
        previous_output: dict,
        pass_number: int,
    ) -> tuple[dict, list[str]]:
        issues: list[str] = []
        if not isinstance(output, dict):
            return {}, ["non-dict output"]

        cleaned: dict = {}
        cleaned["competitors"] = self._clean_competitors(output.get("competitors"), issues)
        cleaned["app_landscape"] = output.get("app_landscape") if isinstance(output.get("app_landscape"), dict) else {}
        cleaned["monetization_strategies"] = self._clean_string_list(output.get("monetization_strategies"))
        cleaned["tech_stack"] = self._clean_string_list(output.get("tech_stack"))

        feasibility = str(output.get("feasibility", "unknown")).lower().strip()
        cleaned["feasibility"] = feasibility if feasibility in {"high", "medium", "low"} else "unknown"
        if cleaned["feasibility"] == "unknown":
            issues.append("invalid feasibility")

        confidence = output.get("confidence")
        if isinstance(confidence, (int, float)) and 0 <= float(confidence) <= 1:
            cleaned["confidence"] = float(confidence)
        else:
            cleaned["confidence"] = None
            issues.append("invalid confidence")

        cleaned["evidence_snippets"] = self._clean_string_list(output.get("evidence_snippets"))
        cleaned["risks"] = self._clean_string_list(output.get("risks"))
        cleaned["go_to_market_hypotheses"] = self._clean_string_list(output.get("go_to_market_hypotheses"))
        notes = output.get("additional_notes")
        cleaned["additional_notes"] = notes if isinstance(notes, str) else None

        if pass_number > 1 and previous_output and self._low_novelty(cleaned, previous_output):
            issues.append("low novelty vs prior pass")
            return {}, issues

        if not cleaned["competitors"]:
            issues.append("missing valid competitors")
        if len(cleaned["evidence_snippets"]) < 2:
            issues.append("insufficient evidence snippets")
        return cleaned, issues

    def _merge_outputs(self, previous: dict, current: dict) -> dict:
        merged = dict(previous)
        for key, value in current.items():
            if value in (None, "", [], {}):
                continue
            merged[key] = value
        return merged

    def _clean_competitors(self, competitors_raw: object, issues: list[str]) -> list[dict]:
        cleaned: list[dict] = []
        for comp in competitors_raw if isinstance(competitors_raw, list) else []:
            if isinstance(comp, dict):
                name = str(comp.get("name", "")).strip()
                summary = self._one_sentence(str(comp.get("summary", "")).strip())
                url = self._clean_url(comp.get("url"))
            else:
                name = str(comp).strip()
                summary = "A competitor in this problem space."
                url = None
            if not name:
                issues.append("competitor missing name")
                continue
            if not summary:
                summary = "A competitor in this problem space."
                issues.append(f"competitor missing summary: {name}")
            cleaned.append({"name": name, "summary": summary, "url": url})
        return cleaned

    def _clean_string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            cleaned.append(text)
        return cleaned

    def _clean_url(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if not re.match(r"^https?://", text):
            return None
        return text

    def _one_sentence(self, text: str) -> str:
        if not text:
            return ""
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        sentence = parts[0].strip()
        if sentence and sentence[-1] not in ".!?":
            sentence += "."
        return sentence

    def _low_novelty(self, current: dict, previous: dict) -> bool:
        prev_tokens = set(
            self._clean_string_list(previous.get("evidence_snippets"))
            + self._clean_string_list(previous.get("risks"))
            + [c.get("name", "") for c in previous.get("competitors", []) if isinstance(c, dict)]
        )
        curr_tokens = set(
            self._clean_string_list(current.get("evidence_snippets"))
            + self._clean_string_list(current.get("risks"))
            + [c.get("name", "") for c in current.get("competitors", []) if isinstance(c, dict)]
        )
        if not curr_tokens or not prev_tokens:
            return False
        overlap = len(prev_tokens & curr_tokens) / max(1, len(prev_tokens | curr_tokens))
        return overlap > 0.9
