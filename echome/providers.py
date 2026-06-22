"""Pluggable LLM provider — one chat() that routes by PROVIDER (Phase 1, Step 5).

The rest of the app never imports an SDK directly; it calls chat(system, messages)
and this module dispatches to OpenAI, Claude, or a local Ollama server based on
config. Keys and model names come from .env (bring-your-own-key). Switching
providers is a one-line .env change, no code change.

`messages` is the OpenAI-style turn list: [{"role": "user"|"assistant", "content": str}].
`system` is the system prompt as a plain string; each backend wires it in the way
that backend expects.
"""

from __future__ import annotations

from typing import Any

import httpx

from echome.config import Config, load_config


class ProviderError(RuntimeError):
    """Raised when a provider is misconfigured (missing key, bad name, unreachable)."""


def chat(system: str, messages: list[dict[str, str]]) -> str:
    """Send a system prompt + message turns to the configured provider; return text."""
    config = load_config()
    provider = config.provider

    if provider == "openai":
        return _chat_openai(system, messages, config)
    if provider == "claude":
        return _chat_claude(system, messages, config)
    if provider == "ollama":
        return _chat_ollama(system, messages, config)

    raise ProviderError(
        f"Unknown PROVIDER '{provider}'. Set PROVIDER to one of: openai, claude, ollama."
    )


def _require_key(value: str, env_name: str, provider: str) -> str:
    """Validate that an API key is actually set (not blank or a placeholder)."""
    if not value or value.startswith("sk-...") or "your-key-here" in value:
        raise ProviderError(
            f"PROVIDER is '{provider}' but {env_name} is not set. "
            f"Add a real key to your .env (copy from .env.example)."
        )
    return value


def _chat_openai(system: str, messages: list[dict[str, str]], config: Config) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise ProviderError("The 'openai' package is not installed. Run: pip install openai") from exc

    api_key = _require_key(config.openai_api_key, "OPENAI_API_KEY", "openai")
    client = OpenAI(api_key=api_key)

    # OpenAI takes the system prompt as a {"role": "system"} message PREPENDED to the list.
    full_messages: list[dict[str, Any]] = [{"role": "system", "content": system}, *messages]
    try:
        response = client.chat.completions.create(
            model=config.openai_model,
            messages=full_messages,
        )
    except Exception as exc:
        raise ProviderError(f"OpenAI request failed: {exc}") from exc
    return (response.choices[0].message.content or "").strip()


def _chat_claude(system: str, messages: list[dict[str, str]], config: Config) -> str:
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise ProviderError("The 'anthropic' package is not installed. Run: pip install anthropic") from exc

    api_key = _require_key(config.claude_api_key, "CLAUDE_API_KEY", "claude")
    client = anthropic.Anthropic(api_key=api_key)

    # Anthropic takes `system` as a separate parameter, not a message.
    try:
        response = client.messages.create(
            model=config.claude_model,
            system=system,
            messages=messages,
            max_tokens=1024,
        )
    except Exception as exc:
        raise ProviderError(f"Claude request failed: {exc}") from exc
    return "".join(block.text for block in response.content if block.type == "text").strip()


def _chat_ollama(system: str, messages: list[dict[str, str]], config: Config) -> str:
    # Ollama's /api/chat takes the system prompt as a leading system message.
    full_messages = [{"role": "system", "content": system}, *messages]
    url = config.ollama_url.rstrip("/") + "/api/chat"
    try:
        response = httpx.post(
            url,
            json={"model": config.ollama_model, "messages": full_messages, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
    except httpx.ConnectError as exc:
        raise ProviderError(
            f"Could not reach Ollama at {config.ollama_url}. Is it running? (ollama serve)"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise ProviderError(f"Ollama returned an error: {exc.response.text}") from exc
    return response.json()["message"]["content"].strip()
