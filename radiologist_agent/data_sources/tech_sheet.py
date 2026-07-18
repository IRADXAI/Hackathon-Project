"""Modality tech sheet — technique and contrast dose."""

from __future__ import annotations

from typing import Any, Dict

from ..models import Technique


def fetch_technique(case: Dict[str, Any]) -> Technique:
    t = case["tech_sheet"]
    return Technique(
        description=t["description"],
        contrast_agent=t.get("contrast_agent"),
        contrast_dose=t.get("contrast_dose"),
    )
