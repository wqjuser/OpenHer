"""Provider configuration boundary tests."""

from __future__ import annotations

import importlib
import os
from typing import Any, cast
import unittest
from unittest.mock import patch


class _FakeLLMProvider:
    def __init__(
        self,
        model=None,
        api_key=None,
        base_url=None,
        temperature=0.92,
        max_tokens=1024,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens


class ProviderConfigBoundaryTests(unittest.TestCase):
    def _reload_configs(self):
        api_config = importlib.import_module("providers.api_config")
        provider_config = importlib.import_module("providers.config")
        api_config.reload()
        provider_config.reload()
        return api_config, provider_config

    def test_api_config_delegates_to_provider_config_for_llm_resolution(self):
        with patch.dict(
            os.environ,
            {
                "DEFAULT_PROVIDER": "deepseek",
                "LLM_API_KEY": "shared-key",
                "LLM_BASE_URL": "https://gateway.example.test/v1",
            },
            clear=True,
        ):
            api_config, provider_config = self._reload_configs()

            self.assertEqual(api_config.get_llm_config(), provider_config.get_llm_config())

    def test_registry_reuses_central_llm_config_resolution(self):
        from providers import config as provider_config
        from providers import registry

        central_cfg = {
            "provider": "deepseek",
            "model": "central-model",
            "api_key": "central-key",
            "base_url": "https://central.example.test/v1",
            "temperature": 0.11,
            "max_tokens": 17,
            "providers": {},
        }

        with patch.dict(
            os.environ,
            {
                "DEFAULT_PROVIDER": "deepseek",
                "DEEPSEEK_API_KEY": "env-key",
                "DEEPSEEK_BASE_URL": "https://env.example.test/v1",
            },
            clear=True,
        ):
            provider_config.reload()
            with patch.dict(registry._LLM_PROVIDERS, {"deepseek": _FakeLLMProvider}, clear=True):
                with patch("providers.registry.get_llm_config", return_value=central_cfg, create=True) as get_config:
                    provider = cast(Any, registry.get_llm())

        self.assertEqual(get_config.call_count, 1)
        self.assertEqual(provider.model, "central-model")
        self.assertEqual(provider.api_key, "central-key")
        self.assertEqual(provider.base_url, "https://central.example.test/v1")
        self.assertEqual(provider.temperature, 0.11)
        self.assertEqual(provider.max_tokens, 17)

    def test_registry_provider_override_resolves_that_provider_config(self):
        from providers import config as provider_config
        from providers import registry

        with patch.dict(
            os.environ,
            {
                "DEFAULT_PROVIDER": "deepseek",
                "DEEPSEEK_API_KEY": "deepseek-key",
                "DEEPSEEK_BASE_URL": "https://deepseek.example.test",
                "OPENAI_API_KEY": "openai-key",
                "OPENAI_BASE_URL": "https://openai.example.test/v1",
            },
            clear=True,
        ):
            provider_config.reload()
            with patch.dict(registry._LLM_PROVIDERS, {"openai": _FakeLLMProvider}, clear=True):
                provider = cast(Any, registry.get_llm(provider="openai"))

        self.assertEqual(provider.api_key, "openai-key")
        self.assertEqual(provider.base_url, "https://openai.example.test/v1")
        self.assertNotEqual(provider.api_key, "deepseek-key")
        self.assertNotEqual(provider.base_url, "https://deepseek.example.test")

    def test_memory_config_single_source_enables_cloud_when_only_api_key_is_set(self):
        with patch.dict(os.environ, {"EVERMEMOS_API_KEY": "cloud-key"}, clear=True):
            api_config, provider_config = self._reload_configs()

            api_memory = api_config.get_memory_config()
            provider_memory = provider_config.get_memory_config()
            provider_nested = provider_config.get_memory_provider_config()["evermemos"]

        self.assertEqual(api_memory, provider_memory)
        self.assertTrue(provider_memory["enabled"])
        self.assertEqual(provider_memory["base_url"], "https://api.evermind.ai/api/v1")
        self.assertEqual(provider_memory["api_key"], "cloud-key")
        self.assertEqual(provider_nested, provider_memory)

    def test_tts_config_marks_active_provider_unavailable_when_key_is_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            _api_config, provider_config = self._reload_configs()

            tts = provider_config.get_tts_config()

        self.assertEqual(tts["provider"], "dashscope")
        self.assertFalse(tts["available"])
        self.assertEqual(tts["active_api_key"], "")
        self.assertEqual(tts["missing_key_env"], "DASHSCOPE_API_KEY")

    def test_tts_config_marks_active_provider_available_when_key_is_set(self):
        with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "dash-key"}, clear=True):
            _api_config, provider_config = self._reload_configs()

            tts = provider_config.get_tts_config()

        self.assertTrue(tts["available"])
        self.assertEqual(tts["active_api_key"], "dash-key")
        self.assertEqual(tts["missing_key_env"], "")


if __name__ == "__main__":
    unittest.main()
