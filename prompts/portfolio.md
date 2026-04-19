# Portfolio Agent Prompt

This stage is deterministic, not LLM-driven.

## Goal

- Summarize recurring crossed-out feedback into short next-run guidance.

## Inputs

- Feedback events with `reason_code` and optional `reason_text`
- The current crossed-out state of ideas

## Principles

- Learn only from recurring patterns, not one-off or emotional comments.
- Produce concise guidance for scout, synthesizer, and analyser.
- Focus on monetization, urgency, distribution, complexity, and platform risk.
- Do not quote raw feedback directly into downstream prompts.
