from __future__ import annotations

from ..data import RNAExample
from ..models.baseline import predict_rnafold


def predict_example(example: RNAExample) -> str:
    """Predict a dot-bracket structure for one loaded RNA example."""
    return predict_rnafold(example.sequence)
