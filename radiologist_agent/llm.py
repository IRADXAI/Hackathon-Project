"""Thin wrapper over the Claude API for the agentic reasoning steps.

The workflow calls Claude for the genuinely open-ended judgement steps
(evidence synthesis, guideline-based recommendations, critical-finding
detection). If no credentials are available the wrapper falls back to a
caller-supplied deterministic ``mock`` function so the whole pipeline still
runs end-to-end — useful for demos, tests, and offline development.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

MODEL = "claude-opus-4-8"


class LLM:
    def __init__(self, model: str = MODEL) -> None:
        self.model = model
        self._client = None
        self._reason = ""
        self._init_client()

    def _init_client(self) -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            self._reason = "anthropic SDK not installed"
            return
        # A bare client picks up ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or an
        # `ant auth login` profile. Only fall back to mock mode when nothing at
        # all is configured.
        if not (
            os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        ):
            self._reason = "no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN"
            return
        import anthropic

        try:
            self._client = anthropic.Anthropic()
        except Exception as exc:  # pragma: no cover - defensive
            self._reason = f"client init failed: {exc}"
            self._client = None

    @property
    def live(self) -> bool:
        return self._client is not None

    @property
    def mode(self) -> str:
        return "Claude (%s)" % self.model if self.live else "demo/mock (%s)" % self._reason

    def complete_json(
        self,
        system: str,
        prompt: str,
        schema: Dict[str, Any],
        mock: Callable[[], Any],
        max_tokens: int = 4096,
    ) -> Any:
        """Return a validated JSON object from Claude, or ``mock()`` offline."""

        if not self.live:
            return mock()
        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "high",
                    "format": {"type": "json_schema", "schema": schema},
                },
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # pragma: no cover - network/runtime guard
            print(f"    [llm] request failed ({exc}); using deterministic fallback")
            return mock()
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print("    [llm] response was not valid JSON; using fallback")
            return mock()
