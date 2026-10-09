from wait_eval import poll_until, pre_eval_wait_seconds
from replay_policy import session_convergence_timeout, should_skip_existing


def test_pre_eval_wait_uses_floor_when_task_timeout_is_lower():
    assert pre_eval_wait_seconds(45) == 90.0
    assert pre_eval_wait_seconds(None) == 90.0


def test_pre_eval_wait_keeps_longer_task_timeout():
    assert pre_eval_wait_seconds(120) == 120.0


def test_pre_eval_wait_honors_explicit_200s_floor():
    assert pre_eval_wait_seconds(45, min_wait=200) == 200.0
    assert pre_eval_wait_seconds(120, min_wait=200) == 200.0


def test_poll_until_stops_when_completeness_matches_target():
    scores = iter([0.5, 0.75, 1.0, 1.0])
    slept: list[float] = []

    def evaluate() -> float:
        return next(scores)

    final, waited = poll_until(
        evaluate=evaluate,
        target=1.0,
        max_wait=90.0,
        interval=5.0,
        sleep=slept.append,
    )
    assert final == 1.0
    assert waited == 15.0
    assert slept == [5.0, 5.0, 5.0]


def test_poll_until_exhausts_max_wait_when_target_never_matches():
    slept: list[float] = []

    final, waited = poll_until(
        evaluate=lambda: 0.75,
        target=1.0,
        max_wait=12.0,
        interval=5.0,
        sleep=slept.append,
    )
    assert final == 0.75
    assert waited == 12.0
    assert slept == [5.0, 5.0, 2.0]


def test_session_timeout_uses_task_convergence_not_hardcoded_30():
    assert session_convergence_timeout(None) == 30
    assert session_convergence_timeout(60) == 60
    assert session_convergence_timeout(120) == 120


def test_session_timeout_floors_to_min_wait():
    assert session_convergence_timeout(60, min_wait=200) == 200
    assert session_convergence_timeout(120, min_wait=90) == 120


def test_poll_until_stops_on_nonmatching_plateau():
    scores = iter([0.6, 0.6, 0.6, 0.6])
    slept: list[float] = []
    final, waited = poll_until(
        evaluate=lambda: next(scores),
        target=0.2,
        max_wait=200.0,
        interval=5.0,
        sleep=slept.append,
        plateau_rounds=3,
    )
    assert final == 0.6
    assert waited == 15.0
    assert len(slept) == 3


def test_skip_completed_stable_replays():
    existing = {"replay_terminal_completeness": 1.0, "stable": True}
    assert should_skip_existing(existing, rerun_unstable=False) is True
    assert should_skip_existing(existing, rerun_unstable=True) is True


def test_retry_errors_and_unstable_when_requested():
    errored = {"error": "Fault verification failed", "stable": False}
    unstable = {"replay_terminal_completeness": 0.6, "stable": False}
    assert should_skip_existing(errored, rerun_unstable=False) is False
    assert should_skip_existing(errored, rerun_unstable=True) is False
    assert should_skip_existing(unstable, rerun_unstable=False) is True
    assert should_skip_existing(unstable, rerun_unstable=True) is False
