"""Triage UI components: entity-grouped incident view, SHAP waterfall, TP/FP feedback."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Severity helpers
# ---------------------------------------------------------------------------

_SEV_CONFIG = {
    "Critical": {"emoji": "🔴", "color": "#ef4444", "badge_bg": "#fee2e2"},
    "High": {"emoji": "🟠", "color": "#f97316", "badge_bg": "#ffedd5"},
    "Medium": {"emoji": "🟡", "color": "#f59e0b", "badge_bg": "#fef3c7"},
    "Low": {"emoji": "🟢", "color": "#10b981", "badge_bg": "#d1fae5"},
}
_SEV_DEFAULT = {"emoji": "⚪", "color": "#6b7280", "badge_bg": "#f3f4f6"}


def _sev_cfg(severity: str) -> Dict:
    return _SEV_CONFIG.get(severity or "Unknown", _SEV_DEFAULT)


def severity_badge(severity: str) -> str:
    """Return an HTML severity-tier badge string."""
    cfg = _sev_cfg(severity)
    return (
        f"<span style='background:{cfg['badge_bg']};color:{cfg['color']};"
        f"font-weight:600;padding:2px 8px;border-radius:12px;font-size:0.8rem;'>"
        f"{cfg['emoji']} {severity}</span>"
    )


def _effective_severity(anomaly: Dict) -> str:
    """Prefer severity_tier (Wave-1 calibration) over raw severity field."""
    return (
        anomaly.get("severity_tier")
        or anomaly.get("severity")
        or (anomaly.get("analysis") or {}).get("severity")
        or "Unknown"
    )


# ---------------------------------------------------------------------------
# Why-it-fired waterfall chart (top_features / SHAP)
# ---------------------------------------------------------------------------

def render_why_fired(anomaly: Dict) -> None:
    """Render inline SHAP-style waterfall for top_features if present."""
    top_features = anomaly.get("top_features")
    if not top_features:
        # Fall back to plain features list
        features = anomaly.get("features", [])
        if features:
            st.caption("**Triggering features** (no SHAP weights available)")
            for f in features[:8]:
                if isinstance(f, str):
                    st.markdown(f"• {f}")
                elif isinstance(f, dict):
                    for k, v in f.items():
                        st.markdown(f"• **{k}**: {v}")
        return

    # Expect top_features as list of {name, value} or list of [name, value]
    names, values = [], []
    for item in top_features[:10]:
        if isinstance(item, dict):
            names.append(str(item.get("name", "?")))
            values.append(float(item.get("value", 0)))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            names.append(str(item[0]))
            values.append(float(item[1]))

    if not names:
        return

    colors = ["#ef4444" if v > 0 else "#10b981" for v in values]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker_color=colors,
            text=[f"{v:+.3f}" for v in values],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="Why it fired (SHAP contributions)",
        height=max(200, len(names) * 30 + 80),
        margin=dict(l=0, r=20, t=30, b=20),
        xaxis_title="Feature contribution",
        yaxis=dict(autorange="reversed"),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Inline TP/FP feedback panel
# ---------------------------------------------------------------------------

_DEFAULT_REASON_CODES = [
    "true_threat",
    "expected_behavior",
    "stale_data",
    "known_false_positive",
    "investigating",
]


def _fetch_reason_codes(api_url: str) -> List[str]:
    try:
        resp = requests.get(f"{api_url}/triage/reason-codes", timeout=3)
        if resp.status_code == 200:
            return resp.json().get("reason_codes", _DEFAULT_REASON_CODES)
    except Exception:
        pass
    return _DEFAULT_REASON_CODES


def render_tp_fp_feedback(anomaly: Dict, api_url: str) -> None:
    """Render inline TP/FP buttons with reason code dropdown."""
    anomaly_id = anomaly.get("id", "")
    if not anomaly_id:
        return

    key_prefix = f"fb_{anomaly_id}"
    cache_key = "triage_reason_codes"

    if cache_key not in st.session_state:
        st.session_state[cache_key] = _fetch_reason_codes(api_url)
    reason_codes = st.session_state[cache_key]

    col_tp, col_fp, col_reason, col_notes = st.columns([1, 1, 2, 3])

    with col_tp:
        tp_clicked = st.button("✅ TP", key=f"{key_prefix}_tp", help="True Positive — confirm this is a real threat")
    with col_fp:
        fp_clicked = st.button("❌ FP", key=f"{key_prefix}_fp", help="False Positive — mark as noise")
    with col_reason:
        reason = st.selectbox(
            "Reason",
            reason_codes,
            key=f"{key_prefix}_reason",
            label_visibility="collapsed",
        )
    with col_notes:
        notes = st.text_input(
            "Notes",
            key=f"{key_prefix}_notes",
            placeholder="Optional analyst notes…",
            label_visibility="collapsed",
        )

    verdict = None
    if tp_clicked:
        verdict = "TP"
    elif fp_clicked:
        verdict = "FP"

    if verdict:
        try:
            resp = requests.post(
                f"{api_url}/anomalies/{anomaly_id}/feedback",
                json={"status": verdict, "reason_code": reason, "notes": notes},
                timeout=5,
            )
            if resp.status_code == 200:
                st.success(f"Feedback saved: {verdict} / {reason}")
                # Invalidate cached anomaly list so group view refreshes
                st.session_state.pop("anomalies_data", None)
            else:
                st.error(f"API error {resp.status_code}: {resp.text[:120]}")
        except Exception as exc:
            st.error(f"Could not reach API: {exc}")


# ---------------------------------------------------------------------------
# Group view — main entry point
# ---------------------------------------------------------------------------

def _auto_close_stale(anomalies: List[Dict], auto_close_days: int, api_url: str) -> int:
    """Auto-close low/medium alerts older than auto_close_days with no interaction."""
    if auto_close_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc).timestamp() - auto_close_days * 86400
    closed = 0
    for a in anomalies:
        if a.get("status") not in ("new",):
            continue
        sev = _effective_severity(a).lower()
        if sev not in ("low",):
            continue
        ts_str = a.get("updated_at") or a.get("timestamp")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts.timestamp() < cutoff:
                requests.post(
                    f"{api_url}/anomalies/{a['id']}/feedback",
                    json={
                        "status": "FP",
                        "reason_code": "stale_data",
                        "notes": f"Auto-closed after {auto_close_days}d inactivity",
                    },
                    timeout=3,
                )
                closed += 1
        except Exception:
            pass
    return closed


def render_group_view(
    anomalies: List[Dict[str, Any]],
    api_url: str,
    entity_keys: Optional[List[str]] = None,
    dedup_window_seconds: int = 300,
    auto_close_days: int = 7,
    auto_close_enabled: bool = False,
) -> None:
    """Render entity-grouped incident view with SHAP panel and inline TP/FP feedback."""
    import sys, os
    # Make sure the project root is on sys.path so the triage module is importable
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from anomaly_detection.triage.grouping import group_by_entity, dedup_window

    if entity_keys is None:
        entity_keys = ["computerName"]

    if not anomalies:
        st.info("No anomalies to display in group view.")
        return

    # Optional auto-close
    if auto_close_enabled and auto_close_days > 0:
        closed = _auto_close_stale(anomalies, auto_close_days, api_url)
        if closed:
            st.info(f"Auto-closed {closed} stale low-severity alert(s) older than {auto_close_days}d.")

    # Dedup then group
    deduped = dedup_window(anomalies, window_seconds=dedup_window_seconds, entity_keys=entity_keys)
    groups = group_by_entity(deduped, entity_keys=entity_keys)

    st.markdown(
        f"**{len(groups)} entities** · {len(deduped)} alerts after dedup "
        f"(window {dedup_window_seconds}s) · {len(anomalies)} raw"
    )
    st.divider()

    for idx, group in enumerate(groups):
        entity = group["entity"]
        count = group["count"]
        top_sev = group.get("top_severity", "Unknown")
        first_seen = group.get("first_seen", "?")
        last_seen = group.get("last_seen", "?")

        cfg = _sev_cfg(top_sev)
        header_html = (
            f"{cfg['emoji']} **{entity}** — "
            f"{severity_badge(top_sev)} "
            f"&nbsp;{count} alert{'s' if count != 1 else ''} &nbsp;·&nbsp; "
            f"first {_fmt_ts(first_seen)} &nbsp;·&nbsp; last {_fmt_ts(last_seen)}"
        )

        with st.expander(f"{cfg['emoji']} {entity}  ·  {top_sev}  ·  {count} alert(s)", expanded=(idx == 0)):
            st.markdown(header_html, unsafe_allow_html=True)
            st.divider()

            for alert in group.get("alerts", []):
                _render_alert_row(alert, api_url)
                st.divider()


def _fmt_ts(ts_str: Optional[str]) -> str:
    if not ts_str:
        return "?"
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d %H:%M")
    except Exception:
        return ts_str[:16]


def _render_alert_row(alert: Dict, api_url: str) -> None:
    """Render one alert inside a group with severity badge, SHAP panel, and TP/FP buttons."""
    alert_id = alert.get("id", "?")[:12]
    score = float(alert.get("score", 0))
    model = alert.get("model", "?")
    status = alert.get("status", "new")
    sev = _effective_severity(alert)
    dup_count = alert.get("dup_count", 1)

    col_badge, col_info, col_score = st.columns([2, 5, 1])
    with col_badge:
        st.markdown(severity_badge(sev), unsafe_allow_html=True)
        if dup_count > 1:
            st.caption(f"×{dup_count} deduped")
    with col_info:
        st.markdown(f"`{alert_id}` · {model} · status: **{status}**")
        loc = alert.get("location") or alert.get("src_ip")
        if loc:
            st.caption(f"Location: {loc}")
    with col_score:
        st.metric("Score", f"{score:.3f}")

    # Why-it-fired panel (SHAP) — only shown if data is present
    render_why_fired(alert)

    # Inline TP/FP feedback
    render_tp_fp_feedback(alert, api_url)
