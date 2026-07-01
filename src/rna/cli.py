from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .data import load_bprna_dataset
from .evaluation.metrics import pair_metrics
from .models.baseline import RNAfoldUnavailable, predict_rnafold
from .representations.pairs import dotbracket_to_pairs


def build_parser() -> argparse.ArgumentParser:
    # This CLI runs a simple RNAfold baseline over a small bpRNA slice.
    parser = argparse.ArgumentParser(description="Run a simple bpRNA RNAfold baseline.")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("rna-ssp/datasets/bpRNA_1m_90"),
        help="Path to bpRNA_1m_90 dataset directory.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of examples to evaluate.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional CSV path for per-example results.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Load examples once, then score each prediction against the known structure.
    examples = load_bprna_dataset(args.dataset_dir, limit=args.limit)

    rows = []
    aggregate = {"tp": 0.0, "fp": 0.0, "fn": 0.0}

    try:
        for example in examples:
            # Predict a structure, convert it to pairs, and compare it to the annotation.
            predicted_dotbracket = predict_rnafold(example.sequence)
            predicted_pairs = dotbracket_to_pairs(predicted_dotbracket)
            metrics = pair_metrics(example.pairs, predicted_pairs)

            for key in aggregate:
                aggregate[key] += metrics[key]

            row = {
                "id": example.id,
                "length": len(example.sequence),
                "true_pairs": len(example.pairs),
                "pred_pairs": len(predicted_pairs),
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
            }
            rows.append(row)
            print(
                f"{example.id}\tlen={row['length']}\tP={row['precision']:.3f}\t"
                f"R={row['recall']:.3f}\tF1={row['f1']:.3f}"
            )
    except RNAfoldUnavailable as exc:
        parser.error(str(exc))

    total_precision = aggregate["tp"] / (aggregate["tp"] + aggregate["fp"]) if aggregate["tp"] + aggregate["fp"] else 0.0
    total_recall = aggregate["tp"] / (aggregate["tp"] + aggregate["fn"]) if aggregate["tp"] + aggregate["fn"] else 0.0
    total_f1 = (
        2 * total_precision * total_recall / (total_precision + total_recall)
        if total_precision + total_recall
        else 0.0
    )

    print("-" * 60)
    print(f"Examples evaluated: {len(rows)}")
    print(f"Micro precision:    {total_precision:.3f}")
    print(f"Micro recall:       {total_recall:.3f}")
    print(f"Micro F1:           {total_f1:.3f}")

    if args.output is not None:
        # Optionally persist per-example results so they can be analyzed later.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved per-example results to {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
