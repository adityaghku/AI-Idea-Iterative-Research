from __future__ import annotations

import asyncio
import httpx
import json
import logging
import os
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def _opencode_session_create(api: Any) -> Any:
    """Create an OpenCode session.

    ``opencode_ai``'s ``session.create()`` POSTs ``/session`` with no JSON body; the
    OpenCode server rejects that with 400 ``Malformed JSON in request body``. Sending
    ``{}`` matches ``curl``/httpx and satisfies the parser (see SDK custom ``post()``).
    """
    from opencode_ai.types import Session

    return await api.post("/session", cast_to=Session, body={})


def _log_llm_structured(event: str, prompt: str, response: str = "", **kwargs) -> None:
    log_entry = {
        "event": event,
        "prompt_length": len(prompt),
        "response_length": len(response) if response else 0,
        **kwargs,
    }
    logger.info(json.dumps(log_entry))


class LLMError(Exception):
    pass


def _extract_json_value(text: str) -> Any | None:
    """Parse the first JSON object or array in text using JSONDecoder.raw_decode."""
    decoder = json.JSONDecoder()
    s = text.strip()
    for i, ch in enumerate(s):
        if ch not in "{[":
            continue
        try:
            obj, _ = decoder.raw_decode(s, i)
            return obj
        except json.JSONDecodeError:
            continue
    return None


FREE_OPENCODE_MODELS = ["deepseek/deepseek-chat"]

_model_rotation_index = 0
_rotation_lock = None


def _get_next_model() -> str:
    """Get the next model in rotation for free tier load balancing."""
    global _model_rotation_index, _rotation_lock

    if _rotation_lock is None:
        import threading

        _rotation_lock = threading.Lock()

    with _rotation_lock:
        model = FREE_OPENCODE_MODELS[_model_rotation_index]
        _model_rotation_index = (_model_rotation_index + 1) % len(FREE_OPENCODE_MODELS)
        return model


def _resolve_provider_model(model: Optional[str]) -> tuple[str, str]:
    """Resolve provider_id and model_id for session.chat (SessionChatParams)."""
    explicit = (model or "").strip()
    env_combined = os.environ.get("OPENCODE_MODEL", "").strip()
    chosen = explicit or env_combined

    if chosen:
        if "/" in chosen:
            prov, mid = chosen.split("/", 1)
            return prov.strip(), mid.strip()
        prov = os.environ.get("OPENCODE_PROVIDER_ID", "opencode").strip()
        return prov, chosen

    prov = os.environ.get("OPENCODE_PROVIDER_ID", "").strip() or "opencode"
    mid = os.environ.get("OPENCODE_MODEL_ID", "").strip() or _get_next_model()

    # Check if mid contains provider/model separator
    if "/" in mid:
        prov_from_mid, mid_from_mid = mid.split("/", 1)
        return prov_from_mid.strip(), mid_from_mid.strip()

    return prov, mid


def _auth_headers() -> Optional[dict[str, str]]:
    key = os.environ.get("OPENCODE_API_KEY", "").strip()
    if not key:
        return None
    return {"Authorization": f"Bearer {key}"}


def _concat_text_parts(parts: object) -> str:
    chunks: list[str] = []
    for p in parts:
        t = getattr(p, "type", None)
        if t == "text":
            chunks.append(getattr(p, "text", "") or "")
    return "".join(chunks)


def _assistant_text_from_messages(messages: object, assistant_message_id: str) -> str:
    for item in messages:
        info = item.info
        if getattr(info, "id", None) == assistant_message_id:
            return _concat_text_parts(item.parts)
    for item in reversed(list(messages)):
        info = item.info
        if getattr(info, "role", None) == "assistant":
            return _concat_text_parts(item.parts)
    raise LLMError("No assistant text in session messages")


class OpenCodeLLMClient:
    """LLM access via opencode-ai HTTP client (OpenCode server REST API)."""

    def __init__(
        self,
        server_url: Optional[str] = None,
        system_prompt: Optional[str] = None,
        cwd: Optional[str] = None,
    ):
        self.server_url = server_url
        self.system_prompt = system_prompt
        # cwd kept for API compatibility; REST client does not use a local workspace.
        self.cwd = cwd
        self._api = None
        self._lock = asyncio.Lock()

    def _base_url(self) -> str:
        return self.server_url or os.environ.get(
            "OPENCODE_BASE_URL", "http://localhost:4096"
        )

    def _make_async_opencode(self):
        try:
            import httpx
            from opencode_ai import AsyncOpencode
        except ImportError as e:
            raise LLMError(
                f"opencode-ai not available: {e}. Install with: pip install opencode-ai"
            ) from e

        base_url = self.server_url or os.environ.get("OPENCODE_BASE_URL")
        headers = _auth_headers()
        timeout = httpx.Timeout(180.0, connect=30.0)
        kwargs: dict[str, Any] = {
            "max_retries": 2,
            "timeout": timeout,
        }
        if base_url:
            kwargs["base_url"] = base_url
        if headers:
            kwargs["default_headers"] = headers

        return AsyncOpencode(**kwargs)

    async def _ensure_api(self) -> None:
        async with self._lock:
            if self._api is None:
                logger.info("Initializing opencode-ai AsyncOpencode client...")
                self._api = self._make_async_opencode()

    async def _close_api(self) -> None:
        if self._api is not None:
            try:
                await self._api.close()
            except Exception as e:
                logger.warning("Error closing opencode-ai client: %s", e)
            self._api = None

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: Optional[str] = None,
        max_retries: int = 2,
        timeout: float = 180.0,
    ) -> str:
        # max_tokens / temperature: not on session.chat in current opencode-ai; kept for API parity.
        logger.debug(
            "complete kwargs: max_tokens=%s temperature=%s", max_tokens, temperature
        )

        await self._ensure_api()
        if self._api is None:
            raise LLMError("HTTP client not initialized")

        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
        if self.system_prompt and not system:
            full_prompt = f"{self.system_prompt}\n\n{full_prompt}"

        provider_id, model_id = _resolve_provider_model(model)

        from opencode_ai.types.text_part_input_param import TextPartInputParam

        parts: list[TextPartInputParam] = [{"type": "text", "text": full_prompt}]

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            provider_id, model_id = _resolve_provider_model(model)
            api = self._api
            if api is None:
                raise LLMError("HTTP client not initialized")
            try:
                logger.info(
                    "OpenCode chat (attempt %s, timeout=%ss, provider=%s, model=%s)...",
                    attempt + 1,
                    timeout,
                    provider_id,
                    model_id,
                )

                # Create session
                async with httpx.AsyncClient(timeout=timeout) as http_client:
                    base_url = self._base_url()

                    # Create session
                    resp = await http_client.post(f"{base_url}/session", json={})
                    resp.raise_for_status()
                    sid = resp.json()["id"]

                    # Send message
                    await http_client.post(
                        f"{base_url}/session/{sid}/message",
                        json={
                            "parts": parts,
                            "model": {"providerID": provider_id, "modelID": model_id},
                        },
                    )

                    # Poll for response
                    text = ""
                    for _ in range(int(timeout / 2)):
                        await asyncio.sleep(2)
                        resp = await http_client.get(
                            f"{base_url}/session/{sid}/message"
                        )
                        resp.raise_for_status()
                        msgs = resp.json()
                        logger.debug("Poll response: %s", msgs)
                        for m in msgs:
                            msg_info = m.get("info", {})
                            if msg_info.get("role") == "assistant":
                                finish_reason = msg_info.get("finish", "")
                                for p in m.get("parts", []):
                                    if p.get("type") == "text":
                                        text += p.get("text", "")
                                if finish_reason == "stop" and text.strip():
                                    break
                                if finish_reason == "tool-calls":
                                    text = ""
                        if text.strip():
                            break

                try:
                    await api.session.delete(sid)
                except Exception as e:
                    logger.debug("session.delete failed (non-fatal): %s", e)

                if not text.strip():
                    raise LLMError("Empty assistant text from OpenCode server")

                return text

            except Exception as e:
                if isinstance(e, LLMError):
                    last_error = e
                else:
                    last_error = LLMError(f"{type(e).__name__}: {e}")
                logger.warning(
                    "LLM chat failed (attempt %s): %s", attempt + 1, last_error
                )
                if attempt < max_retries:
                    delay = 2**attempt
                    logger.info("Waiting %d seconds before retry...", delay)
                    await asyncio.sleep(delay)
                    async with self._lock:
                        await self._close_api()
                        self._api = self._make_async_opencode()
                continue

        raise LLMError(
            f"LLM call failed after {max_retries + 1} attempts: {last_error}"
        )

    async def complete_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.1,
        model: Optional[str] = None,
        max_retries: int = 3,
        *,
        agent_name: Optional[str] = None,
        pass_number: Optional[int] = None,
    ) -> Any:
        logger.info(
            "=== LLM complete_json START (model=%s, max_tokens=%s, temp=%s) ===",
            model,
            max_tokens,
            temperature,
        )
        logger.info("Prompt length: %s chars", len(prompt))
        logger.info("System: %s...", str(system)[:200] if system else "None")

        json_prefix = (
            "You must respond with ONLY valid JSON. No markdown, no explanations, "
            "no conversational text.\n\n"
        )
        json_system = (system or "") + (
            "\n\nCRITICAL: Respond with ONLY valid JSON. No conversational text, "
            "no explanations, no markdown. Just raw JSON."
        )
        full_prompt = json_prefix + prompt
        logger.info("Full prompt length: %s chars", len(full_prompt))
        if "json" not in prompt.lower():
            full_prompt = (
                full_prompt + "\n\nRespond with valid JSON only. No other text."
            )

        last_response = ""

        for attempt in range(max_retries):
            t0 = time.monotonic()
            try:
                response = await self.complete(
                    full_prompt,
                    json_system,
                    max_tokens,
                    temperature,
                    model,
                    max_retries=2,
                )
            except Exception as e:
                _log_llm_structured(
                    "llm_call_metrics",
                    prompt=prompt,
                    response="",
                    agent_name=agent_name,
                    pass_number=pass_number,
                    attempt=attempt + 1,
                    latency_ms=int((time.monotonic() - t0) * 1000),
                    success=False,
                    error_type=type(e).__name__,
                    error=str(e),
                )
                raise
            last_response = response

            _log_llm_structured(
                "llm_response_received",
                prompt=prompt,
                response=response,
                attempt=attempt + 1,
                max_retries=max_retries,
                agent_name=agent_name,
                pass_number=pass_number,
            )

            logger.debug("LLM raw response: %r", response)

            try:
                result = json.loads(response)
                latency_ms = int((time.monotonic() - t0) * 1000)
                logger.info("=== LLM complete_json SUCCESS ===")
                parsed_len = len(result) if isinstance(result, (list, dict)) else "N/A"
                logger.info(
                    "Parsed JSON type: %s, length: %s",
                    type(result).__name__,
                    parsed_len,
                )
                _log_llm_structured(
                    "llm_call_metrics",
                    prompt=prompt,
                    response=response,
                    agent_name=agent_name,
                    pass_number=pass_number,
                    attempt=attempt + 1,
                    latency_ms=latency_ms,
                    success=True,
                    parse_mode="json.loads",
                    response_type=type(result).__name__,
                )
                return result
            except json.JSONDecodeError:
                logger.warning(
                    "JSON parse failed, trying raw_decode / fenced extraction..."
                )
                extracted = _extract_json_value(response)
                if extracted is not None:
                    latency_ms = int((time.monotonic() - t0) * 1000)
                    logger.info("=== LLM complete_json SUCCESS (raw_decode) ===")
                    _log_llm_structured(
                        "llm_call_metrics",
                        prompt=prompt,
                        response=response,
                        agent_name=agent_name,
                        pass_number=pass_number,
                        attempt=attempt + 1,
                        latency_ms=latency_ms,
                        success=True,
                        parse_mode="raw_decode",
                        response_type=type(extracted).__name__,
                    )
                    return extracted

                json_match = re.search(
                    r"```(?:json)?\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*```",
                    response,
                )
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        extracted = _extract_json_value(json_match.group(1))
                        if extracted is not None:
                            logger.info(
                                "=== LLM complete_json SUCCESS (fence+raw_decode) ==="
                            )
                            return extracted

                json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", response)
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        extracted = _extract_json_value(json_match.group(1))
                        if extracted is not None:
                            logger.info(
                                "=== LLM complete_json SUCCESS (bracket+raw_decode) ==="
                            )
                            return extracted

                _log_llm_structured(
                    "llm_json_parse_failed",
                    prompt=prompt,
                    response=response,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    agent_name=agent_name,
                    pass_number=pass_number,
                    latency_ms=int((time.monotonic() - t0) * 1000),
                )

                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    _log_llm_structured(
                        "llm_call_metrics",
                        prompt=prompt,
                        response=response,
                        agent_name=agent_name,
                        pass_number=pass_number,
                        attempt=attempt + 1,
                        latency_ms=int((time.monotonic() - t0) * 1000),
                        success=False,
                        error_type="JSONDecodeError",
                        error="Could not parse JSON response",
                    )

        raise LLMError(
            f"Could not parse JSON after {max_retries} attempts. "
            f"Last response: {last_response[:300]}"
        )

    async def disconnect(self) -> None:
        async with self._lock:
            await self._close_api()

    async def __aenter__(self):
        await self._ensure_api()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()


_llm_client: Optional[OpenCodeLLMClient] = None
_client_lock = asyncio.Lock()


async def get_llm_client(
    server_url: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> OpenCodeLLMClient:
    global _llm_client
    async with _client_lock:
        if _llm_client is None:
            _llm_client = OpenCodeLLMClient(
                server_url=server_url,
                system_prompt=system_prompt,
            )
        return _llm_client


async def _llm_complete_json_async(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    model: Optional[str] = None,
) -> Any:
    client = await get_llm_client()
    return await client.complete_json(prompt, system, max_tokens, temperature, model)


async def async_llm_complete_json(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    model: Optional[str] = None,
    max_retries: int = 8,
    *,
    agent_name: Optional[str] = None,
    pass_number: Optional[int] = None,
) -> Any:
    client = OpenCodeLLMClient()
    try:
        return await client.complete_json(
            prompt,
            system,
            max_tokens,
            temperature,
            model,
            max_retries,
            agent_name=agent_name,
            pass_number=pass_number,
        )
    finally:
        await client.disconnect()
