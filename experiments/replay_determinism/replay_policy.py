"""Replay skip and timeout policy for trajectory reproduction."""

from __future__ import annotations

from typing import Any, Optional


def session_convergence_timeout(
    timeout_seconds: Optional[float],
    default: float = 30.0,
    min_wait: float = 0.0,
) -> int:
    """Use the task's declared convergence budget for session setup.

    Replay previously hardcoded 30s. Troubleshooting tasks declare 45--120s
    because fault verification (e.g. BGP Established) needs that window.
    BGP's default connect-retry is 120s, so a longer ``min_wait`` floor is
    applied when the caller requests it.
    """
    declared = int(default) if timeout_seconds is None else int(timeout_seconds)
    return max(declared, int(min_wait))


def should_skip_existing(
    existing: dict[str, Any],
    *,
    rerun_unstable: bool,
) -> bool:
    """Skip a saved replay only when it is a completed result we still trust.

    Setup errors are never skipped. Completeness mismatches are skipped unless
    ``rerun_unstable`` is set, so a longer wait can be retried.
    """
    if existing.get("error"):
        return False
    if "replay_terminal_completeness" not in existing:
        return False
    if rerun_unstable and not existing.get("stable"):
        return False
    return True
