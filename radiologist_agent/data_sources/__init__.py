"""Mock integrations to the clinical source systems.

Each module models one real hospital system the radiologist tool would connect
to (the order bridge, the modality tech sheet, PACS, the radiology AI model,
and the EHR chart). In this prototype they read from a single case JSON file;
in production each ``fetch_*`` call would hit the corresponding HL7 / DICOM /
FHIR endpoint. Keeping them behind one function each means the orchestrator is
unchanged when the real integration is dropped in.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_case(case_file: str) -> Dict[str, Any]:
    path = case_file
    if not os.path.isabs(path):
        candidate = os.path.join(_DATA_DIR, case_file)
        path = candidate if os.path.exists(candidate) else case_file
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
