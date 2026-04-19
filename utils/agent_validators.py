"""Strict JSON shape validators for agent outputs."""

from __future__ import annotations

from typing import Any


def _require_dict(value: Any, label: str) -> tuple[bool, str]:
    if not isinstance(value, dict):
        return False, f"{label} must be an object"
    return True, ""


def _require_string_list(value: Any, label: str) -> tuple[bool, str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return False, f"{label} must be an array of strings"
    return True, ""


def validate_scout_output(output: Any) -> tuple[bool, str]:
    allowed_keys = {
        "signal_type",
        "content",
        "source_context",
        "payment_context",
        "current_spend_or_workaround",
        "urgency",
    }
    valid_signal_types = {"problem_statement", "complaint", "unmet_need", "repeated_pattern"}
    valid_urgency = {"low", "medium", "high"}

    if not isinstance(output, list):
        return False, "scout output must be an array"

    for index, item in enumerate(output):
        ok, reason = _require_dict(item, f"scout[{index}]")
        if not ok:
            return False, reason
        unknown_keys = set(item) - allowed_keys
        if unknown_keys:
            return False, f"scout[{index}] has unknown keys: {sorted(unknown_keys)}"
        if item.get("signal_type") not in valid_signal_types:
            return False, f"scout[{index}].signal_type is invalid"
        content = item.get("content")
        source_context = item.get("source_context")
        if not isinstance(content, str) or not content.strip():
            return False, f"scout[{index}].content must be a non-empty string"
        if len(content) > 200:
            return False, f"scout[{index}].content exceeds 200 chars"
        if not isinstance(source_context, str) or not source_context.strip():
            return False, f"scout[{index}].source_context must be a non-empty string"
        if "urgency" in item and item["urgency"] not in valid_urgency:
            return False, f"scout[{index}].urgency is invalid"
    return True, ""


def validate_synthesizer_output(output: Any, signal_count: int) -> tuple[bool, str]:
    required_keys = {
        "title",
        "problem",
        "target_user",
        "solution",
        "monetization_hypothesis",
        "payer",
        "pricing_model",
        "wedge",
        "why_now",
        "supporting_signal_indices",
    }
    valid_models = {"subscription", "usage_based", "one_time", "transactional", "sales_led"}

    if not isinstance(output, list):
        return False, "synthesizer output must be an array"

    for index, item in enumerate(output):
        ok, reason = _require_dict(item, f"synthesizer[{index}]")
        if not ok:
            return False, reason
        missing = required_keys - set(item)
        if missing:
            return False, f"synthesizer[{index}] missing keys: {sorted(missing)}"
        for field in required_keys - {"supporting_signal_indices"}:
            if not isinstance(item.get(field), str) or not item[field].strip():
                return False, f"synthesizer[{index}].{field} must be a non-empty string"
        if item["pricing_model"] not in valid_models:
            return False, f"synthesizer[{index}].pricing_model is invalid"
        indices = item["supporting_signal_indices"]
        if not isinstance(indices, list) or not indices:
            return False, f"synthesizer[{index}].supporting_signal_indices must be a non-empty array"
        if not all(isinstance(signal_index, int) for signal_index in indices):
            return False, f"synthesizer[{index}].supporting_signal_indices must contain integers"
        if not all(0 <= signal_index < signal_count for signal_index in indices):
            return False, f"synthesizer[{index}].supporting_signal_indices out of range"
    return True, ""


def validate_analyser_output(output: Any) -> tuple[bool, str]:
    required_keys = {
        "score",
        "monetization_potential",
        "complexity",
        "tags",
        "assumptions",
        "comments",
    }
    valid_levels = {"high", "medium", "low"}

    ok, reason = _require_dict(output, "analyser")
    if not ok:
        return False, reason
    missing = required_keys - set(output)
    if missing:
        return False, f"analyser missing keys: {sorted(missing)}"
    if not isinstance(output["score"], int) or not 0 <= output["score"] <= 100:
        return False, "analyser.score must be an integer from 0 to 100"
    if output["monetization_potential"] not in valid_levels:
        return False, "analyser.monetization_potential is invalid"
    if output["complexity"] not in valid_levels:
        return False, "analyser.complexity is invalid"
    for field in ("tags", "assumptions"):
        ok, reason = _require_string_list(output[field], f"analyser.{field}")
        if not ok:
            return False, reason
    if not isinstance(output["comments"], str):
        return False, "analyser.comments must be a string"
    if "subscores" in output:
        subscores = output["subscores"]
        ok, reason = _require_dict(subscores, "analyser.subscores")
        if not ok:
            return False, reason
        allowed_subscores = {"demand", "gtm", "build_risk", "retention", "monetization", "validation"}
        unknown = set(subscores) - allowed_subscores
        if unknown:
            return False, f"analyser.subscores has unknown keys: {sorted(unknown)}"
        for key, value in subscores.items():
            if not isinstance(value, int) or not 0 <= value <= 100:
                return False, f"analyser.subscores.{key} must be an integer from 0 to 100"
    return True, ""


def validate_critic_output(output: Any) -> tuple[bool, str]:
    required_keys = {
        "saturation_issues",
        "distribution_blockers",
        "technical_blockers",
        "monetization_blockers",
        "validation_blockers",
        "additional_concerns",
    }
    ok, reason = _require_dict(output, "critic")
    if not ok:
        return False, reason
    missing = required_keys - set(output)
    if missing:
        return False, f"critic missing keys: {sorted(missing)}"
    for field in required_keys - {"additional_concerns"}:
        ok, reason = _require_string_list(output[field], f"critic.{field}")
        if not ok:
            return False, reason
    if not isinstance(output["additional_concerns"], str):
        return False, "critic.additional_concerns must be a string"
    return True, ""


def validate_deep_dive_output(output: Any) -> tuple[bool, str]:
    required_keys = {
        "competitors",
        "app_landscape",
        "pricing_landscape",
        "monetization_strategies",
        "paid_alternatives",
        "tech_stack",
        "feasibility",
        "confidence",
        "evidence_snippets",
        "risks",
        "go_to_market_hypotheses",
        "validation_tests",
        "switching_cost_notes",
        "additional_notes",
    }
    valid_feasibility = {"high", "medium", "low"}

    ok, reason = _require_dict(output, "deep_dive")
    if not ok:
        return False, reason
    missing = required_keys - set(output)
    if missing:
        return False, f"deep_dive missing keys: {sorted(missing)}"
    if not isinstance(output["competitors"], list):
        return False, "deep_dive.competitors must be an array"
    for index, item in enumerate(output["competitors"]):
        ok, reason = _require_dict(item, f"deep_dive.competitors[{index}]")
        if not ok:
            return False, reason
        for key in ("name", "summary", "url"):
            if key not in item:
                return False, f"deep_dive.competitors[{index}] missing {key}"
        if not isinstance(item["name"], str) or not item["name"].strip():
            return False, f"deep_dive.competitors[{index}].name must be a non-empty string"
        if not isinstance(item["summary"], str) or not item["summary"].strip():
            return False, f"deep_dive.competitors[{index}].summary must be a non-empty string"
        if item["url"] is not None and not isinstance(item["url"], str):
            return False, f"deep_dive.competitors[{index}].url must be a string or null"
    for field in ("app_landscape", "pricing_landscape"):
        ok, reason = _require_dict(output[field], f"deep_dive.{field}")
        if not ok:
            return False, reason
    for field in (
        "monetization_strategies",
        "paid_alternatives",
        "tech_stack",
        "evidence_snippets",
        "risks",
        "go_to_market_hypotheses",
        "validation_tests",
    ):
        ok, reason = _require_string_list(output[field], f"deep_dive.{field}")
        if not ok:
            return False, reason
    if output["feasibility"] not in valid_feasibility:
        return False, "deep_dive.feasibility is invalid"
    if not isinstance(output["confidence"], (int, float)) or not 0 <= float(output["confidence"]) <= 1:
        return False, "deep_dive.confidence must be a number from 0 to 1"
    if output["switching_cost_notes"] is not None and not isinstance(output["switching_cost_notes"], str):
        return False, "deep_dive.switching_cost_notes must be a string or null"
    if output["additional_notes"] is not None and not isinstance(output["additional_notes"], str):
        return False, "deep_dive.additional_notes must be a string or null"
    return True, ""


def validate_librarian_output(output: Any, pair_count: int) -> tuple[bool, str]:
    valid_actions = {"merge", "keep_separate", "drop"}

    if not isinstance(output, list):
        return False, "librarian output must be an array"
    if len(output) != pair_count:
        return False, f"librarian output length must match pair_count={pair_count}"

    seen_indices: set[int] = set()
    for index, item in enumerate(output):
        ok, reason = _require_dict(item, f"librarian[{index}]")
        if not ok:
            return False, reason
        pair_index = item.get("pair_index")
        action = item.get("action")
        confidence = item.get("confidence")
        if not isinstance(pair_index, int) or pair_index < 0:
            return False, f"librarian[{index}].pair_index is invalid"
        if pair_index in seen_indices:
            return False, f"librarian[{index}].pair_index is duplicated"
        seen_indices.add(pair_index)
        if action not in valid_actions:
            return False, f"librarian[{index}].action is invalid"
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            return False, f"librarian[{index}].confidence must be between 0 and 1"
        if action in {"merge", "keep_separate", "drop"} and "keep_idea_id" not in item:
            return False, f"librarian[{index}].keep_idea_id is required"
        if action == "drop" and "drop_idea_id" not in item:
            return False, f"librarian[{index}].drop_idea_id is required"
    return True, ""
