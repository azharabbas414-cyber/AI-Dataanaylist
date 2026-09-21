import os
import streamlit as st


class AIProvider:
    def is_available(self):
        return False

    def analyze(self, prompt):
        raise NotImplementedError


class GrokProvider(AIProvider):
    def __init__(self):
        self.api_key = self._get_secret("GROK_API_KEY")
        self.model = self._get_secret(
            "GROK_MODEL",
            "grok-4-1-fast-non-reasoning"
        )

    def _get_secret(self, key, default=None):
        try:
            value = st.secrets.get(key)
            if value:
                return value
        except Exception:
            pass

        return os.getenv(key, default)

    def is_available(self):
        return bool(self.api_key)

    def analyze(self, prompt):
        if not self.is_available():
            raise RuntimeError("GROK_API_KEY is not configured.")

        from openai import OpenAI

        client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.x.ai/v1",
        )

        response = client.responses.create(
            model=self.model,
            input=prompt,
        )

        return response.output_text


def get_ai_provider():
    provider_name = "grok"

    if provider_name == "grok":
        return GrokProvider()

    return None
