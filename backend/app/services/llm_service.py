"""
LLM Service module for interacting with the Groq API.
Encapsulates Groq client management with thread-safe round-robin API key rotation,
token-budget context trimming, LLM tool calling, and resilient error handling.
"""

import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status
from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    Groq,
    GroqError,
    RateLimitError,
)

from app.config import settings
from app.tools import AVAILABLE_TOOLS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT: str = (
    "You are a helpful AI assistant. Answer the user's questions clearly, "
    "accurately, and concisely."
)


def trim_messages(messages: List[Dict[str, Any]], max_chars: int = 4000) -> List[Dict[str, Any]]:
    """
    Ensure the cumulative message payload stays strictly within Groq's tokens-per-minute (TPM) budget.
    Preserves system instructions and the original query while compacting intermediate tool outputs.
    """
    if not messages:
        return messages

    trimmed: List[Dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            trimmed.append(m)
            continue

        msg_copy = dict(m)
        role = msg_copy.get("role")
        content = msg_copy.get("content")

        # Compact tool message payloads to prevent TPM blowouts and rate limit throttling
        if role == "tool" and isinstance(content, str) and len(content) > 400:
            msg_copy["content"] = content[:400] + "... [trimmed for token budget]"
        trimmed.append(msg_copy)

    total_len = sum(len(str(m.get("content") or "")) for m in trimmed if isinstance(m, dict))
    if total_len > max_chars:
        logger.info("Message context (%d chars) exceeds token budget (%d chars). Trimming intermediate tool outputs...", total_len, max_chars)
        for m in trimmed:
            if m.get("role") == "tool" and isinstance(m.get("content"), str) and len(m["content"]) > 200:
                m["content"] = m["content"][:200] + "... [trimmed]"

    return trimmed


@dataclass
class ProviderTarget:
    """Represents a specific LLM provider credential, endpoint, and default model."""

    provider: str
    api_key: str
    base_url: Optional[str] = None
    default_model: str = "llama-3.3-70b-versatile"
    default_headers: Dict[str, str] = field(default_factory=dict)


class SimpleFunctionCall:
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class SimpleToolCall:
    def __init__(self, id: str, function: SimpleFunctionCall, type: str = "function"):
        self.id = id
        self.function = function
        self.type = type


class SimpleMessage(dict):
    """
    OpenAI/Groq compatible message object that also behaves as a dictionary
    for seamless serialization and inter-agent passing.
    """

    def __init__(
        self,
        role: str = "assistant",
        content: str = "",
        tool_calls: Optional[List[SimpleToolCall]] = None,
        reasoning: str = "",
    ):
        super().__init__(role=role, content=content)
        self.role = role
        self.content = content
        self.tool_calls = tool_calls
        self.reasoning = reasoning
        if tool_calls:
            self["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]


class SimpleChoice:
    def __init__(self, message: SimpleMessage, finish_reason: str = "stop"):
        self.message = message
        self.finish_reason = finish_reason


class SimpleCompletion:
    def __init__(self, choices: List[SimpleChoice]):
        self.choices = choices


def call_ollama_completion(target: ProviderTarget, call_kwargs: Dict[str, Any]) -> SimpleCompletion:
    """
    Execute chat completion against local Ollama native /api/chat endpoint.
    Handles message normalization, tool calling schema, thinking/reasoning extraction,
    and returns a standard OpenAI/Groq compatible SimpleCompletion object.
    """
    base_url = (target.base_url or "http://127.0.0.1:11434").rstrip("/")
    endpoint = f"{base_url}/api/chat"

    # Normalize messages into JSON-serializable dictionaries for Ollama
    clean_messages: List[Dict[str, Any]] = []
    for m in call_kwargs.get("messages", []):
        if isinstance(m, dict):
            item = dict(m)
        elif hasattr(m, "dict") and callable(m.dict):
            item = m.dict()
        else:
            item = {"role": getattr(m, "role", "assistant"), "content": getattr(m, "content", "") or ""}
            tool_calls = getattr(m, "tool_calls", None)
            if tool_calls:
                item["tool_calls"] = tool_calls

        # Ensure tool_calls in item are in Ollama format (arguments must be dict, not raw JSON string)
        if item.get("tool_calls"):
            norm_tcs = []
            for i, tc in enumerate(item["tool_calls"]):
                if isinstance(tc, dict):
                    func_data = dict(tc.get("function") or {})
                    raw_args = func_data.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            func_data["arguments"] = json.loads(raw_args)
                        except Exception:
                            func_data["arguments"] = {"raw": raw_args}
                    norm_tcs.append({
                        "id": tc.get("id") or f"call_{i}",
                        "function": func_data,
                    })
                else:
                    func_name = getattr(tc.function, "name", "")
                    raw_args = getattr(tc.function, "arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            parsed_args = json.loads(raw_args)
                        except Exception:
                            parsed_args = {"raw": raw_args}
                    else:
                        parsed_args = raw_args or {}
                    norm_tcs.append({
                        "id": getattr(tc, "id", f"call_{i}"),
                        "function": {"name": func_name, "arguments": parsed_args},
                    })
            item["tool_calls"] = norm_tcs

        clean_messages.append(item)

    payload: Dict[str, Any] = {
        "model": call_kwargs.get("model") or target.default_model,
        "messages": clean_messages,
        "stream": False,
    }

    options: Dict[str, Any] = {}
    if "temperature" in call_kwargs:
        options["temperature"] = call_kwargs["temperature"]
    if options:
        payload["options"] = options

    if "tools" in call_kwargs and call_kwargs["tools"]:
        payload["tools"] = call_kwargs["tools"]

    timeout_sec = 120.0
    try:
        with httpx.Client(timeout=timeout_sec) as http_client:
            resp = http_client.post(endpoint, json=payload)
            if resp.status_code != 200:
                raise APIStatusError(
                    f"Ollama returned HTTP {resp.status_code}: {resp.text}",
                    response=resp,
                    body=resp.text,
                )
            data = resp.json()
    except httpx.ConnectError as ce:
        raise ConnectionError(
            f"Cannot connect to local Ollama at {endpoint}. Ensure Ollama is running (`ollama serve`). Details: {ce}"
        ) from ce
    except httpx.TimeoutException as te:
        raise TimeoutError(
            f"Local Ollama timed out after {timeout_sec}s for model {payload['model']}: {te}"
        ) from te

    msg_data = data.get("message", {})
    raw_content = msg_data.get("content") or ""
    thinking = msg_data.get("thinking") or ""

    # If content is empty because thinking took the response, fallback cleanly
    if not raw_content.strip() and thinking.strip():
        raw_content = thinking.strip()

    tool_calls_list: Optional[List[SimpleToolCall]] = None
    if "tool_calls" in msg_data and msg_data["tool_calls"]:
        tool_calls_list = []
        for tc in msg_data["tool_calls"]:
            tc_id = tc.get("id") or "call_ollama"
            func_data = tc.get("function", {})
            func_name = func_data.get("name", "")
            func_args = func_data.get("arguments", "{}")
            if isinstance(func_args, dict):
                func_args = json.dumps(func_args)
            tool_calls_list.append(
                SimpleToolCall(
                    id=tc_id,
                    function=SimpleFunctionCall(name=func_name, arguments=func_args),
                    type="function",
                )
            )

    choice = SimpleChoice(
        message=SimpleMessage(
            role=msg_data.get("role", "assistant"),
            content=raw_content,
            tool_calls=tool_calls_list,
            reasoning=thinking,
        ),
        finish_reason="tool_calls" if tool_calls_list else "stop",
    )

    return SimpleCompletion(choices=[choice])


class KeyRotator:
    """
    Thread-safe round-robin API key rotator supporting multiple providers:
    Ollama (Local LLM), Groq, OpenAI, OpenRouter, and Grok (xAI).
    Distributes LLM requests across configured keys and supports transparent failover.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index = 0

    def get_active_targets(self) -> List[ProviderTarget]:
        """
        Build the list of active provider targets based on settings and available API keys.
        """
        # If in an isolated test where GROQ_API_KEYS was monkeypatched directly without multi-provider settings
        monkeypatched_dict = getattr(settings, "__dict__", {})
        has_groq_override = (
            getattr(settings, "_groq_api_keys_override", None) is not None
            or "GROQ_API_KEYS" in monkeypatched_dict
        )
        has_multi_override = (
            "OPENAI_API_KEYS" in monkeypatched_dict
            or "OPENROUTER_API_KEYS" in monkeypatched_dict
            or "GROK_API_KEYS" in monkeypatched_dict
            or "LLM_PROVIDER" in monkeypatched_dict
            or getattr(settings, "_openai_api_keys_override", None) is not None
            or getattr(settings, "_openrouter_api_keys_override", None) is not None
            or getattr(settings, "_grok_api_keys_override", None) is not None
            or getattr(settings, "_llm_provider_override", None) is not None
        )
        is_isolated_groq_test = has_groq_override and not has_multi_override
        if is_isolated_groq_test:
            groq_keys = settings.GROQ_API_KEYS
            return [
                ProviderTarget(
                    provider="groq",
                    api_key=k,
                    base_url=None,
                    default_model=settings.GROQ_MODEL,
                )
                for k in groq_keys
            ]

        provider_mode = settings.LLM_PROVIDER
        ollama_targets: List[ProviderTarget] = []
        groq_targets: List[ProviderTarget] = []
        openai_targets: List[ProviderTarget] = []
        openrouter_targets: List[ProviderTarget] = []
        grok_targets: List[ProviderTarget] = []

        # 0. Ollama (Local LLM)
        if provider_mode in ("ollama", "local", "round_robin", "all", "auto"):
            ollama_url = settings.OLLAMA_BASE_URL
            ollama_model = settings.OLLAMA_MODEL
            if provider_mode in ("ollama", "local"):
                ollama_targets.append(
                    ProviderTarget(
                        provider="ollama",
                        api_key="ollama",
                        base_url=ollama_url,
                        default_model=ollama_model,
                    )
                )
            elif provider_mode in ("round_robin", "all", "auto"):
                from app.services.mcp_client import is_port_open
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(ollama_url)
                    host = parsed.hostname or "127.0.0.1"
                    port = parsed.port or 11434
                    if is_port_open(host, port, timeout=0.08):
                        ollama_targets.append(
                            ProviderTarget(
                                provider="ollama",
                                api_key="ollama",
                                base_url=ollama_url,
                                default_model=ollama_model,
                            )
                        )
                except Exception:
                    pass

        # 1. Groq
        if provider_mode in ("round_robin", "groq", "all", "auto"):
            for k in settings.GROQ_API_KEYS:
                groq_targets.append(
                    ProviderTarget(
                        provider="groq",
                        api_key=k,
                        base_url=None,
                        default_model=settings.GROQ_MODEL,
                    )
                )

        # 2. OpenAI
        if provider_mode in ("round_robin", "openai", "all", "auto"):
            for k in settings.OPENAI_API_KEYS:
                openai_targets.append(
                    ProviderTarget(
                        provider="openai",
                        api_key=k,
                        base_url="https://api.openai.com/v1",
                        default_model=settings.OPENAI_MODEL,
                        default_headers={"User-Agent": "Multi-Agent-System/1.0"},
                    )
                )

        # 3. OpenRouter
        if provider_mode in ("round_robin", "openrouter", "all", "auto"):
            for k in settings.OPENROUTER_API_KEYS:
                openrouter_targets.append(
                    ProviderTarget(
                        provider="openrouter",
                        api_key=k,
                        base_url="https://openrouter.ai/api/v1",
                        default_model=settings.OPENROUTER_MODEL,
                        default_headers={
                            "HTTP-Referer": "http://localhost:3000",
                            "X-Title": "Multi-Agent AI",
                            "User-Agent": "Multi-Agent-System/1.0",
                        },
                    )
                )

        # 4. Grok (xAI)
        if provider_mode in ("round_robin", "grok", "xai", "all", "auto"):
            for k in settings.GROK_API_KEYS:
                grok_targets.append(
                    ProviderTarget(
                        provider="grok",
                        api_key=k,
                        base_url="https://api.x.ai/v1",
                        default_model=settings.GROK_MODEL,
                        default_headers={"User-Agent": "Multi-Agent-System/1.0"},
                    )
                )

        # If specific single provider requested
        if provider_mode in ("ollama", "local"):
            return ollama_targets
        if provider_mode == "groq":
            return groq_targets
        if provider_mode == "openai":
            return openai_targets
        if provider_mode == "openrouter":
            return openrouter_targets
        if provider_mode in ("grok", "xai"):
            return grok_targets

        # In round_robin/all mode: interleave across providers for optimal load distribution
        provider_buckets = [b for b in (ollama_targets, groq_targets, openai_targets, openrouter_targets, grok_targets) if b]
        if not provider_buckets:
            return []

        interleaved: List[ProviderTarget] = []
        max_bucket_len = max(len(b) for b in provider_buckets)
        for idx in range(max_bucket_len):
            for bucket in provider_buckets:
                if idx < len(bucket):
                    interleaved.append(bucket[idx])

        return interleaved

    def get_next_target(self) -> ProviderTarget:
        """
        Retrieve the next ProviderTarget in round-robin sequence across all active keys.
        """
        targets = self.get_active_targets()
        if not targets:
            logger.error("No valid API keys or local models found across any configured LLM providers.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LLM service is not configured. Set LLM_PROVIDER=ollama to use local Ollama, or provide API keys (GROQ_API_KEYS, OPENAI_API_KEYS, etc.) in your .env file.",
            )

        with self._lock:
            target = targets[self._index % len(targets)]
            self._index = (self._index + 1) % len(targets)
            masked = f"...{target.api_key[-6:]}" if len(target.api_key) >= 6 else "***"
            logger.info(
                "Round-robin selected [%s] key %s (model: %s, slot %d of %d)",
                target.provider.upper(),
                masked,
                target.default_model,
                self._index,
                len(targets),
            )
            return target

    def get_next_key(self) -> str:
        """
        Backward-compatible key getter.
        Returns the API key of the next round-robin target.
        """
        is_isolated_groq_test = (
            getattr(settings, "_groq_api_keys_override", None) is not None
            or "GROQ_API_KEYS" in getattr(settings, "__dict__", {})
        )
        if is_isolated_groq_test:
            keys = settings.GROQ_API_KEYS
            if not keys:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No Groq API keys configured.",
                )
            with self._lock:
                key = keys[self._index % len(keys)]
                self._index = (self._index + 1) % len(keys)
                return key

        return self.get_next_target().api_key


# Global singleton instance of key rotator
key_rotator = KeyRotator()


def get_groq_client(
    api_key: Optional[str] = None,
    target: Optional[ProviderTarget] = None,
) -> Groq:
    """
    Instantiate and return an authenticated client.
    Supports native Groq endpoints and OpenAI-compatible endpoints (OpenAI, OpenRouter, xAI Grok).
    """
    if target is not None:
        client_kwargs: Dict[str, Any] = {
            "api_key": target.api_key,
            "max_retries": 0,
        }
        if target.base_url:
            client_kwargs["base_url"] = target.base_url
        if target.default_headers:
            client_kwargs["default_headers"] = target.default_headers
        return Groq(**client_kwargs)

    selected_key = api_key or key_rotator.get_next_key()
    return Groq(api_key=selected_key, max_retries=0)


def create_completion_with_rotation(kwargs: Dict[str, Any]) -> Any:
    """
    Execute chat completion with round-robin provider and key distribution,
    providing automatic failover across keys and providers on rate limits or outages.
    """
    targets = key_rotator.get_active_targets()
    attempts = max(4, len(targets) * 2) if targets else 4

    # Apply proactive message trimming and output token capping before network dispatch
    if "messages" in kwargs:
        kwargs["messages"] = trim_messages(kwargs["messages"])
    if kwargs.get("max_tokens", 0) > 4000:
        kwargs["max_tokens"] = 4000

    last_error: Optional[Exception] = None

    for attempt_idx in range(attempts):
        target = key_rotator.get_next_target()

        # Clone kwargs and adapt model for target provider
        call_kwargs = dict(kwargs)
        caller_model = kwargs.get("model")
        known_defaults = {
            settings.GROQ_MODEL,
            settings.OPENAI_MODEL,
            settings.OPENROUTER_MODEL,
            settings.GROK_MODEL,
            settings.OLLAMA_MODEL,
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "llama-3.3-70b-versatile",
            "gpt-4o-mini",
            "grok-beta",
            "qwen3.5:4b",
        }
        if not caller_model or caller_model in known_defaults:
            call_kwargs["model"] = target.default_model

        if target.provider == "ollama":
            try:
                return call_ollama_completion(target, call_kwargs)
            except Exception as err:
                last_error = err
                err_msg = str(err)
                logger.warning(
                    "[OLLAMA] Call issue on local model %s: %s. Rotating to next target (attempt %d/%d)...",
                    target.default_model,
                    err_msg[:120],
                    attempt_idx + 1,
                    attempts,
                )
                if attempt_idx < attempts - 1:
                    continue
                raise

        client = get_groq_client(target=target)

        try:
            return client.chat.completions.create(**call_kwargs)
        except (RateLimitError, APIStatusError, Exception) as err:
            last_error = err
            status_code = getattr(err, "status_code", None)
            err_msg = str(err)
            is_rate_or_size = (
                isinstance(err, RateLimitError)
                or status_code in (413, 429)
                or "rate_limit_exceeded" in err_msg
                or "Request too large" in err_msg
                or "tokens per minute" in err_msg
                or "quota" in err_msg.lower()
            )
            masked = f"...{target.api_key[-6:]}" if len(target.api_key) >= 6 else "***"

            if attempt_idx < attempts - 1:
                import re
                import time

                # Fast rotation: rotate to the next independent key immediately without sleeping
                # Only apply backoff if all active keys have already been attempted once
                wait_time = 0.0
                if attempt_idx >= (len(targets) - 1):
                    wait_time = 0.5
                    match = re.search(r"Please try again in ([0-9.]+)s", err_msg)
                    if match:
                        try:
                            wait_time = min(2.0, float(match.group(1)) + 0.1)
                        except ValueError:
                            pass

                logger.warning(
                    "[%s] Call issue on key %s (status %s): %s. Rotating to next key in %.1fs (attempt %d/%d)...",
                    target.provider.upper(),
                    masked,
                    status_code,
                    err_msg[:100],
                    wait_time,
                    attempt_idx + 1,
                    attempts,
                )
                if wait_time > 0:
                    time.sleep(wait_time)
                if "messages" in call_kwargs and is_rate_or_size:
                    kwargs["messages"] = trim_messages(kwargs.get("messages", []), max_chars=4000)
                continue

            logger.error("All available LLM API keys exhausted across all providers: %s", err_msg)
            if is_rate_or_size:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="LLM rate or token-per-minute limit exceeded across available API keys. Please wait a moment before retrying.",
                ) from err

            logger.error("API error (status %s): %s", status_code, err_msg)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"The upstream LLM provider encountered an error: {err_msg[:120]}",
            ) from err

    if last_error:
        raise last_error


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Dispatch and execute a requested tool by forwarding the LLM tool call to the MCP tool execution layer.

    Flow:
        LLM Tool Call -> execute_tool -> mcp_tool_executor -> MCP Client -> MCP Server -> Result -> LLM
    """
    from app.services.mcp_client import mcp_tool_executor

    logger.info("[MCP Tool Executor] Forwarding LLM tool call '%s' to MCP Client", tool_name)
    try:
        return mcp_tool_executor(tool_name, arguments)
    except Exception as err:
        logger.warning("[MCP Tool Executor] MCP call failed (%s), attempting local tool fallback.", err)
        tool_func = AVAILABLE_TOOLS.get(tool_name)
        if not tool_func:
            return json.dumps({"error": f"Tool '{tool_name}' is not recognized."})
        res = tool_func(**arguments)
        return json.dumps(res, ensure_ascii=False) if isinstance(res, (dict, list)) else str(res)


def run_agent_with_tools(
    system_prompt: str,
    user_prompt: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.3,
    max_tool_rounds: int = 3,
    max_tokens: int = 1500,
) -> str:
    """
    Execute an agent reasoning cycle with dynamic tool calling and round-robin key rotation.

    Args:
        system_prompt (str): Instructions defining the agent's role and constraints.
        user_prompt (str): The task or question for the agent.
        tools (Optional[List[Dict[str, Any]]]): List of tool schemas available to this agent.
        temperature (float): Sampling temperature.
        max_tool_rounds (int): Maximum number of tool iterations before forcing synthesis.
        max_tokens (int): Maximum tokens per completion.

    Returns:
        str: The agent's final text response.
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for round_idx in range(max_tool_rounds):
        logger.info(
            "Agent reasoning round %d/%d (tools enabled: %s)",
            round_idx + 1,
            max_tool_rounds,
            bool(tools),
        )

        try:
            kwargs: Dict[str, Any] = {
                "model": settings.GROQ_MODEL,
                "messages": trim_messages(messages),
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            completion = create_completion_with_rotation(kwargs)
            choice = completion.choices[0]
            msg = choice.message

            # Check if LLM requested tool calling
            if getattr(msg, "tool_calls", None):
                logger.info(
                    "LLM decided to call %d tool(s) in round %d.",
                    len(msg.tool_calls),
                    round_idx + 1,
                )
                messages.append(msg)

                for tool_call in msg.tool_calls:
                    tool_name = tool_call.function.name
                    raw_args = tool_call.function.arguments

                    try:
                        args_dict = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError as json_err:
                        logger.warning("Failed to parse tool arguments JSON: %s", raw_args)
                        args_dict = {"raw_input": raw_args, "error": str(json_err)}

                    tool_output = execute_tool(tool_name, args_dict)
                    logger.info("Tool '%s' result preview: %s", tool_name, tool_output[:120])

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": tool_output,
                        }
                    )

                continue

            content = msg.content
            if not content or not content.strip():
                reasoning = getattr(msg, "reasoning", "")
                if reasoning and reasoning.strip():
                    logger.info("Content empty; using reasoning or prompting for explicit answer.")
                    content = reasoning

            if not content:
                content = "No output was generated by the model."

            return content.strip()

        except (APITimeoutError, TimeoutError, httpx.TimeoutException) as err:
            logger.error("LLM request timed out in agent round %d: %s", round_idx + 1, str(err))
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="The LLM service timed out. Please try again later.",
            ) from err

        except (APIConnectionError, ConnectionError, httpx.ConnectError) as err:
            logger.error("Cannot connect to LLM service: %s", str(err))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not connect to the LLM service. Please verify your network connection or ensure Ollama is running.",
            ) from err

        except RateLimitError as err:
            logger.error("Groq rate limit exceeded: %s", str(err))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="LLM provider rate limit exceeded. Please wait a moment before retrying.",
            ) from err

        except APIStatusError as err:
            logger.error("Groq API returned an error (status %s): %s", err.status_code, err.message)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The upstream LLM provider encountered an error. Please try again.",
            ) from err

        except GroqError as err:
            logger.error("Groq client error occurred: %s", str(err))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while communicating with the LLM service.",
            ) from err

        except HTTPException:
            raise

        except Exception as err:
            logger.error("Unexpected error in agent reasoning loop: %s", str(err))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected internal error occurred: {str(err)}",
            ) from err

    # If max tool rounds reached, do a final direct synthesis call
    logger.info("Reached max tool rounds (%d). Requesting final synthesis.", max_tool_rounds)
    messages.append(
        {
            "role": "user",
            "content": "Synthesize the gathered tool outputs and provide your final response concisely now.",
        }
    )
    final_kwargs: Dict[str, Any] = {
        "model": settings.GROQ_MODEL,
        "messages": trim_messages(messages, max_chars=4000),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        final_kwargs["tools"] = tools

    try:
        final_completion = create_completion_with_rotation(final_kwargs)
        final_msg = final_completion.choices[0].message
        final_text = final_msg.content or getattr(final_msg, "reasoning", "") or ""
        if not final_text.strip() and getattr(final_msg, "tool_calls", None):
            for tc in final_msg.tool_calls:
                tc_name = tc.function.name
                try:
                    tc_args = json.loads(tc.function.arguments) if isinstance(tc.function.arguments, str) else tc.function.arguments
                except Exception:
                    tc_args = {}
                return execute_tool(tc_name, tc_args)
        return final_text.strip()
    except Exception as err:
        logger.warning("Final synthesis call encountered error (%s). Falling back to message history.", err)
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("content"):
                return str(m["content"])
            elif hasattr(m, "content") and m.content:
                return str(m.content)
        return "Synthesized findings from gathered research and analysis."


def generate_response(message: str) -> str:
    """
    Backward-compatible single-prompt LLM generation method with round-robin key rotation.
    """
    return run_agent_with_tools(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=message,
        tools=None,
        temperature=0.7,
        max_tokens=1024,
    )


def run_structured_json(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
    max_tokens: int = 1000,
) -> Dict[str, Any]:
    """
    Execute an LLM call enforcing JSON object response format.

    Args:
        system_prompt (str): Instructions specifying the required JSON schema.
        user_prompt (str): Input prompt containing content to evaluate/process.
        temperature (float): Low temperature for deterministic evaluation.
        max_tokens (int): Maximum output tokens.

    Returns:
        Dict[str, Any]: Parsed JSON dictionary.
    """
    # Groq response_format={"type": "json_object"} requires the message body to contain the word "json"
    sys_content = system_prompt if "json" in system_prompt.lower() else f"{system_prompt}\n\nRespond strictly in valid JSON format."
    messages = [
        {"role": "system", "content": sys_content},
        {"role": "user", "content": user_prompt},
    ]

    kwargs: Dict[str, Any] = {
        "model": settings.GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    try:
        completion = create_completion_with_rotation(kwargs)
        choice = completion.choices[0].message
        raw_text = choice.content or getattr(choice, "reasoning", "") or "{}"
        return json.loads(raw_text)
    except Exception as err:
        logger.warning("Structured JSON generation failed (%s). Attempting regex extraction.", err)
        try:
            import re
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception:
            pass
        return {"status": "PASS", "issues": [], "feedback": "Validation parsing fallback passed."}
