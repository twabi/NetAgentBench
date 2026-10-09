"""Post-submit convergence wait for trajectory replay."""

from __future__ import annotations

import time
from typing import Callable, Optional

DEFAULT_MIN_WAIT_SECONDS = 90.0
DEFAULT_INTERVAL_SECONDS = 5.0
TOL = 1e-9


def pre_eval_wait_seconds(
    timeout_seconds: Optional[float],
    min_wait: float = DEFAULT_MIN_WAIT_SECONDS,
) -> float:
    """Return the post-submit wait, never below ``min_wait``.

    The live harness caps this wait at 30s; agents still get extra OSPF/BGP
    wall-clock during LLM think-time. Replay has no think-time, so the floor
    recovers convergence-gated terminal properties.
    """
    timeout = 10.0 if timeout_seconds is None else float(timeout_seconds)
    return max(timeout, float(min_wait))


def poll_until(
    evaluate: Callable[[], float],
    target: Optional[float],
    max_wait: float,
    interval: float = DEFAULT_INTERVAL_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
    tol: float = TOL,
    plateau_rounds: int = 0,
) -> tuple[float, float]:
    """Sleep in ``interval`` steps, evaluating after each, until match or timeout.

    If ``plateau_rounds`` > 0, stop early once that many consecutive evaluations
    are equal and still miss ``target`` (further waiting cannot recover an
    already-converged mismatch).

    Returns ``(final_score, waited_seconds)``.
    """
    waited = 0.0
    last = 0.0
    streak = 0
    while waited < max_wait:
        step = min(interval, max_wait - waited)
        sleep(step)
        waited += step
        current = evaluate()
        if target is not None and abs(current - float(target)) <= tol:
            return current, waited
        if plateau_rounds > 0 and abs(current - last) <= tol:
            streak += 1
            if streak >= plateau_rounds:
                return current, waited
        else:
            streak = 1
        last = current
    return last, waited
