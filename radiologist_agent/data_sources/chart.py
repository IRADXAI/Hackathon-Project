"""EHR chart — care-team lookup for critical-finding communication.

Locates the three people who must be notified of a critical finding:
  * the ordering physician (from the order)
  * the primary care provider (parsed from the most recent progress notes)
  * the floor nurse currently assigned to the patient's bed (from the chart)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import Contact


def find_ordering_physician(case: Dict[str, Any]) -> Optional[Contact]:
    o = case["chart"].get("ordering_physician")
    if not o:
        return None
    return Contact(
        role="ordering_physician",
        name=o["name"],
        method=o["secure_message"],
        phone=o.get("phone"),
    )


def find_primary_care_provider(case: Dict[str, Any]) -> Optional[Contact]:
    """The PCP is derived from the most recent progress notes, mirroring how
    the attending of record is often only reliably found in the note text."""

    notes: List[Dict[str, Any]] = case["chart"].get("recent_notes", [])
    notes_sorted = sorted(notes, key=lambda n: n.get("date", ""), reverse=True)
    for note in notes_sorted:
        pcp = note.get("primary_care_provider")
        if pcp:
            return Contact(
                role="primary_care_provider",
                name=pcp["name"],
                method=pcp["secure_message"],
                phone=pcp.get("phone"),
            )
    return None


def find_floor_nurse(case: Dict[str, Any]) -> Optional[Contact]:
    n = case["chart"].get("floor_nurse")
    if not n:
        return None
    return Contact(
        role="floor_nurse",
        name=n["name"],
        method=n["secure_message"],
        phone=n.get("phone"),
    )


def floor_phone(case: Dict[str, Any]) -> Optional[str]:
    """Nursing-station callback number for phone escalation."""

    return case["chart"].get("floor_phone")
