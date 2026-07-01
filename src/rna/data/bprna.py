from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from ..representations.pairs import bpseq_map_to_pairs, pairs_to_dotbracket
from ..utils.io import read_bpseq, read_fasta


@dataclass(frozen=True)
class RNAExample:
    """One bpRNA record with the sequence, paired bases, and source path."""

    id: str
    sequence: str
    pairs: frozenset[tuple[int, int]]
    dotbracket: str | None
    source_path: Path


def load_bprna_dataset(dataset_dir: str | Path, limit: int | None = None) -> list[RNAExample]:
    """
    Load the bpRNA_1m_90 dataset as aligned sequence/structure examples.

    The loader matches FASTA headers to BPSEQ filenames by shared identifier.
    """
    dataset_dir = Path(dataset_dir)
    # The dataset stores sequence and structure in separate files, so we read both views.
    fasta_path = dataset_dir / "bpRNA_1m_90.fasta"
    bpseq_dir = dataset_dir / "bpRNA_1m_90_BPSEQLFILES"

    if not fasta_path.exists():
        raise FileNotFoundError(f"Missing FASTA file: {fasta_path}")
    if not bpseq_dir.exists():
        raise FileNotFoundError(f"Missing BPSEQ directory: {bpseq_dir}")

    fasta_records = read_fasta(fasta_path)
    bpseq_files = sorted(bpseq_dir.glob("*.bpseq"))

    examples: list[RNAExample] = []
    for bpseq_path in bpseq_files:
        # Match each BPSEQ file to the FASTA record with the same identifier.
        record_id = bpseq_path.stem
        if record_id not in fasta_records:
            continue

        fasta_sequence = fasta_records[record_id]
        bpseq_sequence, pair_map = read_bpseq(bpseq_path)
        if fasta_sequence != bpseq_sequence:
            raise ValueError(
                f"Sequence mismatch for {record_id}: FASTA length {len(fasta_sequence)} "
                f"!= BPSEQ length {len(bpseq_sequence)}"
            )

        pairs = bpseq_map_to_pairs(pair_map)
        try:
            # Some structures contain pseudoknots, which plain dot-bracket cannot encode.
            dotbracket = pairs_to_dotbracket(pairs, len(fasta_sequence))
        except ValueError:
            dotbracket = None
        examples.append(
            RNAExample(
                id=record_id,
                sequence=fasta_sequence,
                pairs=frozenset(pairs),
                dotbracket=dotbracket,
                source_path=bpseq_path,
            )
        )

        if limit is not None and len(examples) >= limit:
            # Stop early when the caller only wants a small sample.
            break

    if not examples:
        raise ValueError(f"No aligned bpRNA examples found in {dataset_dir}")

    return examples


def iter_example_summaries(examples: Iterable[RNAExample]) -> Iterator[str]:
    # Yield a compact, tab-separated summary for each example.
    for ex in examples:
        yield f"{ex.id}\tlen={len(ex.sequence)}\tpairs={len(ex.pairs)}"
