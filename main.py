#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys

from agents import Orchestrator, DEFAULT_MAX_ITERATIONS, DEFAULT_PLATEAU_WINDOW, DEFAULT_MIN_IMPROVEMENT, DEFAULT_DB_PATH, setup_logging

HARDCODED_GOAL = """Find innovative AI application and product ideas with high market potential that can be started by a solo founder but have room to scale.

Focus on ideas that:
- Solve real, painful problems for specific user segments
- Leverage current AI capabilities (LLMs, computer vision, agents, automation)
- Can be built and launched by one person without significant capital
- Have clear paths to monetization and customer acquisition
- Aren't just "wrappers" around existing AI tools but provide genuine value
- Target markets that aren't already saturated with similar solutions
- Can achieve initial traction within 3-6 months of development

Avoid:
- Generic AI chatbots or writing assistants
- Ideas requiring massive datasets or compute resources
- Solutions looking for problems (technology-first approaches)
- Markets dominated by well-funded incumbents
- Ideas requiring regulatory approval or compliance (healthcare, finance) without clear moats"""


def run_llm_test():
    print("\nRunning LLM connectivity test...")
    result = subprocess.run(
        [sys.executable, "test_llm.py"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0


def main():
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

    orchestrator = Orchestrator(
        db_path=args.db,
        run_task_id=args.run_task_id,
        goal=HARDCODED_GOAL,
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
        print("Resume with: python main.py --resume --run-task-id", orchestrator.config.run_task_id)
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
