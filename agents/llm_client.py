from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import Any, Optional

logger = logging.getLogger(__name__)


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


class OpenCodeLLMClient:
    def __init__(
        self,
        server_url: Optional[str] = None,
        system_prompt: Optional[str] = None,
        cwd: Optional[str] = None,
    ):
        self.server_url = server_url
        self.system_prompt = system_prompt
        self.cwd = cwd
        self._client = None
        self._connected = False
        self._lock = asyncio.Lock()

    def _init_client(self) -> None:
        if self._client is not None:
            return

        try:
            from opencode_agent_sdk import SDKClient, AgentOptions

            # Use clean temp directory to avoid AGENTS.md injection
            if self.cwd is None:
                self.cwd = tempfile.mkdtemp(prefix="opencode_clean_")

            # Empty server_url = subprocess mode, URL = HTTP mode
            self._client = SDKClient(options=AgentOptions(
                server_url=self.server_url or "",
                system_prompt=self.system_prompt or "You are a helpful assistant",
                cwd=self.cwd,
            ))
        except ImportError as e:
            raise LLMError(
                f"opencode-agent-sdk not available: {e}. "
                f"Install with: pip install opencode-agent-sdk"
            )

    async def _ensure_connected(self) -> None:
        async with self._lock:
            if not self._connected:
                self._init_client()
                if self._client is None:
                    raise LLMError("Failed to initialize SDK client")
                await self._client.connect()
                self._connected = True

    async def _get_response_text(self, timeout: float = 60.0) -> str:
        await self._ensure_connected()

        if self._client is None:
            raise LLMError("SDK client not initialized")

        text_parts = []
        start_time = asyncio.get_event_loop().time()
        assistant_message_count = 0

        try:
            from opencode_agent_sdk import AssistantMessage, TextBlock
        except ImportError:
            raise LLMError("opencode-agent-sdk not available")

        async for message in self._client.receive_response():
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                raise LLMError(f"LLM response timeout after {timeout}s")

            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)

            if hasattr(message, '__class__') and message.__class__.__name__ == 'ResultMessage':
                break

        if not text_parts:
            raise LLMError("No text response received from LLM")

        return "".join(text_parts)

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: Optional[str] = None,
        max_retries: int = 2,
        timeout: float = 60.0,
    ) -> str:
        await self._ensure_connected()

        client = self._client
        if client is None:
            raise LLMError("SDK client not initialized")

        # Prepend system prompt to user prompt since SDK doesn't support dynamic system prompts
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                # Wrap query with timeout to prevent indefinite hang
                await asyncio.wait_for(client.query(full_prompt), timeout=timeout)
                return await self._get_response_text(timeout=timeout)

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    await asyncio.sleep(1 * (attempt + 1))
                    try:
                        await client.disconnect()
                    except Exception as e:
                        logger.warning(f"Error disconnecting during retry: {e}")
                    self._connected = False
                    await self._ensure_connected()
                    client = self._client
                    if client is None:
                        raise LLMError("SDK client not initialized after reconnect")
                continue

        raise LLMError(f"LLM call failed after {max_retries + 1} attempts: {last_error}")

    async def complete_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.1,
        model: Optional[str] = None,
        max_retries: int = 3,
    ) -> Any:
        # Strong JSON enforcement - prepend to ensure JSON output
        json_prefix = "You must respond with ONLY valid JSON. No markdown, no explanations, no conversational text.\n\n"
        
        json_system = (system or "") + "\n\nCRITICAL: Respond with ONLY valid JSON. No conversational text, no explanations, no markdown. Just raw JSON."
        
        full_prompt = json_prefix + prompt
        if "json" not in prompt.lower():
            full_prompt = full_prompt + "\n\nRespond with valid JSON only. No other text."

        last_error = None
        last_response = ""
        
        for attempt in range(max_retries):
            response = await self.complete(
                full_prompt, json_system, max_tokens, temperature, model, 0
            )
            last_response = response

            _log_llm_structured("llm_response_received", prompt=prompt, response=response, attempt=attempt + 1, max_retries=max_retries)

            try:
                return json.loads(response)
            except json.JSONDecodeError:
                import re

                json_match = re.search(
                    r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```',
                    response,
                    re.DOTALL
                )
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        pass

                json_match = re.search(r'(\{.*\}|\[.*\])', response, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        pass

                last_error = f"Response: {repr(response[:200])}"
                _log_llm_structured("llm_json_parse_failed", prompt=prompt, response=response, attempt=attempt + 1, max_retries=max_retries)
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))

        raise LLMError(
            f"Could not parse JSON after {max_retries} attempts. Last response: {last_response[:300]}"
        )

    async def disconnect(self) -> None:
        if self._connected and self._client:
            try:
                await self._client.disconnect()
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
            self._connected = False

    async def __aenter__(self):
        await self._ensure_connected()
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


def llm_complete(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    model: Optional[str] = None,
) -> str:
    client = asyncio.run(get_llm_client())
    return asyncio.run(client.complete(prompt, system, max_tokens, temperature, model))


def llm_complete_json(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    model: Optional[str] = None,
) -> Any:
    client = asyncio.run(get_llm_client())
    return asyncio.run(client.complete_json(prompt, system, max_tokens, temperature, model))


async def async_llm_complete_json(
    prompt: str,
    system: Optional[str] = None,
    max_tokens: int = 2000,
    temperature: float = 0.7,
    model: Optional[str] = None,
) -> Any:
    client = await get_llm_client()
    return await client.complete_json(prompt, system, max_tokens, temperature, model)
