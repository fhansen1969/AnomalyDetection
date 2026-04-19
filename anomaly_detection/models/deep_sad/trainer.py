"""Deep SAD training loop (Ruff et al., ICLR 2020).

Loss per sample:
  labeled normal   (y =  1): ||φ(x) - c||²
  unlabeled        (y =  0): ||φ(x) - c||²   (treats as normal → Deep SVDD mode)
  labeled anomaly  (y = -1): -(||φ(x) - c||² + ε)⁻¹
"""

import logging
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class DeepSADTrainer:
    """Encapsulates center estimation, training, and scoring for Deep SAD."""

    def __init__(
        self,
        model: nn.Module,
        device: torch.device,
        lr: float = 1e-3,
        n_epochs: int = 50,
        batch_size: int = 64,
        weight_decay: float = 1e-6,
        eps: float = 1e-6,
    ):
        self.model = model.to(device)
        self.device = device
        self.lr = lr
        self.n_epochs = n_epochs
        self.batch_size = batch_size
        self.weight_decay = weight_decay
        self.eps = eps
        self.center: Optional[torch.Tensor] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
    ) -> None:
        """Train Deep SAD.

        Args:
            X: Feature matrix (n_samples, n_features).
            y: Label vector; 1=normal, -1=anomaly, 0/None=unlabeled.
               Pass None to train in unsupervised mode (Deep SVDD).
        """
        X_t = torch.tensor(X, dtype=torch.float32)
        if y is None:
            y_t = torch.zeros(len(X), dtype=torch.long)
        else:
            y_t = torch.tensor(y, dtype=torch.long)

        if self.center is None:
            self.center = self._init_center(X_t)

        optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.lr,
            weight_decay=self.weight_decay,
        )

        n = len(X_t)
        self.model.train()
        for epoch in range(self.n_epochs):
            perm = torch.randperm(n)
            epoch_loss = 0.0
            n_batches = 0
            for start in range(0, n, self.batch_size):
                idx = perm[start : start + self.batch_size]
                xb = X_t[idx].to(self.device)
                yb = y_t[idx].to(self.device)

                optimizer.zero_grad()
                z = self.model(xb)
                dist = ((z - self.center) ** 2).sum(dim=1)
                loss = self._sad_loss(dist, yb)
                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                n_batches += 1

            if (epoch + 1) % max(1, self.n_epochs // 5) == 0:
                logger.debug(
                    "DeepSAD epoch %d/%d  loss=%.4f",
                    epoch + 1,
                    self.n_epochs,
                    epoch_loss / max(n_batches, 1),
                )

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """Return distance-from-center scores (higher = more anomalous)."""
        if self.center is None:
            raise RuntimeError("Model not fitted. Call fit() first.")
        X_t = torch.tensor(X, dtype=torch.float32)
        scores = []
        self.model.eval()
        with torch.no_grad():
            for start in range(0, len(X_t), self.batch_size):
                xb = X_t[start : start + self.batch_size].to(self.device)
                z = self.model(xb)
                dist = ((z - self.center) ** 2).sum(dim=1)
                scores.append(dist.cpu().numpy())
        return np.concatenate(scores)

    def state_dict(self) -> dict:
        return {
            "model": self.model.state_dict(),
            "center": self.center.cpu() if self.center is not None else None,
        }

    def load_state_dict(self, state: dict) -> None:
        self.model.load_state_dict(state["model"])
        if state["center"] is not None:
            self.center = state["center"].to(self.device)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_center(self, X_t: torch.Tensor, min_abs: float = 0.01) -> torch.Tensor:
        """Estimate hypersphere center c = mean of encoder outputs."""
        self.model.eval()
        parts = []
        with torch.no_grad():
            for start in range(0, len(X_t), self.batch_size):
                xb = X_t[start : start + self.batch_size].to(self.device)
                parts.append(self.model(xb))
        c = torch.cat(parts, dim=0).mean(dim=0)
        # Push near-zero dims away from 0 to avoid degenerate hypersphere
        c = torch.where(c.abs() < min_abs, torch.full_like(c, min_abs) * c.sign().masked_fill(c == 0, 1.0), c)
        return c.detach()

    def _sad_loss(self, dist: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """Compute per-sample Deep SAD loss and return mean."""
        normal_mask = y >= 0          # unlabeled or labeled normal
        anomaly_mask = y < 0          # labeled anomaly

        loss_normal = dist[normal_mask].sum() if normal_mask.any() else dist.new_zeros(1).squeeze()
        loss_anomaly = (
            -(dist[anomaly_mask] + self.eps).reciprocal().sum()
            if anomaly_mask.any()
            else dist.new_zeros(1).squeeze()
        )
        return (loss_normal + loss_anomaly) / len(dist)
