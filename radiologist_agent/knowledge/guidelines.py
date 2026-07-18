"""Generate recommendations from current clinical guidelines.

Maps the impression to actionable, guideline-anchored follow-up recommendations
(e.g. Fleischner Society for pulmonary nodules, PERT activation for acute PE).
Offline, a deterministic keyword-driven fallback is used.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..llm import LLM

_SCHEMA = {
    "type": "object",
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Guideline-anchored recommendations; name the guideline.",
        }
    },
    "required": ["recommendations"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are a radiologist writing the recommendations section of a report. "
    "Base each recommendation on current, widely accepted clinical guidelines "
    "and name the guideline or society when applicable (e.g. Fleischner Society, "
    "ACR Appropriateness Criteria, PERT). Keep them specific and actionable."
)


def build_recommendations(
    llm: LLM,
    indication: str,
    impression: str,
) -> List[str]:
    prompt = (
        f"Clinical indication: {indication}\n\n"
        f"IMPRESSION:\n{impression}\n\n"
        "List the guideline-based follow-up recommendations."
    )

    def _mock() -> Dict[str, Any]:
        recs: List[str] = []
        low = impression.lower()
        if "pulmonary embol" in low or "pe" in low.split():
            recs.append(
                "Acute PE: recommend immediate clinical correlation and "
                "anticoagulation per ACCP/PERT guidance if not contraindicated."
            )
            recs.append(
                "Assess right-heart strain (RV/LV ratio, troponin, BNP) for risk "
                "stratification per ESC acute PE guidelines."
            )
        if "nodule" in low:
            recs.append(
                "Pulmonary nodule: follow Fleischner Society 2017 criteria for "
                "interval CT follow-up based on size and risk."
            )
        if not recs:
            recs.append(
                "Clinical correlation recommended; no dedicated imaging follow-up "
                "indicated by current guidelines."
            )
        return {"recommendations": recs}

    result = llm.complete_json(_SYSTEM, prompt, _SCHEMA, _mock)
    return result.get("recommendations", [])
