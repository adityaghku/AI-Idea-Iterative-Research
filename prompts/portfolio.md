# Portfolio Agent Prompt

This stage is currently a deterministic portfolio summarizer, not an LLM prompt.

Its job is to read explicit crossed-out feedback reasons and produce compact guidance for the next run.

## Inputs

- Crossed-out feedback events with `reason_code` and optional `reason_text`
- Current crossed-out state on ideas

## Output Goals

- Identify only recurring rejection patterns worth learning from
- Ignore one-off, emotional, or overly specific comments
- Produce short guidance that helps:
  - scout avoid weak problem areas
  - synthesizer avoid weak business theses
  - analyser calibrate skepticism

## Output Principles

- Prefer stable patterns over anecdotes
- Do not quote raw user feedback directly into prompts
- Focus on monetization, urgency, distribution, complexity, and platform risk
- Keep guidance concise enough to inject into prompts
