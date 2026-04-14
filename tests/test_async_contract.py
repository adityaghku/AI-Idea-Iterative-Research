from pathlib import Path


def test_llm_client_has_no_asyncio_run_wrappers():
    llm_client = Path(__file__).resolve().parents[1] / "utils" / "llm_client.py"
    source = llm_client.read_text(encoding="utf-8")
    assert "asyncio.run(" not in source
