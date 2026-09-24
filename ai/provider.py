"""AI provider abstraction for InsightAI.

The app keeps provider-specific details here so the UI and analyst engine
do not need to know how the model is called.

Current provider:
- Groq through the OpenAI-compatible Python client.

Secrets:
- GROQ_API_KEY
- GROQ_MODEL (optional)
"""
from __future__ import annotations

import os
from typing import Any

import streamlit as st
from openai import OpenAI


class AIProvider:
    """Base interface for an InsightAI model provider."""

    provider_name = "AI Provider"

    def is_available(self) -> bool:
        return False

    def analyze(self, prompt: str) -> str:
        raise NotImplementedError


class GroqProvider(AIProvider):
    """Groq provider using its OpenAI-compatible API."""

    provider_name = "Groq"

    def __init__(self) -> None:
        self.api_key = self._get_secret("GROQ_API_KEY")
        self.model = self._get_secret(
            "GROQ_MODEL",
            "openai/gpt-oss-120b",
        )
        self.base_url = self._get_secret(
            "GROQ_BASE_URL",
            "https://api.groq.com/openai/v1",
        )

    @staticmethod
    def _get_secret(key: str, default: Any = None) -> Any:
        try:
            value = st.secrets.get(key)
            if value:
                return value
        except Exception:
            pass

        return os.getenv(key, default)

    def is_available(self) -> bool:
        return bool(self.api_key)

    def analyze(self, prompt: str) -> str:
        if not self.is_available():
            raise RuntimeError(
                "GROQ_API_KEY is not configured."
            )

        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

        # Chat Completions is used for broad compatibility with
        # OpenAI-compatible providers and Groq-hosted models.
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are InsightAI, a professional evidence-grounded "
                        "data analyst. Answer only from the supplied context."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The AI provider returned an empty response.")

        return content.strip()


def get_ai_provider() -> AIProvider:
    """Return the configured AI provider."""
    return GroqProvider()
