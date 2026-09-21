
import os


class AIProvider:
    """
    Base interface for AI providers.
    """

    def is_available(self):
        return False

    def analyze(self, prompt):
        raise NotImplementedError


class OpenAIProvider(AIProvider):
    """
    OpenAI provider using the Responses API.
    """

    def __init__(self):

        self.api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        self.model = os.getenv(
            "OPENAI_MODEL",
            "gpt-5.6-luna"
        )

    def is_available(self):

        return bool(self.api_key)

    def analyze(self, prompt):

        if not self.is_available():

            raise RuntimeError(
                "OPENAI_API_KEY is not configured."
            )

        from openai import OpenAI

        client = OpenAI(
            api_key=self.api_key
        )

        response = client.responses.create(
            model=self.model,
            input=prompt
        )

        return response.output_text


def get_ai_provider():

    provider_name = os.getenv(
        "AI_PROVIDER",
        "openai"
    ).lower()

    if provider_name == "openai":

        return OpenAIProvider()

    return None
