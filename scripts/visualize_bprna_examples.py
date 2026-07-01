from __future__ import annotations

import argparse
import math
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path


def _add_src_to_path() -> None:
    # Make the package importable when this script is run directly from the repo.
    script_dir = Path(__file__).resolve().parent
    src_dir = script_dir.parent / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


_add_src_to_path()

from rna.data import load_bprna_dataset  # noqa: E402


@dataclass
class ViewerState:
    index: int = 0
    scale: float = 1.0
    offset_x: float = 40.0
    offset_y: float = 220.0
    dragging: bool = False


@dataclass
class DragAnchor:
    x: float = 0.0
    y: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0


def build_parser() -> argparse.ArgumentParser:
    # Keep the viewer configurable without editing the script.
    repo_root = Path(__file__).resolve().parents[1]
    default_dataset_dir = repo_root / "datasets" / "bpRNA_1m_90"

    parser = argparse.ArgumentParser(description="Visualize bpRNA examples in a small tkinter window.")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=default_dataset_dir,
        help="Path to the bpRNA_1m_90 dataset directory.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Number of examples to load into the viewer.",
    )
    return parser


def _shorten(text: str, max_len: int = 60) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _label_font_size(scale: float) -> int:
    # Keep the nucleotide row readable while still letting it scale with the view.
    return int(_clamp(round(10 * math.sqrt(scale)), 8, 18))


def _index_font_size(scale: float) -> int:
    return int(_clamp(round(7 * math.sqrt(scale)), 6, 10))


def _scale_to_fit(canvas_width: int, sequence_length: int) -> float:
    # Use a conservative default fit so long examples remain navigable without
    # shrinking the letters into unreadable noise.
    model_width = max(sequence_length - 1, 1) * 28.0
    available_width = max(canvas_width - 120, 1)
    return _clamp(available_width / model_width, 0.6, 1.6)


def _zoom_view(state: ViewerState, focus_x: float, focus_y: float, factor: float) -> None:
    old_scale = state.scale
    new_scale = _clamp(old_scale * factor, 0.35, 3.0)
    if new_scale == old_scale:
        return

    scale_ratio = new_scale / old_scale
    state.offset_x = focus_x - (focus_x - state.offset_x) * scale_ratio
    state.offset_y = focus_y - (focus_y - state.offset_y) * scale_ratio
    state.scale = new_scale


def _reset_view(state: ViewerState, canvas_width: int, example) -> None:
    scale = _scale_to_fit(max(canvas_width, 900), len(example.sequence))
    model_width = max(len(example.sequence) - 1, 1) * 28.0
    scaled_width = model_width * scale

    if scaled_width < max(canvas_width, 900) - 80:
        offset_x = (max(canvas_width, 900) - scaled_width) / 2
    else:
        offset_x = 40.0

    state.scale = scale
    state.offset_x = offset_x
    state.offset_y = 220.0 * scale + 50.0


def _model_to_canvas(x: float, y: float, state: ViewerState) -> tuple[float, float]:
    return state.offset_x + x * state.scale, state.offset_y + y * state.scale


def _draw_example(canvas: tk.Canvas, example, state: ViewerState, width: int, height: int) -> None:
    # Clear the canvas before drawing the selected record.
    canvas.delete("all")

    n = len(example.sequence)
    base_font = ("Courier", _label_font_size(state.scale))
    index_font = ("Courier", _index_font_size(state.scale))
    show_indices = n <= 120 and state.scale >= 0.8

    backbone_y = 0.0
    label_y = 34.0
    index_y = 56.0
    max_arc_height = 220.0

    canvas.create_text(
        16,
        18,
        anchor="w",
        text=f"{example.id}  length={n}  pairs={len(example.pairs)}",
        font=("Helvetica", 13, "bold"),
    )

    status = "dot-bracket available" if example.dotbracket is not None else "dot-bracket unavailable for this structure"
    canvas.create_text(16, 36, anchor="w", text=status, font=("Helvetica", 10))

    if n == 0:
        return

    x_positions = [(i - 1) * 28.0 for i in range(1, n + 1)]

    # Draw the structural arcs first so the nucleotide letters always sit on top.
    for i, j in sorted(example.pairs):
        x1 = x_positions[i - 1]
        x2 = x_positions[j - 1]
        span = abs(x2 - x1)
        arc_height = min(max_arc_height, max(28.0, span / 2.0))
        sx1, sy1 = _model_to_canvas(x1, -arc_height, state)
        sx2, sy2 = _model_to_canvas(x2, arc_height, state)
        canvas.create_arc(
            sx1,
            sy1,
            sx2,
            sy2,
            start=0,
            extent=180,
            style="arc",
            outline="#2563eb",
            width=max(1, int(round(state.scale))),
        )

    # Backbone and ticks anchor the labels.
    for i, x in enumerate(x_positions, start=1):
        sx, sy = _model_to_canvas(x, backbone_y, state)
        canvas.create_line(sx, sy - 5, sx, sy + 5, fill="#111827")
        if show_indices:
            ix, iy = _model_to_canvas(x, index_y, state)
            canvas.create_text(ix, iy, text=str(i), font=index_font, fill="#6b7280")

    # Put the nucleotide labels in their own row so they never overlap the arcs.
    for x, base in zip(x_positions, example.sequence):
        sx, sy = _model_to_canvas(x, label_y, state)
        canvas.create_text(sx, sy, text=base, font=base_font, fill="#111827")

    canvas.create_text(
        16,
        max(56, height - 30),
        anchor="w",
        text="Wheel: zoom   Drag: pan   Double-click or R: reset view",
        font=("Helvetica", 9),
        fill="#4b5563",
    )

    if example.dotbracket is not None:
        canvas.create_text(
            16,
            max(74, height - 12),
            anchor="w",
            text=f"dot-bracket: {_shorten(example.dotbracket, 120)}",
            font=("Courier", 10),
        )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    examples = load_bprna_dataset(args.dataset_dir, limit=args.limit)
    if not examples:
        raise ValueError(f"No examples found in {args.dataset_dir}")

    root = tk.Tk()
    root.title("bpRNA Example Viewer")
    root.geometry("1300x700")

    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)

    left = tk.Frame(root, padx=10, pady=10)
    left.grid(row=0, column=0, sticky="ns")

    right = tk.Frame(root, padx=10, pady=10)
    right.grid(row=0, column=1, sticky="nsew")
    right.grid_rowconfigure(0, weight=1)
    right.grid_columnconfigure(0, weight=1)

    label = tk.Label(left, text=f"{len(examples)} example(s)", anchor="w")
    label.pack(fill="x")

    listbox = tk.Listbox(left, height=28, width=32, exportselection=False)
    listbox.pack(fill="both", expand=True, pady=(8, 8))

    for ex in examples:
        listbox.insert("end", f"{ex.id}  ({len(ex.sequence)} nt)")

    detail = tk.Label(left, text="", justify="left", anchor="w", wraplength=260)
    detail.pack(fill="x")

    canvas = tk.Canvas(right, bg="white", highlightthickness=1, highlightbackground="#d1d5db")
    canvas.grid(row=0, column=0, sticky="nsew")

    state = ViewerState()
    drag_anchor = DragAnchor()

    def redraw() -> None:
        example = examples[state.index]
        canvas.update_idletasks()
        _draw_example(canvas, example, state, canvas.winfo_width() or 900, canvas.winfo_height() or 600)
        bbox = canvas.bbox("all")
        if bbox is not None:
            canvas.configure(scrollregion=(bbox[0] - 20, bbox[1] - 20, bbox[2] + 20, bbox[3] + 20))

    def show_example(index: int, reset_view: bool = True) -> None:
        index = max(0, min(index, len(examples) - 1))
        state.index = index
        state.dragging = False
        canvas.configure(cursor="")

        example = examples[index]
        detail.config(
            text=(
                f"ID: {example.id}\n"
                f"Length: {len(example.sequence)}\n"
                f"Base pairs: {len(example.pairs)}\n"
                f"Dot-bracket: {'available' if example.dotbracket is not None else 'unavailable'}\n"
                f"Sequence: {_shorten(example.sequence, 120)}"
            )
        )
        listbox.selection_clear(0, "end")
        listbox.selection_set(index)
        listbox.see(index)

        if reset_view:
            _reset_view(state, canvas.winfo_width() or 900, example)
        redraw()

    def on_select(_event: tk.Event | None = None) -> None:
        selection = listbox.curselection()
        if selection:
            show_example(selection[0], reset_view=True)

    def show_prev() -> None:
        show_example(state.index - 1, reset_view=True)

    def show_next() -> None:
        show_example(state.index + 1, reset_view=True)

    buttons = tk.Frame(left)
    buttons.pack(fill="x", pady=(8, 0))

    tk.Button(buttons, text="Prev", command=show_prev).pack(side="left", expand=True, fill="x")
    tk.Button(buttons, text="Next", command=show_next).pack(side="left", expand=True, fill="x", padx=(8, 0))

    listbox.bind("<<ListboxSelect>>", on_select)
    root.bind("<Left>", lambda _e: show_prev())
    root.bind("<Right>", lambda _e: show_next())
    root.bind("r", lambda _e: show_example(state.index, reset_view=True))
    root.bind("R", lambda _e: show_example(state.index, reset_view=True))

    def on_resize(_event: tk.Event) -> None:
        redraw()

    canvas.bind("<Configure>", on_resize)

    def on_mousewheel(event: tk.Event) -> str | None:
        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            factor = 1.1
        else:
            factor = 1 / 1.1
        _zoom_view(state, float(event.x), float(event.y), factor)
        redraw()
        return "break"

    def on_pan_start(event: tk.Event) -> None:
        state.dragging = True
        drag_anchor.x = float(event.x)
        drag_anchor.y = float(event.y)
        drag_anchor.offset_x = state.offset_x
        drag_anchor.offset_y = state.offset_y
        canvas.configure(cursor="fleur")

    def on_pan_move(event: tk.Event) -> None:
        if not state.dragging:
            return
        state.offset_x = drag_anchor.offset_x + (float(event.x) - drag_anchor.x)
        state.offset_y = drag_anchor.offset_y + (float(event.y) - drag_anchor.y)
        redraw()

    def on_pan_end(_event: tk.Event) -> None:
        state.dragging = False
        canvas.configure(cursor="")

    def on_reset_view(_event: tk.Event | None = None) -> None:
        show_example(state.index, reset_view=True)

    canvas.bind("<MouseWheel>", on_mousewheel)
    canvas.bind("<Button-4>", on_mousewheel)
    canvas.bind("<Button-5>", on_mousewheel)
    canvas.bind("<ButtonPress-1>", on_pan_start)
    canvas.bind("<B1-Motion>", on_pan_move)
    canvas.bind("<ButtonRelease-1>", on_pan_end)
    canvas.bind("<Double-Button-1>", on_reset_view)

    root.update_idletasks()
    show_example(0, reset_view=True)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
