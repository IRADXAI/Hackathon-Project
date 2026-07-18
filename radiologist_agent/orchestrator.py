"""End-to-end orchestration of the radiologist reporting workflow.

Ties the data sources, knowledge integration, report tree, and closed-loop
communication together into a single agentic pipeline. Each step is numbered to
match the tool's specification.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from . import critical as critical_mod
from .communication import messaging, phone
from .data_sources import bridge, chart, pacs, rad_model, tech_sheet
from .knowledge import evidence as evidence_mod
from .knowledge import guidelines as guidelines_mod
from .llm import LLM
from .models import Contact, MessageResult, Report
from .report import Chooser, auto_chooser, merge_findings, resolve_tree


def _log(step: str, msg: str) -> None:
    print(f"[{step}] {msg}")


def run_workflow(
    case: Dict[str, Any],
    llm: Optional[LLM] = None,
    choose: Optional[Chooser] = None,
    dictation: Optional[str] = None,
) -> Report:
    llm = llm or LLM()
    choose = choose or auto_chooser()

    print()
    _log("engine", f"reasoning backend: {llm.mode}")
    print()

    # 1. History from the order bridge.
    patient = bridge.fetch_patient(case)
    history = bridge.fetch_history(case)
    _log("1/bridge", f"patient {patient.name} ({patient.mrn}); indication: {history.indication}")

    # 2. Technique + contrast dose from the tech sheet.
    technique = tech_sheet.fetch_technique(case)
    _log("2/tech_sheet", technique.description)

    # 3. Comparison from PACS.
    comparison = pacs.fetch_comparison(case)
    _log("3/pacs", comparison.prior_description)

    # 4. Template, findings, impression suggested by the radiology model.
    suggestion = rad_model.fetch_suggestion(case)
    _log("4/rad_model", f"template '{suggestion.template}'; flagged: {suggestion.flagged_findings or 'none'}")

    # 5. Radiologist dictation of their own findings.
    if dictation is None:
        dictation = case.get("radiologist_dictation", "")
    _log("5/dictation", f"radiologist dictation captured ({len(dictation)} chars)")

    # 6. Present the tree of options for building the final report.
    _log("6/report_tree", "resolving report-construction options")
    selections = resolve_tree(choose)
    for node_id, key in selections.items():
        print(f"          - {node_id}: {key}")

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
        _log("8/evidence", "integrating medical evidence into the impression")
        result = evidence_mod.integrate_evidence(
            llm, history.indication, findings, suggestion.impression
        )
        impression = result["impression"]
        evidence_notes = result["evidence_notes"]

    # 9. Recommendations from current guidelines.
    recommendations: List[str] = []
    if selections["recommendations"] == "guidelines":
        _log("9/guidelines", "deriving recommendations from current guidelines")
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

    # 10. Detect critical / communicable findings.
    _log("10/critical", "scanning impression for critical communicable findings")
    critical_findings = critical_mod.detect_critical_findings(llm, impression)
    report.critical_findings = critical_findings

    if not critical_findings:
        _log("10/critical", "no critical findings; standard report finalized")
        return report

    _log("10/critical", f"{len(critical_findings)} CRITICAL finding(s) detected")
    for cf in critical_findings:
        print(f"          ! {cf.text}  ({cf.rationale})")

    # 11. Locate the care team from the chart.
    _log("11/care_team", "locating ordering physician, PCP, and floor nurse")
    contacts: List[Contact] = []
    for finder in (
        chart.find_ordering_physician,
        chart.find_primary_care_provider,
        chart.find_floor_nurse,
    ):
        c = finder(case)
        if c:
            contacts.append(c)
            print(f"          - {c.role}: {c.name}")
        else:
            print(f"          - {finder.__name__}: not found")

    # 12. Send closed-loop messages to all three.
    _log("12/notify", "sending critical-result messages")
    body = _critical_message(patient.name, patient.mrn, critical_findings)
    results = [messaging.send_message(c, body, case) for c in contacts]
    for r in results:
        status = "ACK" if r.acknowledged else "no-ack"
        print(f"          - {r.contact.role}: {status} ({r.detail})")

    # 13. Escalate any unacknowledged messages; confirm success otherwise.
    _handle_acknowledgements(case, results, patient.name, patient.mrn, critical_findings)

    return report


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
) -> None:
    unacked = [r for r in results if not r.acknowledged]
    if not unacked:
        _log("13/closed_loop", "COMMUNICATION SUCCESSFUL — all recipients acknowledged")
        return

    roles = ", ".join(r.contact.role for r in unacked)
    _log("13/escalate", f"unacknowledged: {roles} — escalating")

    body = _critical_message(name, mrn, findings)
    floor_phone = chart.floor_phone(case)
    answered = phone.call_floor(floor_phone, body, case)

    if answered:
        _log("13/closed_loop", "COMMUNICATION SUCCESSFUL — floor reached by phone")
    else:
        phone.alert_radiologist(body)
        _log(
            "13/closed_loop",
            "COMMUNICATION UNSUCCESSFUL by automated channels — radiologist alerted",
        )
