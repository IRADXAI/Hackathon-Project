"""End-to-end orchestration of the radiologist reporting workflow.

Ties the data sources, knowledge integration, report tree, and closed-loop
communication together into a single agentic pipeline. Each step is numbered to
match the tool's specification. The run returns a :class:`WorkflowResult` with a
structured trace so both the CLI and the web UI can render the same run.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import critical as critical_mod
from .communication import messaging, phone
from .data_sources import bridge, chart, pacs, rad_model, tech_sheet
from .knowledge import evidence as evidence_mod
from .knowledge import guidelines as guidelines_mod
from .llm import LLM
from .models import Contact, MessageResult, Report, WorkflowResult
from .report import Chooser, auto_chooser, merge_findings, resolve_tree


class _Trace:
    """Collects step events while also echoing them to the console."""

    def __init__(self, quiet: bool = False) -> None:
        self.events: List[Dict[str, str]] = []
        self.quiet = quiet

    def log(self, step: str, msg: str) -> None:
        self.events.append({"step": step, "message": msg})
        if not self.quiet:
            print(f"[{step}] {msg}")

    def detail(self, msg: str) -> None:
        if not self.quiet:
            print(f"          {msg}")


def run_workflow(
    case: Dict[str, Any],
    llm: Optional[LLM] = None,
    choose: Optional[Chooser] = None,
    dictation: Optional[str] = None,
    quiet: bool = False,
) -> WorkflowResult:
    llm = llm or LLM()
    choose = choose or auto_chooser()
    tr = _Trace(quiet=quiet)

    if not quiet:
        print()
    tr.log("engine", f"reasoning backend: {llm.mode}")
    if not quiet:
        print()

    # 1. History from the order bridge.
    patient = bridge.fetch_patient(case)
    history = bridge.fetch_history(case)
    tr.log("1/bridge", f"patient {patient.name} ({patient.mrn}); indication: {history.indication}")

    # 2. Technique + contrast dose from the tech sheet.
    technique = tech_sheet.fetch_technique(case)
    tr.log("2/tech_sheet", technique.description)

    # 3. Comparison from PACS.
    comparison = pacs.fetch_comparison(case)
    tr.log("3/pacs", comparison.prior_description)

    # 4. Template, findings, impression suggested by the radiology model.
    suggestion = rad_model.fetch_suggestion(case)
    tr.log("4/rad_model", f"template '{suggestion.template}'; flagged: {suggestion.flagged_findings or 'none'}")

    # 5. Radiologist dictation of their own findings.
    if dictation is None:
        dictation = case.get("radiologist_dictation", "")
    tr.log("5/dictation", f"radiologist dictation captured ({len(dictation)} chars)")

    # 6. Present the tree of options for building the final report.
    tr.log("6/report_tree", "resolving report-construction options")
    selections = resolve_tree(choose)
    for node_id, key in selections.items():
        tr.detail(f"- {node_id}: {key}")

    # 7. Assemble findings per the chosen branch.
    if selections["findings_source"] == "model":
        findings = suggestion.findings
    elif selections["findings_source"] == "dictation":
        findings = dictation or suggestion.findings
    else:  # merge
        findings = merge_findings(suggestion.findings, dictation)

    # 8. Assemble the impression; integrate evidence if that branch was chosen.
    evidence_notes: List[str] = []
    if selections["impression_source"] == "model":
        impression = suggestion.impression
    elif selections["impression_source"] == "dictation":
        impression = dictation or suggestion.impression
    else:  # evidence
        tr.log("8/evidence", "integrating medical evidence into the impression")
        result = evidence_mod.integrate_evidence(
            llm, history.indication, findings, suggestion.impression
        )
        impression = result["impression"]
        evidence_notes = result["evidence_notes"]

    # 9. Recommendations from current guidelines.
    recommendations: List[str] = []
    if selections["recommendations"] == "guidelines":
        tr.log("9/guidelines", "deriving recommendations from current guidelines")
        recommendations = guidelines_mod.build_recommendations(
            llm, history.indication, impression
        )

    report = Report(
        patient=patient,
        history=history,
        technique=technique,
        comparison=comparison,
        template=suggestion.template,
        findings=findings,
        impression=impression,
        recommendations=recommendations,
        evidence_notes=evidence_notes,
    )

    outcome = WorkflowResult(
        report=report,
        selections=selections,
        dictation=dictation,
        events=tr.events,
        backend=llm.mode,
    )

    # 10. Detect critical / communicable findings.
    tr.log("10/critical", "scanning impression for critical communicable findings")
    critical_findings = critical_mod.detect_critical_findings(llm, impression)
    report.critical_findings = critical_findings

    if not critical_findings:
        tr.log("10/critical", "no critical findings; standard report finalized")
        return outcome

    tr.log("10/critical", f"{len(critical_findings)} CRITICAL finding(s) detected")
    for cf in critical_findings:
        tr.detail(f"! {cf.text}  ({cf.rationale})")

    # 11. Locate the care team from the chart.
    tr.log("11/care_team", "locating ordering physician, PCP, and floor nurse")
    contacts: List[Contact] = []
    for finder in (
        chart.find_ordering_physician,
        chart.find_primary_care_provider,
        chart.find_floor_nurse,
    ):
        c = finder(case)
        if c:
            contacts.append(c)
            tr.detail(f"- {c.role}: {c.name}")
        else:
            tr.detail(f"- {finder.__name__}: not found")

    # 12. Send closed-loop messages to all three.
    tr.log("12/notify", "sending critical-result messages")
    body = _critical_message(patient.name, patient.mrn, critical_findings)
    results = [messaging.send_message(c, body, case) for c in contacts]
    outcome.messages = results
    for r in results:
        status = "ACK" if r.acknowledged else "no-ack"
        tr.detail(f"- {r.contact.role}: {status} ({r.detail})")

    # 13. Escalate any unacknowledged messages; confirm success otherwise.
    _handle_acknowledgements(case, results, patient.name, patient.mrn, critical_findings, tr, outcome)

    return outcome


def _critical_message(name: str, mrn: str, findings: List) -> str:
    items = "; ".join(f.text for f in findings)
    return (
        f"CRITICAL RESULT for {name} (MRN {mrn}): {items}. "
        "Please acknowledge receipt immediately."
    )


def _handle_acknowledgements(
    case: Dict[str, Any],
    results: List[MessageResult],
    name: str,
    mrn: str,
    findings: List,
    tr: _Trace,
    outcome: WorkflowResult,
) -> None:
    unacked = [r for r in results if not r.acknowledged]
    if not unacked:
        tr.log("13/closed_loop", "COMMUNICATION SUCCESSFUL — all recipients acknowledged")
        outcome.communication_successful = True
        return

    roles = ", ".join(r.contact.role for r in unacked)
    tr.log("13/escalate", f"unacknowledged: {roles} — escalating")

    body = _critical_message(name, mrn, findings)
    floor_phone = chart.floor_phone(case)
    outcome.phone_called = True
    answered = phone.call_floor(floor_phone, body, case)
    outcome.phone_answered = answered

    if answered:
        tr.log("13/closed_loop", "COMMUNICATION SUCCESSFUL — floor reached by phone")
        outcome.communication_successful = True
    else:
        phone.alert_radiologist(body)
        outcome.radiologist_alerted = True
        outcome.communication_successful = False
        tr.log(
            "13/closed_loop",
            "COMMUNICATION UNSUCCESSFUL by automated channels — radiologist alerted",
        )
