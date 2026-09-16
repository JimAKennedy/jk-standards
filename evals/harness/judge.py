"""deepeval custom judge model backed by the Anthropic API.

No other provider is referenced anywhere in this harness: the same key
that runs the agent arms runs the judge. The client is injected so the
offline tests never construct a real one.

deepeval's metrics call ``generate(prompt, schema=SomePydanticModel)`` and
use the returned instance directly when the model supports it — that path
skips deepeval's fragile raw-JSON trimming, so this judge implements it:
Claude is asked for bare JSON matching the schema and the reply is
validated, with one corrective retry before giving up loudly.
"""

from __future__ import annotations

import json

from deepeval.models import DeepEvalBaseLLM


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


class AnthropicJudge(DeepEvalBaseLLM):
    def __init__(self, client, model: str, max_tokens: int = 4000) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def load_model(self):
        return self._client

    def _call(self, prompt: str) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(getattr(b, "text", "") for b in resp.content)

    def generate(self, prompt: str, schema=None, **kwargs):
        if schema is None:
            return self._call(prompt)
        fields = ", ".join(schema.model_fields)
        ask = (
            f"{prompt}\n\nReply with ONLY a JSON object with the fields: "
            f"{fields}. No prose, no code fences."
        )
        last_err: Exception | None = None
        for attempt in range(2):
            raw = self._call(
                ask
                if attempt == 0
                else f"{ask}\n\nYour previous reply was not valid JSON. JSON only."
            )
            try:
                return schema.model_validate(json.loads(_strip_fences(raw)))
            except (json.JSONDecodeError, ValueError) as e:
                last_err = e
        raise ValueError(
            f"judge did not produce valid {schema.__name__} JSON after retry: {last_err}"
        )

    async def a_generate(self, prompt: str, schema=None, **kwargs):
        return self.generate(prompt, schema=schema, **kwargs)

    def get_model_name(self) -> str:
        return self._model
