"""FastAPI backend for the radiologist reporting agent.

A thin viewer over the pipeline: it exposes the demo case + report tree, runs the
workflow with the caller's dictation / report-tree choices / comms scenario, and
returns the structured :class:`WorkflowResult` for the single-page front end.
"""

from __future__ import annotations

import copy
import dataclasses
import os
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from radiologist_agent.data_sources import load_case
from radiologist_agent.llm import LLM
from radiologist_agent.orchestrator import run_workflow
from radiologist_agent.report import REPORT_TREE, auto_chooser

_STATIC = os.path.join(os.path.dirname(__file__), "static")
_DEFAULT_CASE = "case_ctpa.json"

app = FastAPI(title="Radiologist Reporting Agent")


def _tree_spec() -> Any:
    return [
        {
            "node_id": n.node_id,
            "prompt": n.prompt,
            "default": n.default,
            "options": [{"key": o.key, "label": o.label} for o in n.options],
        }
        for n in REPORT_TREE
    ]


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    with open(os.path.join(_STATIC, "index.html"), "r", encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/api/case")
def get_case() -> JSONResponse:
    case = load_case(_DEFAULT_CASE)
    comms = case.get("communication", {})
    return JSONResponse(
        {
            "patient": case["patient"],
            "indication": case["bridge_note"]["indication"],
            "dictation": case.get("radiologist_dictation", ""),
            "report_tree": _tree_spec(),
            "communication": {
                "acknowledges": comms.get("acknowledges", {}),
                "floor_answers_phone": comms.get("floor_answers_phone", True),
            },
            "backend": LLM().mode,
        }
    )


class RunRequest(BaseModel):
    dictation: str = ""
    selections: Dict[str, str] = {}
    acknowledges: Dict[str, bool] = {}
    floor_answers_phone: bool = True


@app.post("/api/run")
def run(req: RunRequest) -> JSONResponse:
    case = copy.deepcopy(load_case(_DEFAULT_CASE))
    # Apply the UI's communication scenario so both branches can be demoed live.
    comms = case.setdefault("communication", {})
    acks = comms.setdefault("acknowledges", {})
    acks.update(req.acknowledges)
    comms["floor_answers_phone"] = req.floor_answers_phone

    choose = auto_chooser(overrides=req.selections)
    result = run_workflow(
        case,
        llm=LLM(),
        choose=choose,
        dictation=req.dictation,
        quiet=True,
    )

    payload = dataclasses.asdict(result)
    payload["report_text"] = result.report.render()
    return JSONResponse(payload)
