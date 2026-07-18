"""Command-line entry point for the radiologist reporting agent."""

from __future__ import annotations

import argparse
import sys
from typing import List

from .data_sources import load_case
from .llm import LLM
from .orchestrator import run_workflow
from .report import REPORT_TREE, Option, auto_chooser


def _interactive_chooser():
    def _choose(node_id: str, prompt: str, options: List[Option]) -> str:
        node = next(n for n in REPORT_TREE if n.node_id == node_id)
        print(f"\n? {prompt}")
        for i, opt in enumerate(options, 1):
            marker = " (default)" if opt.key == node.default else ""
            print(f"    {i}. {opt.label}{marker}")
        while True:
            raw = input(f"  choose 1-{len(options)} [default]: ").strip()
            if not raw:
                return node.default
            if raw.isdigit() and 1 <= int(raw) <= len(options):
                return options[int(raw) - 1].key
            print("  invalid choice; try again")

    return _choose


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="radiologist-agent",
        description="Agentic radiology reporting workflow with closed-loop "
        "critical-finding communication.",
    )
    parser.add_argument(
        "--case",
        default="case_ctpa.json",
        help="Case JSON file (name in the bundled data dir, or a path).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for report-tree choices and dictation.",
    )
    parser.add_argument(
        "--dictation",
        default=None,
        help="Override the radiologist dictation text.",
    )
    args = parser.parse_args(argv)

    try:
        case = load_case(args.case)
    except FileNotFoundError:
        print(f"error: case file not found: {args.case}", file=sys.stderr)
        return 2

    dictation = args.dictation
    if args.interactive and dictation is None:
        print("\nEnter your dictation (findings/impression). Blank line to finish:")
        lines: List[str] = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line == "":
                break
            lines.append(line)
        dictation = "\n".join(lines)

    choose = _interactive_chooser() if args.interactive else auto_chooser()

    result = run_workflow(case, llm=LLM(), choose=choose, dictation=dictation)

    print()
    print(result.report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
