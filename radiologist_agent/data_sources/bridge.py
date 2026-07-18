"""Order bridge — pulls the clinical history from the order/HL7 note."""

from __future__ import annotations

from typing import Any, Dict

from ..models import History, Patient


def fetch_patient(case: Dict[str, Any]) -> Patient:
    p = case["patient"]
    return Patient(
        mrn=p["mrn"],
        name=p["name"],
        age=p["age"],
        sex=p["sex"],
        location=p["location"],
    )


def fetch_history(case: Dict[str, Any]) -> History:
    note = case["bridge_note"]
    return History(indication=note["indication"], narrative=note["narrative"])
