"""Tagger agent - extracts tags from evaluated ideas using LLM."""
from __future__ import annotations

import asyncio
from typing import Any, cast

from .config import TaggerInput, TaggerOutput
from .llm_client import async_llm_complete_json
from .logger import get_logger


# Default tag categories with descriptions
DEFAULT_TAG_CATEGORIES = {
    "industry": [
        "Healthcare",
        "Finance",
        "E-commerce",
        "Education",
        "Productivity",
        "Entertainment",
        "Marketing",
        "HR/Recruiting",
        "Legal",
        "Real Estate",
        "Travel",
        "Food/Restaurant",
        "Energy",
        "Transportation",
        "Other",
    ],
    "technology": [
        "LLM",
        "Computer Vision",
        "Automation",
        "Data Analytics",
        "NLP",
        "Recommendation",
        "Generative AI",
        "Voice/Audio",
        "Robotics",
        "IoT",
        "Blockchain",
        "AR/VR",
        "Other",
    ],
    "business_model": [
        "SaaS",
        "Marketplace",
        "API/Developer Tool",
        "Consumer App",
        "Enterprise",
        "Freemium",
        "Subscription",
        "Usage-based",
        "Consulting",
        "Other",
    ],
    "founder_fit": [
        "Solo-founder friendly",
        "Requires team",
        "Technical founder needed",
        "Domain expert needed",
        "Capital intensive",
        "Bootstrappable",
        "Other",
    ],
}


class TaggerAgent:
    """Extracts tags from evaluated ideas using LLM batch processing."""

    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size
        self.logger = get_logger()

    async def execute(self, input_data: TaggerInput) -> TaggerOutput:
        """Tag ideas with categories using batch LLM processing."""
        if not input_data.ideas:
            self.logger.info("Tagger received empty input, returning empty output")
            return TaggerOutput(tagged_ideas=[], tag_counts={})

        self.logger.info(f"Tagger starting: {len(input_data.ideas)} ideas to tag")

        # Use provided categories or defaults
        categories = input_data.categories if input_data.categories else list(DEFAULT_TAG_CATEGORIES.keys())

        # Process in batches
        all_tagged_ideas: list[dict[str, Any]] = []
        tag_counts: dict[str, int] = {}

        batches = self._chunk_ideas(input_data.ideas, self.batch_size)
        
        all_thinking_parts: list[str] = []
        
        for batch_idx, batch in enumerate(batches):
            self.logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} ideas)")
            
            batch_result, batch_thinking = await self._tag_batch(batch, categories)
            if batch_thinking:
                all_thinking_parts.append(batch_thinking)
            
            for tagged_idea in batch_result:
                all_tagged_ideas.append(tagged_idea)
                
                # Update tag counts
                for tag in tagged_idea.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        self.logger.info(f"Tagger complete: {len(all_tagged_ideas)} ideas tagged, {len(tag_counts)} unique tags")

        combined_thinking = " ".join(all_thinking_parts)

        return TaggerOutput(
            thinking=combined_thinking,
            tagged_ideas=all_tagged_ideas,
            tag_counts=tag_counts,
        )

    def _chunk_ideas(self, ideas: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
        """Split ideas into batches of given size."""
        return [ideas[i:i + size] for i in range(0, len(ideas), size)]

    async def _tag_batch(
        self,
        ideas: list[dict[str, Any]],
        categories: list[str],
    ) -> tuple[list[dict[str, Any]], str]:
        """Tag a batch of ideas using LLM."""

        # Build category descriptions for prompt
        category_descriptions = self._build_category_descriptions(categories)

        # Build ideas list for prompt
        ideas_text = self._build_ideas_prompt(ideas)

        prompt = f"""You are an expert at categorizing AI startup ideas.

TAG CATEGORIES:
{category_descriptions}

IDEAS TO TAG:
{ideas_text}

Think out loud about what categories these ideas belong to. Consider the industry, technology stack, business model, and founder fit for each idea before assigning tags.

Output as JSON with thinking first, then tagged_ideas:
{{
  "thinking": "Your chain-of-thought reasoning about appropriate tags for all ideas, considering categories and fit",
  "tagged_ideas": [
    {{
      "idea_title": "<exact title from input>",
      "thinking": "Your reasoning about which tags fit this specific idea",
      "tags": ["Tag1", "Tag2", ...],
      "tag_categories": {{
        "Tag1": "category_name",
        "Tag2": "category_name",
        ...
      }}
    }}
  ]
}}

Rules:
1. Use EXACT tag names from the categories above (case-sensitive)
2. Each idea should have 2-5 tags total
3. Every tag must map to exactly one category in tag_categories
4. Use "Other" category sparingly, only when no other category fits
5. Preserve the exact idea_title from input

Only output valid JSON, no markdown."""

        response = await async_llm_complete_json(
            prompt=prompt,
            max_tokens=4000,
            temperature=0.3,
        )

        if not isinstance(response, dict):
            self.logger.warning(f"LLM returned non-dict response: {type(response).__name__}")
            return [], ""

        thinking = response.get("thinking", "")
        batch_thinking = thinking
        tagged_ideas = response.get("tagged_ideas", [])
        
        if not isinstance(tagged_ideas, list):
            self.logger.warning(f"LLM returned non-list tagged_ideas: {type(tagged_ideas).__name__}")
            return [], ""

        # Validate and clean response
        validated = []
        for item in tagged_ideas:
            if not isinstance(item, dict):
                continue
            
            idea_title = item.get("idea_title", "")
            item_thinking = item.get("thinking", "")
            tags = item.get("tags", [])
            tag_categories = item.get("tag_categories", {})

            # Validate tags match categories
            cleaned_tags = []
            cleaned_categories = {}
            for tag in tags:
                if tag in tag_categories:
                    cat = tag_categories[tag]
                    if cat in DEFAULT_TAG_CATEGORIES or cat in categories:
                        cleaned_tags.append(tag)
                        cleaned_categories[tag] = cat

            validated.append({
                "idea_title": idea_title,
                "thinking": item_thinking,
                "tags": cleaned_tags,
                "tag_categories": cleaned_categories,
            })

        return validated, batch_thinking

    def _build_category_descriptions(self, categories: list[str]) -> str:
        """Build category descriptions for the LLM prompt."""
        lines = []
        
        for category in categories:
            if category in DEFAULT_TAG_CATEGORIES:
                tags = DEFAULT_TAG_CATEGORIES[category]
                lines.append(f"\n{category.upper()}:")
                lines.append(f"  Options: {', '.join(tags)}")
            else:
                lines.append(f"\n{category.upper()}:")
                lines.append("  (Custom category - infer appropriate tags)")

        return "\n".join(lines)

    def _build_ideas_prompt(self, ideas: list[dict[str, Any]]) -> str:
        """Build ideas list for the LLM prompt."""
        lines = []
        
        for idx, idea in enumerate(ideas, 1):
            title = idea.get("idea_title", "Untitled")
            summary = idea.get("idea_summary", "")
            score = idea.get("score", 0)
            
            lines.append(f"\n{idx}. Title: {title}")
            if summary:
                # Truncate long summaries
                summary_preview = summary[:200] + "..." if len(summary) > 200 else summary
                lines.append(f"   Summary: {summary_preview}")
            lines.append(f"   Score: {score}")

        return "\n".join(lines)