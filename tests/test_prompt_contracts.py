from utils.prompts_utils import load_prompt


RUNTIME_PROMPT_FILES = [
    "scout.md",
    "synthesizer.md",
    "analyser.md",
    "critic.md",
    "deep_dive.md",
    "librarian.md",
]


def test_load_prompt_does_not_inject_runtime_contract():
    prompt = load_prompt("scout.md")

    assert "Runtime Hard Rules" not in prompt


def test_runtime_prompt_templates_do_not_contain_fenced_json_examples():
    for filename in RUNTIME_PROMPT_FILES:
        prompt = load_prompt(filename)
        assert "```" not in prompt, filename


def test_scout_prompt_has_no_static_memory_placeholder():
    prompt = load_prompt("scout.md")

    assert "## Memory" not in prompt
    assert "No prior scout memory." not in prompt
