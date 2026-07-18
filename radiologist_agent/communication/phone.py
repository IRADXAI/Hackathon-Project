"""Phone escalation and radiologist alerting for unacknowledged criticals.

Last resort when secure messages go unacknowledged: place an automated call to
the nursing-station line, and if that also fails, alert the reading
radiologist so a human closes the loop. Simulated via the case file's
``floor_answers_phone`` flag.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def call_floor(floor_phone: Optional[str], body: str, case: Dict[str, Any]) -> bool:
    if not floor_phone:
        print("    -> no floor phone number on file; cannot place call")
        return False
    answered = bool(case.get("communication", {}).get("floor_answers_phone", False))
    print(f"    -> placing phone call to floor line {floor_phone}")
    print(f"       message: {body}")
    if answered:
        print("       call answered; critical result read back and confirmed")
    else:
        print("       call NOT answered")
    return answered


def alert_radiologist(body: str) -> None:
    print("    -> ALERTING READING RADIOLOGIST: automated communication failed")
    print(f"       {body}")
    print("       radiologist must personally close the communication loop")
