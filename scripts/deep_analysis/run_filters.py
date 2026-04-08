"""Shared run inclusion rules for benchmark analysis pipelines."""

from typing import Any, Dict


def is_adaptive_pattern_run(result: Dict[str, Any]) -> bool:
    """True if testee uses the adaptive multi-agent structure (excluded from comparatives analysis)."""
    return "_multi_adaptive" in str(result.get("testee_id", "")).lower()


def is_gpt5_nano_run(result: Dict[str, Any]) -> bool:
    """True if this run used GPT-5-nano (excluded from comparative paper analysis).

    Matches run_id prefixes (e.g. openai_gpt5nano...) and model_version strings.
    """
    rid = str(result.get("run_id", "")).lower()
    if "gpt5nano" in rid or "gpt-5-nano" in rid:
        return True
    model_src = result.get("model_version") or (result.get("agent_config") or {}).get("model") or ""
    mv = str(model_src).lower()
    if "gpt5nano" in mv or "gpt-5-nano" in mv:
        return True
    return False
