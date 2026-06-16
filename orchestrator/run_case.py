"""CLI entry point for running a Sangam polypharmacy case end-to-end.

Usage:
    uv run python -m orchestrator.run_case --case case_1_warfarin_guggulu

Posts the case's sample_message to the Sangam Case Room, then polls every 3 s
(timeout 120 s) for a FINAL_VERDICT or PENDING_HUMAN_REVIEW from @ComplianceGuard.
Prints the verdict as formatted JSON when found.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from orchestrator.band_client import ROOM_ID, poll_for_verdict, post_case_message

load_dotenv()

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "case_studies.json"


def load_case(case_id: str) -> dict:
    """Find a case by ID in data/case_studies.json; exit with error if not found."""
    with open(DATA_PATH, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    for case in cases:
        if case["id"] == case_id:
            return case
    available = [c["id"] for c in cases]
    print(f"Error: case {case_id!r} not found.", file=sys.stderr)
    print(f"Available cases: {available}", file=sys.stderr)
    sys.exit(1)


async def run_case_analysis(
    case_id: str,
    room_id: str = ROOM_ID,
    timeout_s: float = 120.0,
    poll_interval_s: float = 3.0,
) -> dict | None:
    """Post a case to the Band room and wait for ComplianceGuard's verdict.

    Importable by the Streamlit frontend so it can call this directly without
    spawning a subprocess.
    """
    case = load_case(case_id)
    print(f"[{case['id']}] {case['title']}")
    print(f"Posting to room {room_id}...")

    posted_at = await post_case_message(case["sample_message"], room_id=room_id)
    print(f"Posted at {posted_at.isoformat()}")
    print(f"Polling for verdict (timeout={timeout_s}s, interval={poll_interval_s}s)...")

    verdict = await poll_for_verdict(
        room_id=room_id,
        posted_at=posted_at,
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    )
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a Sangam polypharmacy case end-to-end through the Band room."
    )
    parser.add_argument(
        "--case",
        required=True,
        metavar="CASE_ID",
        help="Case ID from data/case_studies.json (e.g. case_1_warfarin_guggulu)",
    )
    parser.add_argument(
        "--room",
        default=ROOM_ID,
        metavar="ROOM_ID",
        help="Band room ID (defaults to BAND_ROOM_ID env var)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        metavar="SECONDS",
        help="Maximum seconds to wait for a verdict (default 120)",
    )
    args = parser.parse_args()

    verdict = asyncio.run(
        run_case_analysis(args.case, room_id=args.room, timeout_s=args.timeout)
    )

    if verdict is None:
        print("\n[TIMEOUT] No verdict received within the timeout period.", file=sys.stderr)
        print("Check that all 6 agent processes are running:", file=sys.stderr)
        print("  bash scripts/start_agents.sh", file=sys.stderr)
        sys.exit(2)

    print("\n[VERDICT RECEIVED]")
    print(json.dumps(verdict, indent=2))


if __name__ == "__main__":
    main()
