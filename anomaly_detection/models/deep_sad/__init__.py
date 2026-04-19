"""Vendored Deep SAD implementation (Ruff et al., ICLR 2020)."""

from anomaly_detection.models.deep_sad.network import MLPEncoder
from anomaly_detection.models.deep_sad.trainer import DeepSADTrainer

__all__ = ["MLPEncoder", "DeepSADTrainer"]
