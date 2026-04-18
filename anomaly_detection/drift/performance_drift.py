"""Performance-based drift monitoring using ADWIN from river.

river is lazy-imported inside methods to avoid start-up overhead.
"""
import json
import logging
import os
import pickle
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PerformanceDriftMonitor:
    """Tracks model accuracy via a binary feedback stream and detects drift with ADWIN.

    Feed analyst TP/FP feedback: 1 = model's top anomaly confirmed TP, 0 = FP.
    ADWIN fires when the running error rate has shifted significantly.

    Usage::

        monitor = PerformanceDriftMonitor()
        monitor.update(1)   # TP confirmation
        monitor.update(0)   # FP correction
        if monitor.drift_detected:
            trigger_retrain()
    """

    def __init__(
        self,
        persist_path: str = "storage/drift",
        adwin_delta: float = 0.002,
    ):
        self._persist_path = persist_path
        self._adwin_delta = adwin_delta

        self._adwin = None  # river.drift.ADWIN — lazy-initialised
        self._drift_fired: bool = False
        self._drift_fired_at: Optional[str] = None
        self._n_samples: int = 0
        self._n_drift_events: int = 0

        self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def drift_detected(self) -> bool:
        """True if ADWIN has fired at least once since the last reset."""
        return self._drift_fired

    def update(self, value: float) -> bool:
        """Feed a new accuracy signal (1=correct, 0=incorrect).

        Returns True if drift fires on this sample.
        """
        adwin = self._get_adwin()
        adwin.update(float(value))
        self._n_samples += 1

        fired = bool(adwin.drift_detected)
        if fired:
            now = datetime.now(timezone.utc).isoformat()
            self._drift_fired = True
            self._drift_fired_at = now
            self._n_drift_events += 1
            logger.warning(
                "[drift] ADWIN fired: performance drift at sample %d "
                "(total events=%d)",
                self._n_samples, self._n_drift_events,
            )
            self._save_state()

        return fired

    def reset_drift_flag(self) -> None:
        """Clear the drift flag after a retrain has been triggered."""
        self._drift_fired = False
        self._save_state()

    def state(self) -> Dict[str, Any]:
        return {
            "drift_detected": self._drift_fired,
            "drift_fired_at": self._drift_fired_at,
            "n_samples_processed": self._n_samples,
            "n_drift_events": self._n_drift_events,
            "adwin_delta": self._adwin_delta,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_adwin(self):
        if self._adwin is None:
            try:
                from river import drift as river_drift  # noqa: PLC0415 (intentional lazy import)

                self._adwin = river_drift.ADWIN(delta=self._adwin_delta)
            except ImportError as exc:
                logger.error(
                    "[drift] river not available (%s); performance drift disabled", exc
                )
                raise
        return self._adwin

    def _save_state(self) -> None:
        try:
            os.makedirs(self._persist_path, exist_ok=True)
            adwin_path = os.path.join(self._persist_path, "performance_adwin.pkl")
            state_path = os.path.join(self._persist_path, "performance_drift_state.json")

            if self._adwin is not None:
                with open(adwin_path, "wb") as f:
                    pickle.dump(self._adwin, f)

            with open(state_path, "w") as f:
                json.dump(
                    {
                        "adwin_delta": self._adwin_delta,
                        "drift_fired": self._drift_fired,
                        "drift_fired_at": self._drift_fired_at,
                        "n_samples": self._n_samples,
                        "n_drift_events": self._n_drift_events,
                    },
                    f,
                    indent=2,
                )

        except Exception as exc:
            logger.warning("[drift] failed to save performance state: %s", exc)

    def _load_state(self) -> None:
        try:
            adwin_path = os.path.join(self._persist_path, "performance_adwin.pkl")
            state_path = os.path.join(self._persist_path, "performance_drift_state.json")

            if os.path.exists(state_path):
                with open(state_path) as f:
                    state = json.load(f)
                self._adwin_delta = state.get("adwin_delta", self._adwin_delta)
                self._drift_fired = state.get("drift_fired", False)
                self._drift_fired_at = state.get("drift_fired_at")
                self._n_samples = state.get("n_samples", 0)
                self._n_drift_events = state.get("n_drift_events", 0)

            if os.path.exists(adwin_path):
                with open(adwin_path, "rb") as f:
                    self._adwin = pickle.load(f)

        except Exception as exc:
            logger.debug("[drift] could not load performance state (ok on first run): %s", exc)
