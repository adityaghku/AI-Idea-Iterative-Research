"""Formatting helpers for passing structured idea context to prompts."""

from __future__ import annotations


def format_business_context(idea) -> str:
    lines: list[str] = []
    fields = [
        ("Monetization Hypothesis", getattr(idea, "monetization_hypothesis", None)),
        ("Payer", getattr(idea, "payer", None)),
        ("Pricing Model", getattr(idea, "pricing_model", None)),
        ("Wedge", getattr(idea, "wedge", None)),
        ("Why Now", getattr(idea, "why_now", None)),
    ]
    for label, value in fields:
        if value not in (None, ""):
            lines.append(f"{label}: {value}")
    return "\n".join(lines)
