"""Hybrid retraining trigger policy.

Evaluates three independent signals and blocks on guards (cooldown + min-sample gate).
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_PERSIST_PATH = "storage/drift"
_TRIGGER_STATE_FILE = "trigger_state.json"


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_json(path: str, data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        logger.warning("[drift] failed to save %s: %s", path, exc)


def _trigger_state_path(persist_path: str) -> str:
    return os.path.join(persist_path, _TRIGGER_STATE_FILE)


# ---------------------------------------------------------------------------
# Public helpers for the detection path
# ---------------------------------------------------------------------------

def record_new_samples(n: int, persist_path: str = _DEFAULT_PERSIST_PATH) -> None:
    """Increment the new-sample counter. Called from the detection path per batch."""
    path = _trigger_state_path(persist_path)
    state = _load_json(path)
    state["n_new_samples"] = state.get("n_new_samples", 0) + n
    _save_json(path, state)


def mark_retrain_complete(persist_path: str = _DEFAULT_PERSIST_PATH) -> None:
    """Reset counters after a retrain has been triggered successfully."""
    path = _trigger_state_path(persist_path)
    state = _load_json(path)
    state["last_retrain_at"] = datetime.now(timezone.utc).isoformat()
    state["n_new_samples"] = 0
    _save_json(path, state)


# ---------------------------------------------------------------------------
# Main policy
# ---------------------------------------------------------------------------

def should_retrain(
    persist_path: str = _DEFAULT_PERSIST_PATH,
    cooldown_days: int = 7,
    min_new_samples: int = 500,
    cadence_days: int = 30,
    drift_window_min_count: int = 3,
) -> Tuple[bool, List[str]]:
    """Evaluate the hybrid retrain policy.

    Returns (should_retrain: bool, reasons: list[str]).

    Triggers if ANY of:
      (a) feature drift detected in >= drift_window_min_count recent windows
      (b) ADWIN performance drift fired
      (c) >= cadence_days elapsed since last retrain (cadence floor)

    Blocked by:
      - within cooldown_days of the last retrain
      - fewer than min_new_samples new samples accumulated
    """
    trigger_state = _load_json(_trigger_state_path(persist_path))
    last_retrain_str: Optional[str] = trigger_state.get("last_retrain_at")
    n_new_samples: int = trigger_state.get("n_new_samples", 0)
    now = datetime.now(timezone.utc)

    # --- Guard: cooldown ---
    if last_retrain_str:
        last_retrain = datetime.fromisoformat(last_retrain_str)
        days_since = (now - last_retrain).days
        if days_since < cooldown_days:
            reason = f"cooldown:{days_since}d<{cooldown_days}d"
            logger.info("[drift] should_retrain=False (%s)", reason)
            return False, [reason]

    # --- Guard: minimum new samples ---
    if n_new_samples < min_new_samples:
        reason = f"min_samples:{n_new_samples}<{min_new_samples}"
        logger.info("[drift] should_retrain=False (%s)", reason)
        return False, [reason]

    # --- Evaluate trigger signals ---
    reasons: List[str] = []

    # (a) Feature drift windows
    feat_state = _load_json(os.path.join(persist_path, "feature_drift_state.json"))
    window_history = feat_state.get("window_history", [])
    n_drifted = sum(window_history)
    window_size = feat_state.get("window_size", 10)
    if n_drifted >= drift_window_min_count:
        reasons.append(f"feature_drift_windows:{n_drifted}/{window_size}")

    # (b) ADWIN performance drift
    perf_state = _load_json(os.path.join(persist_path, "performance_drift_state.json"))
    if perf_state.get("drift_fired", False):
        reasons.append("performance_drift:adwin_fired")

    # (c) Cadence floor
    if last_retrain_str:
        last_retrain = datetime.fromisoformat(last_retrain_str)
        days_since = (now - last_retrain).days
        if days_since >= cadence_days:
            reasons.append(f"cadence_floor:{days_since}d>={cadence_days}d")
    else:
        reasons.append("cadence_floor:never_retrained")

    result = len(reasons) > 0
    logger.info(
        "[drift] should_retrain=%s reasons=%s n_new_samples=%d "
        "cooldown_ok=True min_samples_ok=True",
        result, reasons, n_new_samples,
    )
    return result, reasons
