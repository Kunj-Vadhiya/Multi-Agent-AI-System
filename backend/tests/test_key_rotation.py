"""
Unit tests for round-robin API key rotation and failover.
"""

from unittest.mock import MagicMock, PropertyMock, patch
from groq import RateLimitError
import pytest

from app.config import settings
from app.services.llm_service import KeyRotator, create_completion_with_rotation


def test_key_rotator_round_robin_sequence(monkeypatch):
    """Verify keys are delivered in exact round-robin order."""
    rotator = KeyRotator()
    fake_keys = ["key_alpha", "key_beta", "key_gamma"]
    monkeypatch.setattr(settings, "GROQ_API_KEYS", fake_keys)

    sequence = [rotator.get_next_key() for _ in range(7)]
    assert sequence == [
        "key_alpha",
        "key_beta",
        "key_gamma",
        "key_alpha",
        "key_beta",
        "key_gamma",
        "key_alpha",
    ]


def test_key_rotator_thread_safety(monkeypatch):
    """Verify thread-safe concurrent access produces evenly distributed counts."""
    from concurrent.futures import ThreadPoolExecutor

    rotator = KeyRotator()
    fake_keys = ["key_1", "key_2"]
    monkeypatch.setattr(settings, "GROQ_API_KEYS", fake_keys)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: rotator.get_next_key(), range(100)))

    count_1 = results.count("key_1")
    count_2 = results.count("key_2")
    assert count_1 == 50
    assert count_2 == 50


def test_failover_on_rate_limit(monkeypatch):
    """Verify create_completion_with_rotation automatically fails over to next key on 429."""
    fake_keys = ["rate_limited_key", "good_key"]
    monkeypatch.setattr(settings, "GROQ_API_KEYS", fake_keys)

    mock_rate_limit_response = MagicMock()
    mock_rate_limit_response.status_code = 429
    mock_rate_limit_err = RateLimitError(
        message="Rate limit exceeded",
        response=mock_rate_limit_response,
        body=None,
    )

    mock_good_completion = MagicMock()
    mock_good_completion.choices = [MagicMock(message=MagicMock(content="Success with good key"))]

    mock_client_fail = MagicMock()
    mock_client_fail.chat.completions.create.side_effect = mock_rate_limit_err

    mock_client_success = MagicMock()
    mock_client_success.chat.completions.create.return_value = mock_good_completion

    def client_side_effect(api_key: str, **kwargs):
        if api_key == "rate_limited_key":
            return mock_client_fail
        return mock_client_success

    with patch("app.services.llm_service.Groq", side_effect=client_side_effect):
        result = create_completion_with_rotation({"model": "test-model", "messages": []})
        assert result.choices[0].message.content == "Success with good key"


def test_multi_provider_round_robin_targets(monkeypatch):
    """Verify targets rotate across Groq, OpenAI, OpenRouter, and Grok."""
    rotator = KeyRotator()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "round_robin")
    monkeypatch.setattr(settings, "GROQ_API_KEYS", ["groq_1"])
    monkeypatch.setattr(settings, "OPENAI_API_KEYS", ["openai_1", "openai_2"])
    monkeypatch.setattr(settings, "OPENROUTER_API_KEYS", ["openrouter_1"])
    monkeypatch.setattr(settings, "GROK_API_KEYS", ["grok_1"])

    targets = rotator.get_active_targets()
    assert len(targets) == 5
    providers = [t.provider for t in targets]
    assert providers == ["groq", "openai", "openrouter", "grok", "openai"]

    # Test round-robin rotation through interleaved providers
    collected_keys = [rotator.get_next_target().api_key for _ in range(7)]
    assert collected_keys == [
        "groq_1",
        "openai_1",
        "openrouter_1",
        "grok_1",
        "openai_2",
        "groq_1",
        "openai_1",
    ]


def test_single_provider_selection(monkeypatch):
    """Verify filtering to only OpenAI when LLM_PROVIDER='openai'."""
    rotator = KeyRotator()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "GROQ_API_KEYS", ["groq_1"])
    monkeypatch.setattr(settings, "OPENAI_API_KEYS", ["openai_1", "openai_2"])
    monkeypatch.setattr(settings, "OPENROUTER_API_KEYS", ["openrouter_1"])

    targets = rotator.get_active_targets()
    assert len(targets) == 2
    assert all(t.provider == "openai" for t in targets)


def test_cross_provider_failover(monkeypatch):
    """Verify that failover seamlessly jumps from a rate-limited OpenAI key to an OpenRouter or Grok key."""
    rotator = KeyRotator()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "round_robin")
    monkeypatch.setattr(settings, "GROQ_API_KEYS", [])
    monkeypatch.setattr(settings, "OPENAI_API_KEYS", ["rate_limited_openai"])
    monkeypatch.setattr(settings, "OPENROUTER_API_KEYS", ["healthy_openrouter"])
    monkeypatch.setattr(settings, "GROK_API_KEYS", [])

    mock_rate_limit_response = MagicMock()
    mock_rate_limit_response.status_code = 429
    mock_rate_limit_err = RateLimitError(
        message="Rate limit exceeded",
        response=mock_rate_limit_response,
        body=None,
    )

    mock_good_completion = MagicMock()
    mock_good_completion.choices = [MagicMock(message=MagicMock(content="Success with OpenRouter"))]

    mock_client_fail = MagicMock()
    mock_client_fail.chat.completions.create.side_effect = mock_rate_limit_err

    mock_client_success = MagicMock()
    mock_client_success.chat.completions.create.return_value = mock_good_completion

    def client_factory(api_key: str, **kwargs):
        if api_key == "rate_limited_openai":
            return mock_client_fail
        return mock_client_success

    with patch("app.services.llm_service.Groq", side_effect=client_factory):
        result = create_completion_with_rotation({"model": "gpt-4o-mini", "messages": []})
        assert result.choices[0].message.content == "Success with OpenRouter"


def test_ollama_provider_selection(monkeypatch):
    """Verify that setting LLM_PROVIDER='ollama' routes exclusively to the local Ollama instance."""
    rotator = KeyRotator()
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "qwen3.5:4b")

    targets = rotator.get_active_targets()
    assert len(targets) == 1
    assert targets[0].provider == "ollama"
    assert targets[0].default_model == "qwen3.5:4b"
    assert targets[0].base_url == "http://127.0.0.1:11434"

