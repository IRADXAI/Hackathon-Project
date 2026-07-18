"""Detect critical / communicable findings in the final impression.

A "critical result" is one that requires urgent, documented, closed-loop
communication with the care team (per ACR Actionable Reporting guidance).
Claude classifies each impression line; offline, a keyword rule set is used.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .llm import LLM
from .models import CriticalFinding, Severity

_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["routine", "urgent", "critical"],
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["text", "severity", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

_SYSTEM = (
    "You are a radiologist applying ACR Actionable Reporting guidance. Classify "
    "each impression statement as 'routine', 'urgent', or 'critical'. 'critical' "
    "means a finding that could be life-threatening if not communicated "
    "immediately (e.g. acute PE, tension pneumothorax, aortic dissection, "
    "intracranial hemorrhage, misplaced tube/line). Provide a brief rationale."
)

# Keyword rules for the offline fallback. Each entry: (keyword, severity).
_CRITICAL_KEYWORDS = [
    "pulmonary embol",
    "tension pneumothorax",
    "aortic dissection",
    "intracranial hemorrhage",
    "intracranial haemorrhage",
    "free air",
    "pneumoperitoneum",
    "malpositioned",
    "misplaced",
    "acute stroke",
    "bowel ischemia",
    "ectopic pregnancy",
]
_URGENT_KEYWORDS = ["pneumothorax", "abscess", "obstruction", "new nodule"]


def detect_critical_findings(llm: LLM, impression: str) -> List[CriticalFinding]:
    prompt = (
        "Classify each line of this radiology impression.\n\n"
        f"IMPRESSION:\n{impression}\n"
    )

    def _mock() -> Dict[str, Any]:
        out: List[Dict[str, str]] = []
        for line in impression.strip().splitlines():
            low = line.lower()
            sev = "routine"
            rationale = "No time-critical feature detected."
            for kw in _CRITICAL_KEYWORDS:
                if kw in low:
                    sev = "critical"
                    rationale = f"Matches critical result criterion: '{kw}'."
                    break
            else:
                for kw in _URGENT_KEYWORDS:
                    if kw in low:
                        sev = "urgent"
                        rationale = f"Potentially urgent finding: '{kw}'."
                        break
            out.append({"text": line.strip(), "severity": sev, "rationale": rationale})
        return {"findings": out}

    result = llm.complete_json(_SYSTEM, prompt, _SCHEMA, _mock)
    findings: List[CriticalFinding] = []
    for item in result.get("findings", []):
        try:
            sev = Severity(item["severity"])
        except ValueError:
            sev = Severity.ROUTINE
        if sev is Severity.CRITICAL:
            findings.append(
                CriticalFinding(
                    text=item["text"], severity=sev, rationale=item["rationale"]
                )
            )
    return findings
