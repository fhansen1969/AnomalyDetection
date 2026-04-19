"""
Offline calibrator fitting — maintenance CLI.

Loads recent anomaly records with TP/FP feedback labels from storage and fits a
ScoreCalibrator per model.  Calibrators are persisted to:

    storage/calibrators/<model_name>.joblib

Feedback labels are read from each anomaly record in this priority order:
  1. metadata["label"]  — integer/bool, 1 = TP, 0 = FP
  2. status field       — literal string "tp" or "fp"

Records without a resolvable label contribute to ECDF fitting but not to the
probability calibrator (isotonic / Platt).

Usage
-----
Run from the project root (same directory that contains config/config.yaml):

    python -m anomaly_detection.calibration.fit_calibrator

Options:
    --config PATH     Path to config.yaml  (default: config/config.yaml)
    --limit N         Maximum anomaly records to load  (default: 10 000)
    --storage PATH    Override storage root directory  (default: storage)

This script is NOT run during normal API startup.
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path) as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_from_db(config: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    """Attempt to load anomaly records from PostgreSQL via StorageManager."""
    try:
        from anomaly_detection.storage.storage_manager import StorageManager

        db_cfg = config.get("database", {})
        storage = StorageManager(db_cfg)
        storage.initialize_connection_pool()
        records = storage.get_anomalies(limit=limit)
        logger.info("Loaded %d records from database", len(records))
        return records
    except Exception as exc:
        logger.warning("Could not load from database (%s); will try file fallback", exc)
        return []


def _load_from_files(storage_root: Path, limit: int) -> List[Dict[str, Any]]:
    """Load anomaly records from JSON files under storage/anomalies/."""
    anomalies_dir = storage_root / "anomalies"
    if not anomalies_dir.exists():
        logger.warning("No anomalies directory found at %s", anomalies_dir)
        return []

    files = sorted(
        anomalies_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    records: List[Dict[str, Any]] = []
    for f in files:
        if len(records) >= limit:
            break
        try:
            with open(f) as fh:
                data = json.load(fh)
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict):
                records.append(data)
        except Exception as exc:
            logger.warning("Skipping %s: %s", f.name, exc)

    logger.info("Loaded %d records from files in %s", len(records[:limit]), anomalies_dir)
    return records[:limit]


# ---------------------------------------------------------------------------
# Label extraction
# ---------------------------------------------------------------------------

def _extract_label(anomaly: Dict[str, Any]) -> Optional[int]:
    """Return 1 (TP), 0 (FP), or None (unlabeled)."""
    # Priority 1: metadata["label"]
    metadata = anomaly.get("metadata") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    if "label" in metadata:
        try:
            return int(bool(metadata["label"]))
        except (TypeError, ValueError):
            pass

    # Priority 2: status string
    status = (anomaly.get("status") or "").lower()
    if status == "tp":
        return 1
    if status == "fp":
        return 0

    return None


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _group_by_model(
    records: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Return {model_name: {scores: [...], labeled: [(score, label), ...]}}."""
    groups: Dict[str, Dict[str, Any]] = {}
    for rec in records:
        model = rec.get("model_name") or rec.get("model") or "unknown"
        raw_score = rec.get("score")
        if raw_score is None:
            continue
        score = float(raw_score)
        if model not in groups:
            groups[model] = {"scores": [], "labeled": []}
        groups[model]["scores"].append(score)
        label = _extract_label(rec)
        if label is not None:
            groups[model]["labeled"].append((score, label))
    return groups


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Fit ScoreCalibrators from stored anomaly feedback."
    )
    parser.add_argument(
        "--config", default="config/config.yaml", help="Path to config.yaml"
    )
    parser.add_argument(
        "--limit", type=int, default=10_000, help="Max anomaly records to load"
    )
    parser.add_argument(
        "--storage", default="storage", help="Storage root directory"
    )
    args = parser.parse_args(argv)

    config = _load_yaml(args.config)
    storage_root = Path(args.storage)

    cal_cfg = config.get("calibration", {})
    tier_cutoffs_override = cal_cfg.get("tier_cutoffs", {})
    calibrators_path = Path(cal_cfg.get("calibrators_path", "storage/calibrators"))

    # Load records
    logger.info("Loading anomaly records (limit=%d)…", args.limit)
    records = _load_from_db(config, args.limit)
    if not records:
        logger.info("Falling back to JSON files in %s/anomalies/", storage_root)
        records = _load_from_files(storage_root, args.limit)

    if not records:
        logger.error("No anomaly records found. Nothing to fit.")
        sys.exit(1)

    logger.info("Total records: %d", len(records))

    groups = _group_by_model(records)
    if not groups:
        logger.error("No records with a score field. Nothing to fit.")
        sys.exit(1)

    from anomaly_detection.calibration.score_calibrator import (
        DEFAULT_TIER_CUTOFFS,
        ScoreCalibrator,
    )

    tier_cutoffs = {**DEFAULT_TIER_CUTOFFS, **tier_cutoffs_override}
    calibrators_path.mkdir(parents=True, exist_ok=True)

    header = f"{'Model':<38} {'Samples':>8} {'Labeled':>8} {'TP':>5} {'Method':>10}"
    print(f"\n{header}")
    print("-" * len(header))

    for model_name, data in sorted(groups.items()):
        scores_all = np.array(data["scores"], dtype=float)
        labeled: List[Tuple[float, int]] = data["labeled"]

        cal = ScoreCalibrator(tier_cutoffs=tier_cutoffs)
        cal.fit_ecdf(scores_all)

        method = "ecdf_only"
        n_tp = 0

        if labeled:
            label_scores = np.array([x[0] for x in labeled], dtype=float)
            label_values = np.array([x[1] for x in labeled], dtype=float)
            n_tp = int(label_values.sum())
            method = cal.fit_isotonic(label_scores, label_values)

        save_path = calibrators_path / f"{model_name}.joblib"
        cal.save(str(save_path))

        print(
            f"{model_name:<38} {len(scores_all):>8} {len(labeled):>8} {n_tp:>5} {method:>10}"
        )

    print()
    logger.info("Calibrators saved to %s", calibrators_path)


if __name__ == "__main__":
    main()
