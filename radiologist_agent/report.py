"""The report-building decision tree.

Rather than a single fixed assembly, the tool offers the radiologist a tree of
options at each stage of report creation. A ``Chooser`` callback resolves each
node — interactively (CLI prompt) or automatically (scripted defaults) — so the
same tree drives both a live reading session and an autonomous demo run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

# A chooser is given (node_id, prompt, options) and returns the chosen key.
Chooser = Callable[[str, str, List["Option"]], str]


@dataclass
class Option:
    key: str
    label: str


@dataclass
class DecisionNode:
    node_id: str
    prompt: str
    options: List[Option]
    default: str


# The tree of options presented to build the final report.
REPORT_TREE: List[DecisionNode] = [
    DecisionNode(
        node_id="findings_source",
        prompt="How should the FINDINGS be sourced?",
        options=[
            Option("model", "Accept the radiology model's findings"),
            Option("dictation", "Use the radiologist's own dictation"),
            Option("merge", "Merge model findings with the dictation"),
        ],
        default="merge",
    ),
    DecisionNode(
        node_id="impression_source",
        prompt="How should the IMPRESSION be created?",
        options=[
            Option("model", "Use the model's impression as-is"),
            Option("evidence", "Integrate medical evidence into the impression"),
            Option("dictation", "Use the radiologist's dictated impression"),
        ],
        default="evidence",
    ),
    DecisionNode(
        node_id="recommendations",
        prompt="Add guideline-based RECOMMENDATIONS?",
        options=[
            Option("guidelines", "Generate recommendations from current guidelines"),
            Option("none", "No recommendations"),
        ],
        default="guidelines",
    ),
]


def resolve_tree(choose: Chooser) -> Dict[str, str]:
    """Walk the report tree, returning the chosen key for each node."""

    selections: Dict[str, str] = {}
    for node in REPORT_TREE:
        selections[node.node_id] = choose(node.node_id, node.prompt, node.options)
    return selections


def auto_chooser(overrides: Dict[str, str] = None) -> Chooser:
    """A non-interactive chooser using node defaults (or supplied overrides)."""

    overrides = overrides or {}

    def _choose(node_id: str, prompt: str, options: List[Option]) -> str:
        if node_id in overrides:
            return overrides[node_id]
        node = next(n for n in REPORT_TREE if n.node_id == node_id)
        return node.default

    return _choose


def merge_findings(model_findings: str, dictation: str) -> str:
    """Combine model findings with the radiologist's dictated additions."""

    if not dictation.strip():
        return model_findings
    return (
        model_findings.rstrip()
        + "\n\nRadiologist addendum:\n"
        + dictation.strip()
    )
