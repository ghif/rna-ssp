from __future__ import annotations

import re
import shutil
import subprocess


class RNAfoldUnavailable(RuntimeError):
    """Raised when the RNAfold executable cannot be found or run."""
    pass


_DOTBRACKET_RE = re.compile(r"^[().]+$")


def _parse_rnafold_output(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    for line in lines[1:]:
        token = line.split()[0]
        if _DOTBRACKET_RE.fullmatch(token):
            return token
    raise RuntimeError(f"Unexpected RNAfold output: {output}")


def _ensure_rnafold_available() -> None:
    if shutil.which("RNAfold") is None:
        raise RNAfoldUnavailable(
            "RNAfold was not found on PATH. Install ViennaRNA and try again."
        )


def ensure_rnafold_available() -> None:
    """Raise a clear error if the RNAfold executable is not on PATH."""
    _ensure_rnafold_available()


def predict_rnafold(sequence: str) -> str:
    """
    Predict RNA secondary structure with ViennaRNA RNAfold.

    Returns the predicted dot-bracket structure.
    """
    try:
        _ensure_rnafold_available()
        # Delegate structure prediction to ViennaRNA's RNAfold command-line tool.
        proc = subprocess.run(
            ["RNAfold", "--noPS"],
            input=(sequence + "\n").encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RNAfoldUnavailable(
            "RNAfold was not found on PATH. Install ViennaRNA and try again."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace") if exc.stderr else ""
        raise RuntimeError(f"RNAfold failed: {stderr.strip()}") from exc

    return _parse_rnafold_output(proc.stdout.decode(errors="replace"))
