#!/usr/bin/env python3
"""Run the radiologist reporting agent.

Usage:
    python main.py                 # run the bundled CTPA demo case
    python main.py --interactive   # choose report-tree options + dictate
    python main.py --case path.json
"""

from radiologist_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
