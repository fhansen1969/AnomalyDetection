#!/usr/bin/env python3
"""Periodic drift-check CLI — intended to run as a cron job or k8s CronJob.

Examples::

    python -m anomaly_detection.drift.check_and_retrain
    python -m anomaly_detection.drift.check_and_retrain --config config/config.yaml
    python -m anomaly_detection.drift.check_and_retrain --dry-run
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timezone

# Ensure project root on path when executed directly
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

logger = logging.getLogger("drift-check")


def _load_drift_config(config_path: str = "config/config.yaml") -> dict:
    """Load the drift: section from config.yaml; return {} on failure."""
    try:
        import yaml  # noqa: PLC0415

        with open(config_path) as f:
            full = yaml.safe_load(f)
        return full.get("drift", {})
    except Exception as exc:
        logger.warning("[drift-check] could not load config (%s); using defaults", exc)
        return {}


def _run_retrain_pipeline() -> bool:
    """Invoke the retraining pipeline.

    Wire in your actual entrypoint here, e.g.::

        from pipelines.train import run_full_retrain
        run_full_retrain()

    Returns True on success.
    """
    logger.info("[drift-check] RETRAIN TRIGGERED — invoking retraining pipeline (stub)")
    # TODO: replace stub with actual pipeline call
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Drift check and conditional retraining trigger"
    )
    parser.add_argument(
        "--config", default="config/config.yaml", help="Path to config.yaml"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate drift but do not trigger retraining",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    run_ts = datetime.now(timezone.utc).isoformat()
    logger.info("[drift-check] starting at %s", run_ts)

    cfg = _load_drift_config(args.config)
    feat_cfg = cfg.get("feature_drift", {})
    perf_cfg = cfg.get("performance_drift", {})
    trig_cfg = cfg.get("trigger", {})

    persist_path: str = feat_cfg.get("persist_path", "storage/drift")
    cooldown_days: int = trig_cfg.get("cooldown_days", 7)
    min_new_samples: int = trig_cfg.get("min_new_samples", 500)
    cadence_days: int = trig_cfg.get("cadence_days", 30)
    drift_window_min: int = feat_cfg.get("drift_window_min_count", 3)

    from anomaly_detection.drift.feature_drift import get_drift_monitor  # noqa: PLC0415
    from anomaly_detection.drift.performance_drift import PerformanceDriftMonitor  # noqa: PLC0415
    from anomaly_detection.drift.trigger import (  # noqa: PLC0415
        mark_retrain_complete,
        should_retrain,
    )

    feat_monitor = get_drift_monitor(feat_cfg)
    feat_state = feat_monitor.state()

    perf_monitor = PerformanceDriftMonitor(
        persist_path=persist_path,
        adwin_delta=perf_cfg.get("adwin_delta", 0.002),
    )
    perf_state = perf_monitor.state()

    retrain, reasons = should_retrain(
        persist_path=persist_path,
        cooldown_days=cooldown_days,
        min_new_samples=min_new_samples,
        cadence_days=cadence_days,
        drift_window_min_count=drift_window_min,
    )

    # Emit a structured decision log line for every run
    logger.info(
        "[drift-check] decision: should_retrain=%s reasons=%s "
        "feat_windows_drifted=%d/%d perf_drift_fired=%s "
        "feat_is_fitted=%s dry_run=%s",
        retrain,
        reasons,
        feat_state.get("n_windows_drifted", 0),
        feat_state.get("window_size", 10),
        perf_state.get("drift_detected", False),
        feat_state.get("is_fitted", False),
        args.dry_run,
    )

    if retrain and not args.dry_run:
        success = _run_retrain_pipeline()
        if success:
            mark_retrain_complete(persist_path=persist_path)
            perf_monitor.reset_drift_flag()
            logger.info("[drift-check] retrain triggered and state counters reset")
        else:
            logger.error("[drift-check] retraining pipeline failed")
            sys.exit(1)
    elif retrain and args.dry_run:
        logger.info("[drift-check] dry-run: would have triggered retrain, reasons=%s", reasons)
    else:
        logger.info("[drift-check] no retrain needed")


if __name__ == "__main__":
    main()
