from __future__ import annotations

from typing import Iterable


def pair_metrics(true_pairs: Iterable[tuple[int, int]], pred_pairs: Iterable[tuple[int, int]]) -> dict[str, float]:
    # Score the prediction at the level of paired bases rather than individual nucleotides.
    true_set = set(true_pairs)
    pred_set = set(pred_pairs)

    tp = len(true_set & pred_set)
    fp = len(pred_set - true_set)
    fn = len(true_set - pred_set)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "tp": float(tp),
        "fp": float(fp),
        "fn": float(fn),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
