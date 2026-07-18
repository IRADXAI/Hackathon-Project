"""PACS — prior study comparison."""

from __future__ import annotations

from typing import Any, Dict

from ..models import Comparison


def fetch_comparison(case: Dict[str, Any]) -> Comparison:
    c = case["pacs"]
    return Comparison(
        prior_available=c.get("prior_available", False),
        prior_description=c["prior_description"],
    )
