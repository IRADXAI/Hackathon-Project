"""Typed data structures shared across the workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Severity(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    CRITICAL = "critical"


@dataclass
class Patient:
    mrn: str
    name: str
    age: int
    sex: str
    location: str  # e.g. "5 West, Bed 12"


@dataclass
class History:
    """Clinical history pulled from the bridge (HL7/order) note."""

    indication: str
    narrative: str
    source: str = "bridge"


@dataclass
class Technique:
    """Technique + contrast dose pulled from the modality tech sheet."""

    description: str
    contrast_agent: Optional[str]
    contrast_dose: Optional[str]
    source: str = "tech_sheet"


@dataclass
class Comparison:
    """Prior study comparison pulled from PACS."""

    prior_available: bool
    prior_description: str
    source: str = "pacs"


@dataclass
class ModelSuggestion:
    """Output of the radiology AI model."""

    template: str
    findings: str
    impression: str
    flagged_findings: List[str] = field(default_factory=list)
    source: str = "radiology_model"


@dataclass
class Contact:
    role: str  # "ordering_physician" | "primary_care_provider" | "floor_nurse"
    name: str
    method: str  # secure message address / pager / phone
    phone: Optional[str] = None


@dataclass
class CriticalFinding:
    text: str
    severity: Severity
    rationale: str


@dataclass
class MessageResult:
    contact: Contact
    delivered: bool
    acknowledged: bool
    detail: str


@dataclass
class Report:
    patient: Patient
    history: History
    technique: Technique
    comparison: Comparison
    template: str
    findings: str
    impression: str
    recommendations: List[str] = field(default_factory=list)
    evidence_notes: List[str] = field(default_factory=list)
    critical_findings: List[CriticalFinding] = field(default_factory=list)

    def render(self) -> str:  # noqa: C901
        lines: List[str] = []
        p = self.patient
        lines.append("=" * 72)
        lines.append("RADIOLOGY REPORT")
        lines.append("=" * 72)
        lines.append(f"Patient: {p.name}    MRN: {p.mrn}    {p.age}{p.sex}")
        lines.append(f"Location: {p.location}")
        lines.append(f"Exam template: {self.template}")
        lines.append("")
        lines.append("CLINICAL HISTORY:")
        lines.append(f"  {self.history.narrative}")
        lines.append("")
        lines.append("TECHNIQUE:")
        tech = self.technique.description
        if self.technique.contrast_agent:
            tech += (
                f" Contrast: {self.technique.contrast_agent}"
                f" {self.technique.contrast_dose or ''}".rstrip()
            )
        lines.append(f"  {tech}")
        lines.append("")
        lines.append("COMPARISON:")
        lines.append(f"  {self.comparison.prior_description}")
        lines.append("")
        lines.append("FINDINGS:")
        for para in self.findings.strip().splitlines():
            lines.append(f"  {para}")
        lines.append("")
        lines.append("IMPRESSION:")
        for i, para in enumerate(self.impression.strip().splitlines(), 1):
            lines.append(f"  {para}")
        if self.recommendations:
            lines.append("")
            lines.append("RECOMMENDATIONS:")
            for rec in self.recommendations:
                lines.append(f"  - {rec}")
        if self.evidence_notes:
            lines.append("")
            lines.append("SUPPORTING EVIDENCE:")
            for note in self.evidence_notes:
                lines.append(f"  - {note}")
        if self.critical_findings:
            lines.append("")
            lines.append("** CRITICAL / COMMUNICABLE FINDINGS **")
            for cf in self.critical_findings:
                lines.append(f"  [{cf.severity.value.upper()}] {cf.text}")
        lines.append("=" * 72)
        return "\n".join(lines)


@dataclass
class WorkflowResult:
    """Structured output of a full workflow run — drives both the CLI and UI."""

    report: Report
    selections: Dict[str, str] = field(default_factory=dict)
    dictation: str = ""
    messages: List[MessageResult] = field(default_factory=list)
    phone_called: bool = False
    phone_answered: bool = False
    radiologist_alerted: bool = False
    # None when there is no critical finding (no communication required).
    communication_successful: Optional[bool] = None
    events: List[Dict[str, str]] = field(default_factory=list)
    backend: str = ""
