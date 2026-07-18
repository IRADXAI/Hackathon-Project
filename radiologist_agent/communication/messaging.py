"""Secure messaging channel for critical-result notification.

In production this would post to the hospital secure-messaging / paging API and
wait on a delivery + read receipt. Here it is simulated: whether a contact
acknowledges is driven by the case file's ``acknowledges`` map, so the demo can
exercise both the happy path and the escalation path deterministically.
"""

from __future__ import annotations

from typing import Any, Dict

from ..models import Contact, MessageResult


def send_message(
    contact: Contact,
    body: str,
    case: Dict[str, Any],
    ack_wait_seconds: int = 0,
) -> MessageResult:
    ack_map: Dict[str, bool] = case.get("communication", {}).get("acknowledges", {})
    acknowledged = bool(ack_map.get(contact.role, False))
    print(f"    -> secure message to {contact.role} ({contact.name}) via {contact.method}")
    print(f"       body: {body}")
    if acknowledged:
        detail = "delivered; read receipt + acknowledgement received"
    else:
        detail = "delivered; NO acknowledgement within window"
    return MessageResult(
        contact=contact,
        delivered=True,
        acknowledged=acknowledged,
        detail=detail,
    )
