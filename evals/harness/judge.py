"""deepeval custom judge model backed by the Anthropic API.

No other provider is referenced anywhere in this harness: the same key
that runs the agent arms runs the judge. The client is injected so the
offline tests never construct a real one.
"""

from __future__ import annotations

from deepeval.models import DeepEvalBaseLLM


class AnthropicJudge(DeepEvalBaseLLM):
    def __init__(self, client, model: str, max_tokens: int = 1500) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def load_model(self):
        return self._client

    def generate(self, prompt: str, *args, **kwargs) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(getattr(b, "text", "") for b in resp.content)

    async def a_generate(self, prompt: str, *args, **kwargs) -> str:
        return self.generate(prompt, *args, **kwargs)

    def get_model_name(self) -> str:
        return self._model
