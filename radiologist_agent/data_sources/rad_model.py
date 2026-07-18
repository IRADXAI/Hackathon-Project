"""Radiology AI model — suggests a report template, findings, and impression."""

from __future__ import annotations

from typing import Any, Dict

from ..models import ModelSuggestion


def fetch_suggestion(case: Dict[str, Any]) -> ModelSuggestion:
    m = case["radiology_model"]
    return ModelSuggestion(
        template=m["template"],
        findings=m["findings"],
        impression=m["impression"],
        flagged_findings=m.get("flagged_findings", []),
    )
