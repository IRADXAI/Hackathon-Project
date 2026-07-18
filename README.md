# Hackathon-Project — Radiologist Reporting Agent

An agentic workflow that assembles a radiology report from the clinical source
systems, sharpens it with medical evidence and current guidelines, and — when a
critical finding is present — runs closed-loop communication with the care team
until the result is acknowledged.

## What it does

The workflow (`radiologist_agent/orchestrator.py`) runs these steps in order:

1. **Bridge** — pulls the clinical **history** from the order/HL7 note.
2. **Tech sheet** — pulls the **technique** and **contrast dose**.
3. **PACS** — pulls the prior-study **comparison**.
4. **Radiology model** — suggests a **template**, **findings**, and **impression**.
5. **Dictation** — prompts the radiologist to add their **own findings**.
6. **Report tree** — presents a **tree of options** for building the final report
   (findings source, impression source, recommendations).
7–9. Assembles findings/impression, **integrates medical evidence** into the
   impression, and derives **recommendations from current guidelines**.
10. **Critical detection** — flags any **critical communicable findings**.
11. **Care team** — if critical, finds the **ordering physician**, the
    **primary care provider** (from recent notes), and the **floor nurse**
    (from the chart).
12. **Notify** — sends secure messages to **all three**.
13. **Escalate / confirm** — if messages go **unacknowledged**, calls the floor
    by **phone** or **alerts the radiologist**; if communication **succeeds**, it
    says so.

## Architecture

```
radiologist_agent/
  orchestrator.py        end-to-end pipeline (the 13 steps)
  data_sources/          mock integrations to real hospital systems
    bridge.py            order/HL7 note  -> history
    tech_sheet.py        modality sheet  -> technique + contrast dose
    pacs.py              PACS            -> prior comparison
    rad_model.py         AI model        -> template/findings/impression
    chart.py             EHR chart       -> care-team lookup
  knowledge/
    evidence.py          evidence-informed impression   (Claude)
    guidelines.py        guideline-based recommendations (Claude)
  critical.py            critical-finding classification (Claude)
  communication/
    messaging.py         secure messaging + acknowledgement
    phone.py             phone escalation + radiologist alert
  report.py              the report-construction decision tree
  llm.py                 Claude wrapper (with offline fallback)
  data/case_ctpa.json    sample case (CTPA showing acute PE)
```

Each `data_sources/*` module stands in for a real HL7 / DICOM / FHIR
integration; swapping in the live endpoint leaves the orchestrator unchanged.

## Reasoning backend

The open-ended judgement steps (evidence synthesis, guideline recommendations,
critical-finding detection) call **Claude (`claude-opus-4-8`)**. If no
credentials are configured the tool falls back to a deterministic offline mode
so the full pipeline still runs — the console prints which backend is active.

To use Claude, set a key (or `ant auth login`):

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Setup & run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python main.py                 # run the bundled CTPA demo case
.venv/bin/python main.py --interactive   # navigate the report tree + dictate
.venv/bin/python main.py --case path.json
```

The demo case is a CT pulmonary angiogram showing an **acute pulmonary
embolism** — a critical finding — so it exercises the full detect → notify →
escalate → confirm communication path.

## Web UI

A FastAPI backend + a single self-contained HTML page (`web/`) — a viewer over
the pipeline. Dictate in the browser, pick the report-tree options, toggle the
communication scenario (who acknowledges, whether the floor answers the phone),
and watch the report, critical-finding banner, and closed-loop communication
timeline update.

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn web.server:app --port 8010   # http://localhost:8010
```

Endpoints: `GET /api/case` (demo case + report tree), `POST /api/run` (runs the
workflow with the caller's dictation / choices / comms scenario and returns the
structured result).
