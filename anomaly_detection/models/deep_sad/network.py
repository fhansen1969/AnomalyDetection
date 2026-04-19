"""MLP encoder for Deep SAD.

No bias terms throughout — required to prevent hypersphere collapse
(Ruff et al., ICLR 2020, Appendix A).
"""

import torch
import torch.nn as nn
from typing import List


class MLPEncoder(nn.Module):
    """Bias-free MLP that maps inputs to a low-dimensional representation."""

    def __init__(self, input_dim: int, hidden_dims: List[int], rep_dim: int):
        super().__init__()
        layers: list = []
        prev = input_dim
        for h in hidden_dims:
            layers += [
                nn.Linear(prev, h, bias=False),
                nn.BatchNorm1d(h, affine=False),
                nn.LeakyReLU(negative_slope=0.1, inplace=True),
            ]
            prev = h
        layers.append(nn.Linear(prev, rep_dim, bias=False))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)
