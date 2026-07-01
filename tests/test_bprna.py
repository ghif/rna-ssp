from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rna.data.bprna import load_bprna_dataset


class TestBPRNAParser(unittest.TestCase):
    def _write_dataset(
        self, root: Path, name: str, record_id: str, fasta_body: str, bpseq_body: str
    ) -> Path:
        # Build a tiny on-disk dataset so the loader is exercised end to end.
        dataset_dir = root / name
        bpseq_dir = dataset_dir / f"{name}_BPSEQLFILES"
        bpseq_dir.mkdir(parents=True, exist_ok=True)

        (dataset_dir / f"{name}.fasta").write_text(fasta_body)
        (bpseq_dir / f"{record_id}.bpseq").write_text(bpseq_body)
        return dataset_dir

    def test_load_bprna_dataset_parses_simple_nested_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # A simple nested structure should round-trip into canonical pairs and dot-bracket.
            dataset_dir = self._write_dataset(
                root,
                "bpRNA_1m_90",
                "example",
                ">example\nGCAU\n",
                "# bpRNA File:example.bpseq\n"
                "1 G 4\n"
                "2 C 3\n"
                "3 A 2\n"
                "4 U 1\n",
            )

            examples = load_bprna_dataset(dataset_dir)

            self.assertEqual(len(examples), 1)
            example = examples[0]
            self.assertEqual(example.id, "example")
            self.assertEqual(example.sequence, "GCAU")
            self.assertEqual(set(example.pairs), {(1, 4), (2, 3)})
            self.assertEqual(example.dotbracket, "(())")

    def test_load_bprna_dataset_marks_crossing_pairs_as_non_dotbracket(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # Crossing pairs cannot be represented in plain dot-bracket, so the loader should mark that case.
            dataset_dir = self._write_dataset(
                root,
                "bpRNA_1m_90",
                "crossing",
                ">crossing\nGCAUAG\n",
                "# bpRNA File:crossing.bpseq\n"
                "1 G 5\n"
                "2 C 6\n"
                "3 A 0\n"
                "4 U 0\n"
                "5 A 1\n"
                "6 G 2\n",
            )

            examples = load_bprna_dataset(dataset_dir)

            self.assertEqual(len(examples), 1)
            example = examples[0]
            self.assertEqual(example.id, "crossing")
            self.assertEqual(set(example.pairs), {(1, 5), (2, 6)})
            self.assertIsNone(example.dotbracket)


if __name__ == "__main__":
    unittest.main()
