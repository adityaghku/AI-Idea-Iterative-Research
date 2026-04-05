#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from agents import (  # noqa: E402
    Orchestrator,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PLATEAU_WINDOW,
    DEFAULT_MIN_IMPROVEMENT,
    DEFAULT_DB_PATH,
    setup_logging,
)

_DEFAULT_GOAL = """Find innovative mobile app ideas with high market potential that can be started by a solo founder but have room to scale.

Focus on ideas that:
- Are specifically mobile applications (iOS/Android apps, not web platforms or SaaS)
- Solve real, painful problems for specific user segments
- Can be built and launched by one person without significant capital
- Have clear paths to monetization and customer acquisition (subscriptions, in-app purchases, freemium)
- Provide genuine value through smart UX, automation, or solving niche problems
- Target markets that aren't already saturated with similar solutions
- Leverage mobile-native features (camera, GPS, notifications, sensors, offline capabilities)

Avoid:
- Generic apps that are just clones of existing successful apps
- Ideas requiring massive infrastructure or enterprise sales
- Solutions looking for problems (technology-first approaches)
- Markets dominated by well-funded incumbents
- Web-based SaaS tools (not mobile apps)
"""


def resolve_goal(args: argparse.Namespace) -> str:
    """Goal from --goal-file (highest priority), then --goal, else default."""
    if getattr(args, "goal_file", None) is not None:
        path = args.goal_file
        if not path.is_file():
            raise SystemExit(f"Goal file not found: {path}")
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            raise SystemExit(f"Goal file is empty: {path}")
        return text
    if getattr(args, "goal", None):
        return args.goal.strip()
    return _DEFAULT_GOAL


def run_llm_test() -> bool:
    print("\nRunning LLM connectivity test...")
    test_script = _ROOT / "test_llm.py"
    if not test_script.is_file():
        print(
            f"\nFatal: missing {test_script} (run from project directory or install test_llm.py)."
        )
        return False
    result = subprocess.run(
        [sys.executable, str(test_script)],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Idea Harvester - Multi-agent AI idea discovery system for finding innovative AI startup opportunities"
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum iterations (default: {DEFAULT_MAX_ITERATIONS})",
    )
    parser.add_argument(
        "--plateau-window",
        type=int,
        default=DEFAULT_PLATEAU_WINDOW,
        help=f"Plateau detection window (default: {DEFAULT_PLATEAU_WINDOW})",
    )
    parser.add_argument(
        "--min-improvement",
        type=float,
        default=DEFAULT_MIN_IMPROVEMENT,
        help=f"Minimum improvement threshold (default: {DEFAULT_MIN_IMPROVEMENT})",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing run",
    )
    parser.add_argument(
        "--run-task-id",
        help="Run task ID (for resume)",
    )
    parser.add_argument(
        "--model",
        help="Model name for tracking",
    )
    parser.add_argument(
        "--goal",
        help="Goal text for this run (default: built-in goal)",
    )
    parser.add_argument(
        "--goal-file",
        type=Path,
        help="Read goal text from this file (UTF-8); overrides --goal",
    )
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable verbose logging (default: True, use --no-verbose to disable)",
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    if os.path.exists(".idea-harvester-off"):
        print("Stop sentinel detected (.idea-harvester-off). Remove it to resume.")
        sys.exit(0)

    if not run_llm_test():
        print("\nFatal: LLM test failed")
        sys.exit(1)

    print("\nLLM test passed. Starting Idea Harvester...")

    goal = resolve_goal(args)

    orchestrator = Orchestrator(
        db_path=args.db,
        run_task_id=args.run_task_id,
        goal=goal,
        max_iterations=args.max_iterations,
        plateau_window=args.plateau_window,
        min_improvement=args.min_improvement,
        model=args.model,
    )

    try:
        if args.resume:
            orchestrator.resume()
        else:
            orchestrator.start()
    except KeyboardInterrupt:
        print("\nInterrupted by user. Run state saved to database.")
        print(
            f"Resume with: python main.py --resume --run-task-id {orchestrator.config.run_task_id}"
        )
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
