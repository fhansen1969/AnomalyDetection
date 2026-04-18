"""
Feature attribution explainer for anomaly detection models.

Dispatches by model type:
  - IsolationForestModel  → shap.TreeExplainer (happy path)
  - AutoencoderModel      → per-feature reconstruction error (normalized)
  - EnsembleModel         → weight-merged attributions from base models
  - Everything else       → empty list (silent, never raises)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("explainer.shap")


class ShapExplainer:
    """Attach top-K feature attributions to an anomaly without touching scoring logic."""

    def explain(
        self,
        model: Any,
        feature_vector: np.ndarray,
        feature_names: List[str],
        top_k: int = 5,
    ) -> List[Tuple[str, float]]:
        """
        Return up to top_k (feature_name, contribution) pairs sorted by |contribution|.

        Never raises — unsupported model types return [].
        """
        if not feature_names or feature_vector is None or len(feature_vector) == 0:
            return []

        model_class = type(model).__name__

        try:
            if model_class == "IsolationForestModel":
                return self._explain_isolation_forest(model, feature_vector, feature_names, top_k)
            elif model_class == "AutoencoderModel":
                return self._explain_autoencoder(model, feature_vector, feature_names, top_k)
            elif model_class == "EnsembleModel":
                return self._explain_ensemble(model, feature_vector, feature_names, top_k)
            else:
                return []
        except Exception as exc:
            logger.warning("Explainer failed for %s: %s", model_class, exc)
            return []

    # ------------------------------------------------------------------
    # IsolationForest — shap.TreeExplainer
    # ------------------------------------------------------------------

    def _explain_isolation_forest(
        self,
        model: Any,
        feature_vector: np.ndarray,
        feature_names: List[str],
        top_k: int,
    ) -> List[Tuple[str, float]]:
        try:
            import shap
        except ImportError:
            logger.warning("shap package not installed; skipping IsolationForest explanation")
            return []

        sklearn_model = getattr(model, "model", None)
        if sklearn_model is None:
            return []

        explainer = shap.TreeExplainer(sklearn_model)
        fv = np.array(feature_vector, dtype=np.float64).reshape(1, -1)
        shap_values = explainer.shap_values(fv)

        # TreeExplainer on IsolationForest returns shape (1, n_features)
        if isinstance(shap_values, list):
            contributions = np.array(shap_values[0]).flatten()
        else:
            contributions = np.array(shap_values).flatten()

        return _top_k_pairs(feature_names, contributions, top_k)

    # ------------------------------------------------------------------
    # Autoencoder — per-feature reconstruction error (normalized)
    # ------------------------------------------------------------------

    def _explain_autoencoder(
        self,
        model: Any,
        feature_vector: np.ndarray,
        feature_names: List[str],
        top_k: int,
    ) -> List[Tuple[str, float]]:
        try:
            import torch
        except ImportError:
            logger.warning("torch not installed; skipping Autoencoder explanation")
            return []

        nn_model = getattr(model, "model", None)
        device = getattr(model, "device", torch.device("cpu"))
        if nn_model is None:
            return []

        fv = torch.FloatTensor(np.array(feature_vector, dtype=np.float32)).unsqueeze(0).to(device)
        nn_model.eval()
        with torch.no_grad():
            reconstructed = nn_model(fv)
            per_feature_error = ((fv - reconstructed) ** 2).squeeze(0).cpu().numpy()

        total = per_feature_error.sum()
        contributions = per_feature_error / total if total > 1e-12 else per_feature_error

        return _top_k_pairs(feature_names, contributions, top_k)

    # ------------------------------------------------------------------
    # Ensemble — weight-merged attributions from base models
    # ------------------------------------------------------------------

    def _explain_ensemble(
        self,
        model: Any,
        feature_vector: np.ndarray,
        feature_names: List[str],
        top_k: int,
    ) -> List[Tuple[str, float]]:
        base_instances: Dict[str, Any] = getattr(model, "_model_instances", {})
        models_to_use: List[str] = getattr(model, "models_to_use", list(base_instances.keys()))
        weights: Dict[str, float] = getattr(model, "weights", {})
        default_weight: float = float(getattr(model, "default_weight", 0.5))

        # Build a lookup from the caller-supplied feature_vector
        caller_values: Dict[str, float] = dict(zip(feature_names, feature_vector.tolist()))

        merged: Dict[str, float] = {}
        total_weight = 0.0

        for name in models_to_use:
            base = base_instances.get(name)
            if base is None:
                continue
            weight = float(weights.get(name, default_weight))

            # Reconstruct a feature vector aligned to THIS base model's training features
            base_feat_names: Optional[List[str]] = getattr(base, "training_feature_names", None)
            if not base_feat_names:
                continue
            base_fv = np.array(
                [caller_values.get(fn, 0.0) for fn in base_feat_names], dtype=np.float64
            )

            try:
                pairs = self.explain(base, base_fv, base_feat_names, top_k=len(base_feat_names))
            except Exception as exc:
                logger.warning("Ensemble sub-explain failed for %s: %s", name, exc)
                continue

            for feat_name, contrib in pairs:
                merged[feat_name] = merged.get(feat_name, 0.0) + weight * contrib
            total_weight += weight

        if total_weight > 0:
            merged = {k: v / total_weight for k, v in merged.items()}

        contributions = np.array(list(merged.values()))
        feat_names = list(merged.keys())
        return _top_k_pairs(feat_names, contributions, top_k)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _top_k_pairs(
    feature_names: List[str],
    contributions: np.ndarray,
    top_k: int,
) -> List[Tuple[str, float]]:
    """Zip, sort by |contribution| descending, return top_k."""
    n = min(len(feature_names), len(contributions))
    pairs = [(feature_names[i], float(contributions[i])) for i in range(n)]
    pairs.sort(key=lambda x: abs(x[1]), reverse=True)
    return pairs[:top_k]
