from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def _add_src_to_path() -> None:
    """Make the package importable when the script is run directly."""

    script_dir = Path(__file__).resolve().parent
    src_dir = script_dir.parent / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


_add_src_to_path()

from rna.analysis.baseline_plots import write_error_analysis_report  # noqa: E402
from rna.data import load_bprna_dataset  # noqa: E402
from rna.evaluation.metrics import pair_metrics  # noqa: E402
from rna.models.baseline import RNAfoldUnavailable, ensure_rnafold_available, predict_rnafold  # noqa: E402
from rna.representations.pairs import dotbracket_to_pairs  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for the baseline runner."""

    repo_root = Path(__file__).resolve().parents[1]
    default_dataset_dir = repo_root / "datasets" / "bpRNA_1m_90"

    parser = argparse.ArgumentParser(description="Run a standalone bpRNA RNAfold baseline.")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=default_dataset_dir,
        help="Path to the bpRNA_1m_90 dataset directory.",
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
    parser.add_argument(
        "--plot-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory for SVG/HTML error-analysis plots. "
            "If omitted and --output is set, a sibling <output-stem>_plots directory is used."
        ),
    )
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    try:
        ensure_rnafold_available()
    except RNAfoldUnavailable as exc:
        parser.error(str(exc))

    examples = load_bprna_dataset(args.dataset_dir, limit=args.limit)

    rows: list[dict[str, object]] = []
    aggregate = {"tp": 0.0, "fp": 0.0, "fn": 0.0}

    try:
        for example in examples:
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
                "tp": int(metrics["tp"]),
                "fp": int(metrics["fp"]),
                "fn": int(metrics["fn"]),
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "pair_error": len(predicted_pairs) - len(example.pairs),
                "abs_pair_error": abs(len(predicted_pairs) - len(example.pairs)),
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
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved per-example results to {args.output}")

    plot_dir = args.plot_dir
    if plot_dir is None and args.output is not None:
        plot_dir = args.output.parent / f"{args.output.stem}_plots"

    if plot_dir is not None:
        report_path = write_error_analysis_report(
            rows,
            plot_dir,
            micro_precision=total_precision,
            micro_recall=total_recall,
            micro_f1=total_f1,
        )
        print(f"Saved error analysis plots to {report_path}")
