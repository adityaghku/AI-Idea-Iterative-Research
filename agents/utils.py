from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any, Optional

from .config import (
    DEFAULT_DB_PATH,
    DEFAULT_SCRAPER_COOLDOWN_SECONDS,
)
from .logger import get_logger

logger = get_logger()


def get_current_epoch() -> int:
    return int(time.time())


def call_db(cmd: str, db_path: str = DEFAULT_DB_PATH, **kwargs) -> Any:
    """Execute idea_harvester_db.py command and return parsed result.
    
    Args:
        cmd: The subcommand to execute
        db_path: Path to the SQLite database
        **kwargs: Additional arguments for the command
        
    Returns:
        Parsed JSON result or None
    """
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_script = os.path.join(script_dir, "db", "idea_harvester_db.py")
    args = ["python3", db_script, cmd, "--db", db_path]
    
    for key, value in kwargs.items():
        if value is None:
            continue
        arg_key = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                args.append(arg_key)
        else:
            args.append(arg_key)
            args.append(str(value))
    
    result = None
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout.strip()
        if output == "null" or output == "OK":
            return None if output == "null" else "OK"
        return json.loads(output)
    except subprocess.CalledProcessError as e:
        logger.error(f"DB command failed: {cmd}, stderr: {e.stderr}")
        raise
    except json.JSONDecodeError:
        if result is not None:
            return result.stdout.strip()
        raise


def can_scrape(
    db_path: str,
    run_task_id: str,
    cooldown_seconds: int = DEFAULT_SCRAPER_COOLDOWN_SECONDS,
) -> tuple[bool, int]:
    """Check if enough time has passed since last scrape.
    
    Args:
        db_path: Path to the database
        run_task_id: The run task ID
        cooldown_seconds: Minimum seconds between scrapes
        
    Returns:
        Tuple of (can_proceed, seconds_until_available)
    """
    last = call_db("get-kv", db_path, run_task_id=run_task_id, key="scraper_last_completed_epoch")
    
    if last is None:
        return True, 0
    
    last_epoch = last.get("epoch", 0)
    elapsed = get_current_epoch() - last_epoch
    
    if elapsed >= cooldown_seconds:
        return True, 0
    
    return False, cooldown_seconds - elapsed


def update_scraper_timestamp(db_path: str, run_task_id: str) -> None:
    """Update the last scrape timestamp in knowledge_kv."""
    call_db(
        "upsert-kv",
        db_path,
        run_task_id=run_task_id,
        key="scraper_last_completed_epoch",
        value=json.dumps({"epoch": get_current_epoch()}),
    )


def get_knowledge(db_path: str, run_task_id: str, key: str) -> Optional[dict[str, Any]]:
    """Get a knowledge_kv value."""
    return call_db("get-kv", db_path, run_task_id=run_task_id, key=key)


def set_knowledge(db_path: str, run_task_id: str, key: str, value: dict[str, Any]) -> None:
    """Set a knowledge_kv value."""
    call_db(
        "upsert-kv",
        db_path,
        run_task_id=run_task_id,
        key=key,
        value=json.dumps(value),
    )


def create_run(
    db_path: str,
    task_id: str,
    goal: str,
    max_iterations: int,
    plateau_window: int,
    min_improvement: float,
    model: Optional[str] = None,
) -> str:
    """Create a new run in the database.
    
    Returns:
        The task_id
    """
    call_db(
        "create-run",
        db_path,
        task_id=task_id,
        goal=goal,
        model=model or "",
        max_iterations=max_iterations,
        plateau_window=plateau_window,
        min_improvement=min_improvement,
    )
    return task_id


def ensure_iteration(db_path: str, run_task_id: str, iteration_number: int) -> None:
    """Ensure an iteration row exists."""
    call_db("ensure-iteration", db_path, run_task_id=run_task_id, iteration_number=iteration_number)


def enqueue_message(
    db_path: str,
    run_task_id: str,
    from_agent: str,
    to_agent: str,
    stage: str,
    payload: dict[str, Any],
    iteration_number: Optional[int] = None,
    available_at: Optional[int] = None,
) -> int:
    """Enqueue a message for an agent.
    
    Returns:
        The message_id
    """
    result = call_db(
        "enqueue",
        db_path,
        run_task_id=run_task_id,
        from_agent=from_agent,
        to_agent=to_agent,
        stage=stage,
        payload=json.dumps(payload),
        iteration_number=iteration_number,
        available_at=available_at,
    )
    # enqueue returns the message_id directly
    if isinstance(result, str) and result.isdigit():
        return int(result)
    return 0


def dequeue_message(
    db_path: str,
    run_task_id: str,
    to_agent: str,
    iteration_number: Optional[int] = None,
    stage: Optional[str] = None,
    locked_by: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Dequeue a pending message for an agent."""
    result = call_db(
        "dequeue",
        db_path,
        run_task_id=run_task_id,
        to_agent=to_agent,
        iteration_number=iteration_number,
        stage=stage,
        locked_by=locked_by,
    )
    if result == "null" or result is None:
        return None
    return result


def mark_done(db_path: str, message_id: int, result: dict[str, Any]) -> None:
    """Mark a message as done."""
    call_db("mark-done", db_path, message_id=message_id, result=json.dumps(result))


def mark_failed(db_path: str, message_id: int, error: str) -> None:
    """Mark a message as failed."""
    call_db("mark-failed", db_path, message_id=message_id, error=error)


def store_iteration_output(
    db_path: str,
    run_task_id: str,
    iteration_number: int,
    stage: str,
    output: dict[str, Any],
) -> None:
    """Store agent stage output in iteration row."""
    call_db(
        "store-iteration-output",
        db_path,
        run_task_id=run_task_id,
        iteration_number=iteration_number,
        stage=stage,
        json=json.dumps(output),
    )


def store_ideas(
    db_path: str,
    run_task_id: str,
    iteration_number: int,
    ideas: list[dict[str, Any]],
) -> None:
    """Store evaluated ideas (handles dedup via fingerprint)."""
    call_db(
        "store-ideas",
        db_path,
        run_task_id=run_task_id,
        iteration_number=iteration_number,
        ideas=json.dumps(ideas),
    )


def store_validation(
    db_path: str,
    run_task_id: str,
    iteration_number: int,
    validation_score: float,
    validation_explain: str,
) -> None:
    """Store validation metrics for an iteration."""
    call_db(
        "store-iteration-validation",
        db_path,
        run_task_id=run_task_id,
        iteration_number=iteration_number,
        score=validation_score,
        explain=validation_explain,
    )


def get_iteration_scores(db_path: str, run_task_id: str) -> list[dict[str, Any]]:
    """Get average scores for all iterations."""
    return call_db("iteration-scores", db_path, run_task_id=run_task_id) or []


def get_top_ideas(db_path: str, run_task_id: str, limit: int = 10) -> list[dict[str, Any]]:
    """Get top N ideas by score."""
    return call_db("top-ideas", db_path, run_task_id=run_task_id, limit=limit) or []


def filter_new_urls(
    db_path: str,
    run_task_id: str,
    urls: list[str],
    retry_limit: int = 2,
) -> dict[str, list[str]]:
    """Filter URLs to only those not yet seen (or failed with attempts < retry_limit).
    
    Returns:
        Dict with 'keep_urls' and 'skipped_urls'
    """
    return call_db(
        "filter-new-urls",
        db_path,
        run_task_id=run_task_id,
        urls=json.dumps(urls),
        retry_limit=retry_limit,
    ) or {"keep_urls": [], "skipped_urls": []}


def mark_sources_status(
    db_path: str,
    run_task_id: str,
    urls: list[str],
    status: str,
) -> None:
    """Mark URLs with a status in the sources table."""
    call_db(
        "mark-sources-status",
        db_path,
        run_task_id=run_task_id,
        urls=json.dumps(urls),
        status=status,
    )


def list_pending_messages(
    db_path: str,
    run_task_id: str,
    to_agent: Optional[str] = None,
    stage: Optional[str] = None,
    iteration_number: Optional[int] = None,
) -> list[dict[str, Any]]:
    """List pending queue messages."""
    return call_db(
        "pending-messages",
        db_path,
        run_task_id=run_task_id,
        to_agent=to_agent,
        stage=stage,
        iteration_number=iteration_number,
    ) or []


def store_iteration_complete(
    db_path: str,
    run_task_id: str,
    iteration_number: int,
    status: str = "complete",
) -> None:
    """Mark an iteration as complete."""
    # This is handled by store_iteration_output for most cases,
    # but we can update the status field if needed
    call_db(
        "store-iteration-output",
        db_path,
        run_task_id=run_task_id,
        iteration_number=iteration_number,
        stage="learner",
        json={"status": status},
    )
