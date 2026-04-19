"""
Active Anomaly Discovery (AAD) core algorithm — Das et al., ICDM 2016.

Vendored implementation of tree-weight optimization for IsolationForest.
pyaad / ad_examples is not reliably available on PyPI, so the core math
(about 80 lines) is reproduced here from the paper.

Key idea: each tree in the forest gets a learned weight w_t.  Given
analyst TP/FP labels, gradient descent on a hinge loss pulls anomaly
scores in the correct direction while keeping weights on the probability
simplex (w >= 0, sum(w) = 1).

Reference:
    "Incorporating Expert Feedback into Active Anomaly Discovery"
    Shubhomoy Das, Weng-Keen Wong, Thomas Dietterich, Alan Fern,
    Andrew Emmott. ICDM 2016.
"""

import numpy as np
from typing import Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(n: int) -> float:
    """Expected path length for an unsuccessful search in a BST of size n."""
    if n <= 1:
        return 0.0
    euler_mascheroni = 0.5772156649015328
    H = np.log(n - 1) + euler_mascheroni
    return 2.0 * H - 2.0 * (n - 1) / n


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_tree_scores(iforest, X: np.ndarray) -> np.ndarray:
    """
    Compute the per-tree anomaly score matrix (the phi / feature map).

    For each tree t and sample x the score is:
        phi[x, t] = 2 ** (- path_length(x, t) / c(max_samples))

    Shorter isolation path -> higher score -> more anomalous.

    Args:
        iforest: Fitted sklearn IsolationForest.
        X:       (n_samples, n_features) float array.

    Returns:
        phi: (n_samples, n_trees) — values in (0, 1], higher = more anomalous.
    """
    n_samples = X.shape[0]
    n_trees = len(iforest.estimators_)
    c = _c(int(iforest.max_samples_))

    phi = np.zeros((n_samples, n_trees), dtype=np.float64)

    for t, tree in enumerate(iforest.estimators_):
        # decision_path returns a sparse (n_samples, n_nodes) indicator matrix
        node_indicator = tree.decision_path(X)
        path_lengths = np.asarray(node_indicator.sum(axis=1)).ravel().astype(np.float64)

        if c > 0.0:
            phi[:, t] = np.power(2.0, -path_lengths / c)
        else:
            phi[:, t] = 0.5

    return phi


def fit_aad_weights(
    phi: np.ndarray,
    labels: np.ndarray,
    labeled_mask: np.ndarray,
    n_iter: int = 200,
    lr: float = 0.01,
    C: float = 1.0,
    tau: Optional[float] = None,
) -> np.ndarray:
    """
    Learn per-tree weights via projected gradient descent on hinge loss.

    For labeled TP samples (label=1) we want  w·phi(x) >= tau.
    For labeled FP samples (label=0) we want  w·phi(x) <  tau.

    The loss is:
        L(w) = (lambda/2)||w||^2 + C * sum_i max(0, -y_i*(w·phi_i - tau))

    where y_i ∈ {+1, -1} (FP 0 is converted to -1) and
    lambda = 1 / (C * n_labeled).

    After each gradient step weights are projected onto the simplex:
        w >= 0  and  sum(w) = 1.

    Args:
        phi:          (n_samples, n_trees)
        labels:       (n_samples,) — 1=TP, 0=FP, np.nan=unlabeled
        labeled_mask: (n_samples,) boolean
        n_iter:       gradient steps
        lr:           learning rate
        C:            hinge loss regularization coefficient
        tau:          decision threshold (defaults to mean score of labeled set)

    Returns:
        weights: (n_trees,) non-negative, sums to 1
    """
    n_trees = phi.shape[1]
    labeled_idx = np.where(labeled_mask)[0]

    if len(labeled_idx) == 0:
        return np.ones(n_trees, dtype=np.float64) / n_trees

    phi_labeled = phi[labeled_idx]                                   # (n_lab, T)
    # Convert 0 -> -1 for SVM-style margin
    y = np.where(labels[labeled_idx] == 1, 1.0, -1.0)               # (n_lab,)

    w = np.ones(n_trees, dtype=np.float64) / n_trees

    if tau is None:
        # Mean score of labeled samples under uniform weights
        tau = float((phi_labeled @ w).mean())

    lambda_reg = 1.0 / (C * max(len(labeled_idx), 1))
    best_w = w.copy()
    best_loss = float("inf")

    for _ in range(n_iter):
        scores = phi_labeled @ w                                      # (n_lab,)
        margins = y * (scores - tau)
        violated = margins < 0

        grad = lambda_reg * w
        if violated.any():
            # Gradient of hinge loss wrt w:  -C * mean_i [ y_i * phi_i ]
            grad -= C * (y[violated, None] * phi_labeled[violated]).mean(axis=0)

        w = w - lr * grad

        # Project onto the probability simplex
        w = np.maximum(0.0, w)
        w_sum = w.sum()
        if w_sum > 1e-12:
            w /= w_sum
        else:
            w = np.ones(n_trees, dtype=np.float64) / n_trees

        loss = float(np.maximum(0.0, -margins).sum())
        if loss < best_loss:
            best_loss = loss
            best_w = w.copy()

    return best_w
