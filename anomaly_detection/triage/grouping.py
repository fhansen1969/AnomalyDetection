"""Entity-based alert grouping, dedup window, and optional embedding clustering."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _parse_ts(ts: Any) -> Optional[datetime]:
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def _top_severity(anomalies: List[Dict]) -> str:
    best = "low"
    best_rank = 0
    for a in anomalies:
        sev = a.get("severity", "")
        if not sev and isinstance(a.get("analysis"), dict):
            sev = a["analysis"].get("severity", "")
        rank = _SEVERITY_ORDER.get((sev or "low").lower(), 0)
        if rank > best_rank:
            best_rank = rank
            best = sev or "low"
    return best


def _entity_label(anomaly: Dict, entity_keys: List[str]) -> str:
    parts = []
    for key in entity_keys:
        val = (
            anomaly.get(key)
            or (anomaly.get("original_data") or {}).get(key)
            or (anomaly.get("details") or {}).get(key)
            or anomaly.get("location")
        )
        parts.append(str(val) if val else "unknown")
    return "|".join(parts)


def group_by_entity(
    anomalies: List[Dict[str, Any]],
    entity_keys: List[str] = None,
) -> List[Dict[str, Any]]:
    """Cluster anomalies by one or more entity fields.

    Returns list of group dicts: entity, count, first_seen, last_seen,
    top_severity, alert_ids, alerts.
    Groups are sorted: highest severity first, then by count descending.
    """
    if entity_keys is None:
        entity_keys = ["computerName"]

    buckets: Dict[str, List[Dict]] = defaultdict(list)
    for anomaly in anomalies:
        entity_id = _entity_label(anomaly, entity_keys)
        buckets[entity_id].append(anomaly)

    groups = []
    for entity_id, members in buckets.items():
        timestamps = [_parse_ts(a.get("timestamp")) for a in members]
        valid_ts = [t for t in timestamps if t]
        first_seen = min(valid_ts).isoformat() if valid_ts else None
        last_seen = max(valid_ts).isoformat() if valid_ts else None
        groups.append(
            {
                "entity": entity_id,
                "count": len(members),
                "first_seen": first_seen,
                "last_seen": last_seen,
                "top_severity": _top_severity(members),
                "alert_ids": [a.get("id") for a in members],
                "alerts": members,
            }
        )

    groups.sort(
        key=lambda g: (
            -_SEVERITY_ORDER.get(g["top_severity"].lower(), 0),
            -g["count"],
        )
    )
    return groups


def dedup_window(
    anomalies: List[Dict[str, Any]],
    window_seconds: int = 300,
    entity_keys: List[str] = None,
) -> List[Dict[str, Any]]:
    """Collapse near-duplicate alerts on the same entity+model within a time window.

    Returns one representative alert per (entity, model, window) bucket.
    The representative gets a `dup_count` field showing how many were merged.
    """
    if entity_keys is None:
        entity_keys = ["computerName"]

    _epoch_min = datetime.min.replace(tzinfo=timezone.utc)

    sorted_anomalies = sorted(
        anomalies,
        key=lambda a: _parse_ts(a.get("timestamp")) or _epoch_min,
    )

    representatives: Dict[str, Dict] = {}
    dup_counts: Dict[str, int] = {}

    for anomaly in sorted_anomalies:
        ts = _parse_ts(anomaly.get("timestamp"))
        entity = _entity_label(anomaly, entity_keys)
        model = anomaly.get("model", "unknown")
        window_slot = int(ts.timestamp() // window_seconds) if ts else 0
        bucket_key = f"{entity}::{model}::{window_slot}"

        if bucket_key not in representatives:
            representatives[bucket_key] = dict(anomaly)
            dup_counts[bucket_key] = 1
        else:
            dup_counts[bucket_key] += 1

    result = []
    for bucket_key, rep in representatives.items():
        rep = dict(rep)
        rep["dup_count"] = dup_counts[bucket_key]
        result.append(rep)

    return result


def cluster_embeddings(
    feature_vectors: List[List[float]],
    eps: float = 0.5,
    min_samples: int = 3,
) -> List[int]:
    """DBSCAN-based grouping for entity-less anomalies (optional; requires sklearn).

    Returns a list of integer cluster labels (same length as feature_vectors).
    Label -1 = noise / outlier. Returns all -1 if sklearn is unavailable.
    """
    try:
        import numpy as np
        from sklearn.cluster import DBSCAN

        if not feature_vectors:
            return []
        X = np.array(feature_vectors)
        labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(X)
        return labels.tolist()
    except ImportError:
        return [-1] * len(feature_vectors)
