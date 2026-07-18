"""Integrate medical evidence to sharpen the impression.

Given the draft findings and impression, ask Claude to (a) produce an
evidence-informed impression and (b) list the supporting evidence points a
radiologist could stand behind. Offline, a deterministic fallback keyed to the
draft impression keeps the pipeline running.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..llm import LLM

_SCHEMA = {
    "type": "object",
    "properties": {
        "impression": {
            "type": "string",
            "description": "Evidence-informed impression, one finding per line.",
        },
        "evidence_notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concise supporting-evidence statements.",
        },
    },
    "required": ["impression", "evidence_notes"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are a board-certified radiologist refining a report impression. "
    "Ground each statement in established radiologic evidence and imaging "
    "criteria. Be precise and clinically conservative. Do not invent findings "
    "that are not supported by the provided findings text."
)


def integrate_evidence(
    llm: LLM,
    indication: str,
    findings: str,
    draft_impression: str,
) -> Dict[str, Any]:
    prompt = (
        f"Clinical indication: {indication}\n\n"
        f"FINDINGS:\n{findings}\n\n"
        f"DRAFT IMPRESSION:\n{draft_impression}\n\n"
        "Return an evidence-informed impression (one item per line) and a short "
        "list of supporting-evidence notes."
    )

    def _mock() -> Dict[str, Any]:
        notes: List[str] = []
        low = (findings + " " + draft_impression).lower()
        if "pulmonary embol" in low or "filling defect" in low:
            notes.append(
                "Acute PE on CTPA is defined by an intraluminal filling defect; "
                "RV/LV diameter ratio >1.0 signals right-heart strain."
            )
        if "reflux" in low or "esophag" in low:
            notes.append(
                "Contrast reflux into the IVC/hepatic veins can indicate elevated "
                "right-sided pressures rather than pure technique artifact."
            )
        if not notes:
            notes.append(
                "Impression aligned with described findings; no additional "
                "evidence modifiers applied."
            )
        return {"impression": draft_impression.strip(), "evidence_notes": notes}

    return llm.complete_json(_SYSTEM, prompt, _SCHEMA, _mock)
