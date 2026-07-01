from __future__ import annotations

from typing import Iterable


def bpseq_map_to_pairs(pair_map: dict[int, int]) -> set[tuple[int, int]]:
    """Convert a BPSEQ partner map into canonical `(i, j)` base-pair tuples."""
    pairs: set[tuple[int, int]] = set()
    for i, j in pair_map.items():
        if j > i:
            pairs.add((i, j))
    return pairs


def pairs_to_dotbracket(pairs: Iterable[tuple[int, int]], length: int) -> str:
    # Validate the pairing geometry before emitting a plain dot-bracket string.
    pair_list = sorted(set(pairs))
    for idx, (i, j) in enumerate(pair_list):
        if not (1 <= i < j <= length):
            raise ValueError(f"Invalid pair {(i, j)} for length {length}")

        for k, l in pair_list[idx + 1 :]:
            if i < k < j < l or k < i < l < j:
                raise ValueError(
                    "Pairs contain a crossing/pseudoknot and cannot be represented in plain dot-bracket"
                )

    chars = ["."] * length
    for i, j in pair_list:
        chars[i - 1] = "("
        chars[j - 1] = ")"
    return "".join(chars)


def dotbracket_to_pairs(dotbracket: str) -> set[tuple[int, int]]:
    # Recover a pair set from a dot-bracket string by matching opening and closing brackets.
    stack: list[int] = []
    pairs: set[tuple[int, int]] = set()
    for idx, ch in enumerate(dotbracket, start=1):
        if ch == "(":
            stack.append(idx)
        elif ch == ")":
            if not stack:
                continue
            i = stack.pop()
            pairs.add((i, idx))
    return pairs
