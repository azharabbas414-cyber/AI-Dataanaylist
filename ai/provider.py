import os
import streamlit as st
from openai import OpenAI


class AIProvider:
    def is_available(self):
        return False

    def analyze(self, prompt):
        raise NotImplementedError


class GroqProvider(AIProvider):
    def __init__(self):
        self.api_key = self._get_secret("GROQ_API_KEY")
        self.model = self._get_secret(
            "GROQ_MODEL",
            "llama-3.3-70b-versatile"
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
            raise RuntimeError("GROQ_API_KEY is not configured.")

        client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
        )

        response = client.responses.create(
            model=self.model,
            input=prompt,
        )

        return response.output_text


def get_ai_provider():
    return GroqProvider()
