from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _add_src_to_path() -> None:
    # Make the package importable when this script is run directly from the repo.
    script_dir = Path(__file__).resolve().parent
    src_dir = script_dir.parent / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


_add_src_to_path()

from rna.data import load_bprna_dataset  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    # Keep the script configurable from the command line without requiring edits.
    repo_root = Path(__file__).resolve().parents[1]
    default_dataset_dir = repo_root / "datasets" / "bpRNA_1m_90"

    parser = argparse.ArgumentParser(
        description="Load a small bpRNA subset and print example summaries."
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=default_dataset_dir,
        help="Path to the bpRNA_1m_90 dataset directory.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of examples to load and print.",
    )
    return parser


def _format_structure_preview(dotbracket: str | None, length: int, preview_len: int = 80) -> str:
    if dotbracket is None:
        return "None"
    if length <= preview_len:
        return dotbracket
    return f"{dotbracket[:preview_len]}..."


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()

    # Load a small slice of the dataset so the output stays readable in a shell session.
    examples = load_bprna_dataset(args.dataset_dir, limit=args.limit)

    print(f"Loaded {len(examples)} example(s) from {args.dataset_dir}")
    print("-" * 80)
    for example in examples:
        # Show a compact summary of each record rather than dumping the full sequence.
        structure_preview = _format_structure_preview(example.dotbracket, len(example.sequence))
        sequence_preview = example.sequence[:80] + ("..." if len(example.sequence) > 80 else "")

        print(f"ID:              {example.id}")
        print(f"Length:          {len(example.sequence)}")
        print(f"Base pairs:      {len(example.pairs)}")
        print(f"Dot-bracket:     {'available' if example.dotbracket is not None else 'None'}")
        print(f"Sequence preview: {sequence_preview}")
        print(f"Structure:       {structure_preview}")
        print("-" * 80)
