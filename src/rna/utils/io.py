from __future__ import annotations

from pathlib import Path


def read_fasta(path: Path) -> dict[str, str]:
    """
    Read a FASTA file and return a dictionary mapping IDs to sequences.
    The FASTA format uses lines starting with `>` to indicate sequence identifiers,
    followed by one or more lines of sequence data. This function concatenates
    sequence lines for each identifier and returns a mapping of ID to full sequence.  

    Args:
        path (Path): Path to the FASTA file.

    Returns:
        dict[str, str]: A dictionary where keys are sequence IDs and values are the corresponding sequences
    """
    # Parse a minimal FASTA file into an in-memory id -> sequence mapping.
    records: dict[str, list[str]] = {}
    current_id: str | None = None
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            current_id = line[1:].split()[0]
            records.setdefault(current_id, [])
        elif current_id is not None:
            records[current_id].append(line)
        else:
            raise ValueError(f"Invalid FASTA file {path}: sequence before header")
    return {rid: "".join(parts) for rid, parts in records.items()}


def read_bpseq(path: Path) -> tuple[str, dict[int, int]]:
    """
    Parse a BPSEQ file.

    Returns:
        sequence: RNA sequence string
        pair_map: 1-based index -> paired index (0 if unpaired)
    """
    sequence: list[str] = []
    pair_map: dict[int, int] = {}

    for raw_line in path.read_text().splitlines():
        # BPSEQ uses one-based indices and may include comment lines.
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) < 3:
            raise ValueError(f"Invalid BPSEQ line in {path}: {line}")

        index = int(parts[0])
        base = parts[1]
        paired_index = int(parts[2])

        if index != len(sequence) + 1:
            raise ValueError(
                f"Non-contiguous BPSEQ index in {path}: got {index}, expected {len(sequence) + 1}"
            )

        sequence.append(base)
        pair_map[index] = paired_index

    return "".join(sequence), pair_map
