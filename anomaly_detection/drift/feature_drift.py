"""Feature distribution drift monitoring using alibi-detect.

alibi-detect is lazy-imported inside methods to avoid the multi-second import
penalty at API start-up.
"""
import json
import logging
import os
import threading
from collections import Counter, deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import numpy as np

logger = logging.getLogger(__name__)

_GLOBAL_MONITOR: Optional["FeatureDriftMonitor"] = None
_GLOBAL_MONITOR_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reservoir_sample(matrix: np.ndarray, max_rows: int, seed: int = 42) -> np.ndarray:
    """Return at most max_rows rows via random sampling (no replacement)."""
    if len(matrix) <= max_rows:
        return matrix
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(matrix), size=max_rows, replace=False)
    return matrix[idx]


def _to_matrix(data: Union[np.ndarray, List[Dict[str, Any]]]) -> tuple:
    """Extract numeric columns from an ndarray or list-of-dicts.

    Returns (matrix: np.ndarray, col_names: list[str]).
    """
    if isinstance(data, np.ndarray):
        arr = data.astype(float)
        if arr.ndim == 1:
            arr = arr.reshape(-1, 1)
        return arr, [str(i) for i in range(arr.shape[1])]

    if not data:
        return np.empty((0, 0)), []

    import pandas as pd  # noqa: PLC0415

    df = pd.DataFrame(data)
    num_cols = list(df.select_dtypes(include=[np.number]).columns)
    if not num_cols:
        return np.empty((len(df), 0)), []
    return df[num_cols].fillna(0.0).values.astype(float), [str(c) for c in num_cols]


def _align_to_width(matrix: np.ndarray, n_cols: int) -> np.ndarray:
    """Truncate or zero-pad matrix columns to match n_cols."""
    if matrix.shape[1] == n_cols:
        return matrix
    if matrix.shape[1] > n_cols:
        return matrix[:, :n_cols]
    padding = np.zeros((len(matrix), n_cols - matrix.shape[1]))
    return np.hstack([matrix, padding])


def _compute_psi(actual: List[Any], reference: List[Any], eps: float = 1e-8) -> float:
    """Population Stability Index for two categorical distributions."""
    ref_counts = Counter(reference)
    act_counts = Counter(actual)
    categories = set(ref_counts) | set(act_counts)
    n_ref = len(reference) or 1
    n_act = len(actual) or 1
    psi = 0.0
    for cat in categories:
        p_ref = (ref_counts.get(cat, 0) + eps) / (n_ref + eps * len(categories))
        p_act = (act_counts.get(cat, 0) + eps) / (n_act + eps * len(categories))
        psi += (p_act - p_ref) * np.log(p_act / p_ref)
    return float(psi)


# ---------------------------------------------------------------------------
# Monitor class
# ---------------------------------------------------------------------------

class FeatureDriftMonitor:
    """Monitors numerical feature distributions with KSDrift or MMDDrift.

    Usage::

        monitor = FeatureDriftMonitor(persist_path="storage/drift")
        monitor.fit_reference(training_matrix)
        verdict = monitor.update(new_batch)   # list-of-dicts or ndarray
    """

    def __init__(
        self,
        persist_path: str = "storage/drift",
        method: str = "ks",
        p_value_threshold: float = 0.05,
        sliding_window_size: int = 10,
        drift_window_min_count: int = 3,
        max_reference_rows: int = 10_000,
        n_permutations: int = 200,
    ):
        self._persist_path = persist_path
        self._method = method.lower()
        self._p_value_threshold = p_value_threshold
        self._window_size = sliding_window_size
        self._min_drift_count = drift_window_min_count
        self._max_ref_rows = max_reference_rows
        self._n_permutations = n_permutations

        self._reference: Optional[np.ndarray] = None
        self._detector = None
        self._window: deque = deque(maxlen=sliding_window_size)
        self._n_windows_checked: int = 0
        self._last_drift_at: Optional[str] = None
        self._last_checked_at: Optional[str] = None

        # Categorical reference store: {feature_name: [values]}
        self._cat_reference: Dict[str, List[Any]] = {}

        self._lock = threading.Lock()
        self._load_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_reference(self, data: Union[np.ndarray, List[Dict[str, Any]]]) -> None:
        """Store the reference distribution (e.g. training set) and build the detector."""
        matrix, _ = _to_matrix(data)
        if matrix.size == 0:
            logger.warning("[drift] fit_reference: empty data, skipping")
            return

        matrix = _reservoir_sample(matrix, self._max_ref_rows)

        with self._lock:
            self._reference = matrix
            self._detector = None
            self._window.clear()
            self._n_windows_checked = 0
            self._last_drift_at = None
            self._last_checked_at = None

        self._build_detector(matrix)
        self._save_state()
        logger.info(
            "[drift] reference fitted: %d rows × %d features (method=%s)",
            matrix.shape[0], matrix.shape[1], self._method,
        )

    def update(self, batch: Union[np.ndarray, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
        """Run a drift test on a new batch.

        Returns a verdict dict or None if the monitor is not fitted / batch is empty.
        """
        with self._lock:
            if self._reference is None or self._detector is None:
                return None
            ref_n_cols = self._reference.shape[1]

        matrix, _ = _to_matrix(batch)
        if matrix.size == 0 or matrix.shape[1] == 0:
            return None

        matrix = _align_to_width(matrix, ref_n_cols)

        try:
            result = self._detector.predict(matrix)
        except Exception as exc:
            logger.warning("[drift] detector.predict failed: %s", exc)
            return None

        data = result.get("data", {})
        is_drift = bool(data.get("is_drift", 0))
        raw_pval = data.get("p_val", 1.0)
        p_value = float(np.min(raw_pval)) if hasattr(raw_pval, "__len__") else float(raw_pval)

        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._window.append(is_drift)
            self._n_windows_checked += 1
            self._last_checked_at = now
            if is_drift:
                self._last_drift_at = now
            n_drifted = sum(self._window)

        verdict = {
            "drift_detected": is_drift,
            "p_value": p_value,
            "p_value_threshold": self._p_value_threshold,
            "method": self._method,
            "n_windows_checked": self._n_windows_checked,
            "n_windows_drifted": n_drifted,
            "window_size": self._window_size,
            "checked_at": now,
        }

        logger.log(
            logging.WARNING if is_drift else logging.DEBUG,
            "[drift] verdict drift_detected=%s p_value=%.4f method=%s "
            "n_windows_drifted=%d/%d",
            is_drift, p_value, self._method, n_drifted, len(self._window),
        )

        self._save_state()
        return verdict

    def update_categorical(
        self, batch: List[Dict[str, Any]], feature_name: str
    ) -> Optional[Dict[str, Any]]:
        """Run a PSI check on a single categorical feature against stored reference."""
        if feature_name not in self._cat_reference:
            logger.debug("[drift] no categorical reference for '%s'", feature_name)
            return None

        actual = [row[feature_name] for row in batch if feature_name in row]
        if not actual:
            return None

        psi = _compute_psi(actual, self._cat_reference[feature_name])
        verdict = {
            "feature": feature_name,
            "psi": psi,
            "drift_detected": psi >= 0.25,
            "drift_moderate": psi >= 0.1,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(
            "[drift] categorical psi=%.4f feature=%s drift_detected=%s",
            psi, feature_name, verdict["drift_detected"],
        )
        return verdict

    def fit_categorical_reference(
        self, data: List[Dict[str, Any]], feature_name: str
    ) -> None:
        """Store reference values for a categorical feature."""
        values = [row[feature_name] for row in data if feature_name in row]
        self._cat_reference[feature_name] = values
        self._save_state()

    def is_fitted(self) -> bool:
        return self._reference is not None and self._detector is not None

    def n_windows_drifted(self) -> int:
        with self._lock:
            return sum(self._window)

    def state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "is_fitted": self._reference is not None,
                "reference_size": int(len(self._reference)) if self._reference is not None else 0,
                "n_features": int(self._reference.shape[1]) if self._reference is not None else 0,
                "n_windows_checked": self._n_windows_checked,
                "n_windows_drifted": sum(self._window),
                "window_size": self._window_size,
                "last_drift_detected_at": self._last_drift_at,
                "last_checked_at": self._last_checked_at,
                "method": self._method,
                "p_value_threshold": self._p_value_threshold,
            }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_detector(self, reference: np.ndarray) -> None:
        """Construct the alibi-detect drift detector from the reference matrix."""
        try:
            if self._method == "mmd":
                from alibi_detect.cd import MMDDrift  # noqa: PLC0415 (intentional lazy import)

                detector = MMDDrift(
                    reference,
                    backend="numpy",
                    p_val=self._p_value_threshold,
                    n_permutations=self._n_permutations,
                )
            else:
                from alibi_detect.cd import KSDrift  # noqa: PLC0415 (intentional lazy import)

                detector = KSDrift(reference, p_val=self._p_value_threshold)

            with self._lock:
                self._detector = detector

        except ImportError as exc:
            logger.error(
                "[drift] alibi-detect not available (%s); drift detection disabled", exc
            )
        except Exception as exc:
            logger.error("[drift] failed to build detector: %s", exc)

    def _save_state(self) -> None:
        try:
            os.makedirs(self._persist_path, exist_ok=True)
            ref_path = os.path.join(self._persist_path, "feature_reference.npy")
            state_path = os.path.join(self._persist_path, "feature_drift_state.json")

            with self._lock:
                if self._reference is not None:
                    np.save(ref_path, self._reference)
                state = {
                    "method": self._method,
                    "p_value_threshold": self._p_value_threshold,
                    "window_size": self._window_size,
                    "min_drift_count": self._min_drift_count,
                    "max_ref_rows": self._max_ref_rows,
                    "n_permutations": self._n_permutations,
                    "n_windows_checked": self._n_windows_checked,
                    "window_history": list(self._window),
                    "last_drift_at": self._last_drift_at,
                    "last_checked_at": self._last_checked_at,
                }

            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)

        except Exception as exc:
            logger.warning("[drift] failed to save state: %s", exc)

    def _load_state(self) -> None:
        try:
            ref_path = os.path.join(self._persist_path, "feature_reference.npy")
            state_path = os.path.join(self._persist_path, "feature_drift_state.json")

            if not os.path.exists(state_path):
                return

            with open(state_path) as f:
                state = json.load(f)

            self._method = state.get("method", self._method)
            self._p_value_threshold = state.get("p_value_threshold", self._p_value_threshold)
            self._window_size = state.get("window_size", self._window_size)
            self._min_drift_count = state.get("min_drift_count", self._min_drift_count)
            self._n_permutations = state.get("n_permutations", self._n_permutations)
            self._n_windows_checked = state.get("n_windows_checked", 0)
            self._last_drift_at = state.get("last_drift_at")
            self._last_checked_at = state.get("last_checked_at")
            self._window = deque(state.get("window_history", []), maxlen=self._window_size)

            if os.path.exists(ref_path):
                reference = np.load(ref_path)
                self._reference = reference
                self._build_detector(reference)

            logger.info("[drift] loaded feature drift state from %s", self._persist_path)

        except Exception as exc:
            logger.debug("[drift] could not load state (ok on first run): %s", exc)


# ---------------------------------------------------------------------------
# Global singleton factory
# ---------------------------------------------------------------------------

def get_drift_monitor(config: Optional[Dict[str, Any]] = None) -> FeatureDriftMonitor:
    """Return the process-wide FeatureDriftMonitor singleton."""
    global _GLOBAL_MONITOR
    with _GLOBAL_MONITOR_LOCK:
        if _GLOBAL_MONITOR is None:
            cfg = config or {}
            _GLOBAL_MONITOR = FeatureDriftMonitor(
                persist_path=cfg.get("persist_path", "storage/drift"),
                method=cfg.get("method", "ks"),
                p_value_threshold=cfg.get("p_value_threshold", 0.05),
                sliding_window_size=cfg.get("sliding_window_size", 10),
                drift_window_min_count=cfg.get("drift_window_min_count", 3),
                max_reference_rows=cfg.get("max_reference_rows", 10_000),
                n_permutations=cfg.get("n_permutations", 200),
            )
    return _GLOBAL_MONITOR
