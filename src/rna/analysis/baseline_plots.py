from __future__ import annotations

import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from xml.sax.saxutils import escape


@dataclass(frozen=True)
class PlotFrame:
    """Describe the drawing area for the SVG-based diagnostics."""

    width: int = 960
    height: int = 640
    left: int = 90
    right: int = 30
    top: int = 60
    bottom: int = 80

    @property
    def plot_width(self) -> int:
        return self.width - self.left - self.right

    @property
    def plot_height(self) -> int:
        return self.height - self.top - self.bottom

    def x(self, value: float, xmin: float, xmax: float) -> float:
        if xmax <= xmin:
            return self.left + self.plot_width / 2
        return self.left + (value - xmin) * self.plot_width / (xmax - xmin)

    def y(self, value: float, ymin: float, ymax: float) -> float:
        if ymax <= ymin:
            return self.top + self.plot_height / 2
        return self.top + self.plot_height - (value - ymin) * self.plot_height / (ymax - ymin)


@dataclass(frozen=True)
class ChartSpec:
    """Describe one cartesian chart in a way that keeps plot code concise."""

    title: str
    x_label: str
    y_label: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float


def _svg_rect(x: float, y: float, width: float, height: float, fill: str, stroke: str = "none", opacity: float = 1.0) -> str:
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        f'fill="{fill}" stroke="{stroke}" fill-opacity="{opacity:.3f}" />'
    )


def _svg_line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    stroke: str,
    stroke_width: float = 1.5,
    opacity: float = 1.0,
    dasharray: str | None = None,
) -> str:
    dash_attr = f' stroke-dasharray="{dasharray}"' if dasharray else ""
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{stroke}" stroke-width="{stroke_width:.2f}" stroke-opacity="{opacity:.3f}"{dash_attr} />'
    )


def _svg_circle(x: float, y: float, radius: float, fill: str, stroke: str = "none", opacity: float = 1.0) -> str:
    return (
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" '
        f'fill="{fill}" stroke="{stroke}" fill-opacity="{opacity:.3f}" />'
    )


def _svg_text(
    x: float,
    y: float,
    text: str,
    *,
    size: int = 14,
    anchor: str = "middle",
    fill: str = "#1f2937",
    weight: str = "normal",
    rotate: float | None = None,
) -> str:
    transform = f' transform="rotate({rotate:.2f} {x:.2f} {y:.2f})"' if rotate is not None else ""
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
        f'fill="{fill}"{transform}>{escape(text)}</text>'
    )


def _svg_polyline(points: list[tuple[float, float]], stroke: str, stroke_width: float = 2.0, opacity: float = 1.0) -> str:
    point_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return (
        f'<polyline points="{point_str}" fill="none" stroke="{stroke}" '
        f'stroke-width="{stroke_width:.2f}" stroke-opacity="{opacity:.3f}" />'
    )


def _svg_header(title: str, width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">',
        "<style>",
        "  .axis { stroke: #374151; stroke-width: 1.3; }",
        "  .grid { stroke: #d1d5db; stroke-width: 1; }",
        "  .tick { fill: #4b5563; font-family: Arial, Helvetica, sans-serif; font-size: 12px; }",
        "  .title { fill: #111827; font-family: Arial, Helvetica, sans-serif; font-size: 20px; font-weight: 700; }",
        "  .subtitle { fill: #4b5563; font-family: Arial, Helvetica, sans-serif; font-size: 12px; }",
        "  .legend { fill: #111827; font-family: Arial, Helvetica, sans-serif; font-size: 12px; }",
        "</style>",
        _svg_rect(0, 0, width, height, "#ffffff"),
        _svg_text(width / 2, 28, title, size=20, weight="700", fill="#111827"),
    ]


def _svg_footer() -> list[str]:
    return ["</svg>"]


def _write_svg(path: Path, title: str, width: int, height: int, body: list[str]) -> None:
    path.write_text("\n".join(_svg_header(title, width, height) + body + _svg_footer()), encoding="utf-8")


def _bin_counts(values: list[float], bins: int, low: float = 0.0, high: float = 1.0) -> list[int]:
    """Count values into equally spaced bins over the provided interval."""

    counts = [0] * bins
    if not values:
        return counts

    span = high - low
    for value in values:
        if value <= low:
            idx = 0
        elif value >= high:
            idx = bins - 1
        else:
            idx = min(bins - 1, int(((value - low) / span) * bins))
        counts[idx] += 1
    return counts


def _evenly_spaced_values(start: float, stop: float, steps: int) -> list[float]:
    """Return evenly spaced tick values, handling degenerate ranges cleanly."""

    if steps <= 0:
        return [start]
    if stop <= start:
        return [start for _ in range(steps + 1)]
    return [start + (stop - start) * idx / steps for idx in range(steps + 1)]


def _format_tick_label(value: float, *, integer: bool = False, decimals: int = 1) -> str:
    """Format tick labels consistently across all plots."""

    return f"{int(round(value))}" if integer else f"{value:.{decimals}f}"


def _build_chart_shell(frame: PlotFrame, spec: ChartSpec) -> list[str]:
    """Create the shared title and axis labels for a chart body."""

    return [
        _svg_text(frame.left, 42, spec.title, anchor="start", size=14, weight="700"),
        _svg_text(frame.left, frame.height - 18, spec.x_label, anchor="middle", size=13),
        _svg_text(18, frame.top + frame.plot_height / 2, spec.y_label, anchor="middle", size=13, rotate=-90),
    ]


def _add_cartesian_axes(
    body: list[str],
    frame: PlotFrame,
    spec: ChartSpec,
    *,
    x_ticks: list[float],
    y_ticks: list[float],
    x_tick_label: Callable[[float], str],
    y_tick_label: Callable[[float], str],
) -> None:
    """Draw grid lines, axes, and tick labels for a cartesian chart."""

    for tick in y_ticks:
        y = frame.y(tick, spec.y_min, spec.y_max)
        body.append(_svg_line(frame.left, y, frame.left + frame.plot_width, y, "#e5e7eb", stroke_width=1.0))
        body.append(_svg_text(frame.left - 12, y + 4, y_tick_label(tick), anchor="end", size=11, fill="#4b5563"))

    for tick in x_ticks:
        x = frame.x(tick, spec.x_min, spec.x_max)
        body.append(_svg_line(x, frame.top, x, frame.top + frame.plot_height, "#f3f4f6", stroke_width=1.0))
        body.append(_svg_text(x, frame.top + frame.plot_height + 18, x_tick_label(tick), anchor="middle", size=11, fill="#4b5563"))

    body.append(_svg_line(frame.left, frame.top, frame.left, frame.top + frame.plot_height, "#374151", stroke_width=1.5))
    body.append(_svg_line(frame.left, frame.top + frame.plot_height, frame.left + frame.plot_width, frame.top + frame.plot_height, "#374151", stroke_width=1.5))


def _binned_median_points(points: list[tuple[float, float]], bins: int = 8) -> list[tuple[float, float]]:
    """Compress a scatter cloud into median points across equal-width bins."""

    if not points:
        return []

    x_values = [x for x, _ in points]
    xmin = min(x_values)
    xmax = max(x_values)
    if xmax <= xmin:
        return [(xmin, statistics.median([y for _, y in points]))]

    span = xmax - xmin
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(bins)]
    for x, y in points:
        idx = min(bins - 1, int(((x - xmin) / span) * bins))
        buckets[idx].append((x, y))

    summary: list[tuple[float, float]] = []
    for bucket in buckets:
        if not bucket:
            continue
        summary.append(
            (
                statistics.median([x for x, _ in bucket]),
                statistics.median([y for _, y in bucket]),
            )
        )
    return summary


def _length_bin_summary(rows: list[dict[str, object]], bins: int = 8) -> list[tuple[float, float]]:
    """Summarize length/F1 pairs by binning the lengths and taking medians."""

    pairs = [(float(row["length"]), float(row["f1"])) for row in rows]
    return _binned_median_points(pairs, bins=bins)


def _render_f1_vs_length(rows: list[dict[str, object]], plot_dir: Path) -> None:
    frame = PlotFrame()
    lengths = [float(row["length"]) for row in rows]
    spec = ChartSpec(
        title="RNAfold baseline: F1 vs length",
        x_label="Sequence length",
        y_label="F1",
        x_min=min(lengths),
        x_max=max(lengths),
        y_min=0.0,
        y_max=1.0,
    )

    body = _build_chart_shell(frame, spec)
    _add_cartesian_axes(
        body,
        frame,
        spec,
        x_ticks=_evenly_spaced_values(spec.x_min, spec.x_max, 5),
        y_ticks=[0.0, 0.25, 0.5, 0.75, 1.0],
        x_tick_label=lambda value: _format_tick_label(value, integer=True),
        y_tick_label=lambda value: _format_tick_label(value, decimals=2),
    )

    for row in rows:
        x = frame.x(float(row["length"]), spec.x_min, spec.x_max)
        y = frame.y(float(row["f1"]), spec.y_min, spec.y_max)
        body.append(_svg_circle(x, y, 4.3, "#2563eb", opacity=0.72))

    trend = _length_bin_summary(rows)
    if len(trend) >= 2:
        points = [(frame.x(length, spec.x_min, spec.x_max), frame.y(f1, spec.y_min, spec.y_max)) for length, f1 in trend]
        body.append(_svg_polyline(points, "#dc2626", stroke_width=2.4, opacity=0.9))
        for x, y in points:
            body.append(_svg_circle(x, y, 5.2, "#dc2626", opacity=1.0))

    body.append(_svg_text(frame.left + 16, frame.top + 16, f"n={len(rows)}", anchor="start", size=12, fill="#4b5563"))
    _write_svg(plot_dir / "f1_vs_length.svg", spec.title, frame.width, frame.height, body)


def _render_metric_distributions(rows: list[dict[str, object]], plot_dir: Path) -> None:
    frame = PlotFrame()
    metric_specs = [
        ("Precision", [float(row["precision"]) for row in rows], "#2563eb"),
        ("Recall", [float(row["recall"]) for row in rows], "#16a34a"),
        ("F1", [float(row["f1"]) for row in rows], "#dc2626"),
    ]
    bin_count = 10
    counts = [(name, values, color, _bin_counts(values, bin_count)) for name, values, color in metric_specs]
    max_count = max((max(value_counts) for _, _, _, value_counts in counts), default=1)

    spec = ChartSpec(
        title="RNAfold baseline: metric distributions",
        x_label="Metric value",
        y_label="Example count",
        x_min=0.0,
        x_max=1.0,
        y_min=0.0,
        y_max=float(max_count),
    )

    body = _build_chart_shell(frame, spec)
    _add_cartesian_axes(
        body,
        frame,
        spec,
        x_ticks=_evenly_spaced_values(spec.x_min, spec.x_max, 5),
        y_ticks=_evenly_spaced_values(spec.y_min, spec.y_max, 4),
        x_tick_label=lambda value: _format_tick_label(value, decimals=1),
        y_tick_label=lambda value: _format_tick_label(value, integer=True),
    )

    bin_width = frame.plot_width / bin_count
    group_width = bin_width / 3.0
    for metric_index, (name, _values, color, value_counts) in enumerate(counts):
        for bin_index, count in enumerate(value_counts):
            height = 0.0 if max_count == 0 else (count / max_count) * frame.plot_height
            x = frame.left + bin_index * bin_width + metric_index * group_width + 0.12 * group_width
            y = frame.top + frame.plot_height - height
            body.append(_svg_rect(x, y, 0.76 * group_width, height, color, opacity=0.28))

    legend_x = frame.left + frame.plot_width - 210
    legend_y = frame.top + 8
    for idx, (name, _values, color, _counts) in enumerate(counts):
        y = legend_y + idx * 18
        body.append(_svg_rect(legend_x, y - 10, 12, 12, color, opacity=0.45))
        body.append(_svg_text(legend_x + 18, y, name, anchor="start", size=12, fill="#111827"))

    _write_svg(plot_dir / "metric_distributions.svg", spec.title, frame.width, frame.height, body)


def _render_pair_count_scatter(rows: list[dict[str, object]], plot_dir: Path) -> None:
    frame = PlotFrame()
    true_pairs = [float(row["true_pairs"]) for row in rows]
    pred_pairs = [float(row["pred_pairs"]) for row in rows]
    max_value = max(true_pairs + pred_pairs) if rows else 1.0
    max_value = max(1.0, max_value * 1.05)

    spec = ChartSpec(
        title="RNAfold baseline: pair-count scatter",
        x_label="Reference pairs",
        y_label="Predicted pairs",
        x_min=0.0,
        x_max=max_value,
        y_min=0.0,
        y_max=max_value,
    )

    body = _build_chart_shell(frame, spec)
    _add_cartesian_axes(
        body,
        frame,
        spec,
        x_ticks=_evenly_spaced_values(spec.x_min, spec.x_max, 5),
        y_ticks=_evenly_spaced_values(spec.y_min, spec.y_max, 5),
        x_tick_label=lambda value: _format_tick_label(value, integer=True),
        y_tick_label=lambda value: _format_tick_label(value, integer=True),
    )
    body.append(_svg_line(frame.left, frame.top + frame.plot_height, frame.left + frame.plot_width, frame.top, "#111827", stroke_width=1.8, dasharray="6 4"))

    for row in rows:
        x = frame.x(float(row["true_pairs"]), spec.x_min, spec.x_max)
        y = frame.y(float(row["pred_pairs"]), spec.y_min, spec.y_max)
        body.append(_svg_circle(x, y, 4.2, "#7c3aed", opacity=0.72))

    body.append(_svg_text(frame.left + 16, frame.top + 16, f"n={len(rows)}", anchor="start", size=12, fill="#4b5563"))
    body.append(_svg_text(frame.left + frame.plot_width - 20, frame.top + 18, "y = x", anchor="end", size=12, fill="#111827"))
    _write_svg(plot_dir / "pair_count_scatter.svg", spec.title, frame.width, frame.height, body)


def _render_pair_error_vs_length(rows: list[dict[str, object]], plot_dir: Path) -> None:
    frame = PlotFrame()
    lengths = [float(row["length"]) for row in rows]
    errors = [abs(float(row["pred_pairs"]) - float(row["true_pairs"])) for row in rows]
    spec = ChartSpec(
        title="RNAfold baseline: pair-count error",
        x_label="Sequence length",
        y_label="|predicted pairs - reference pairs|",
        x_min=min(lengths),
        x_max=max(lengths),
        y_min=0.0,
        y_max=max(1.0, max(errors) * 1.15),
    )

    body = _build_chart_shell(frame, spec)
    _add_cartesian_axes(
        body,
        frame,
        spec,
        x_ticks=_evenly_spaced_values(spec.x_min, spec.x_max, 5),
        y_ticks=_evenly_spaced_values(spec.y_min, spec.y_max, 5),
        x_tick_label=lambda value: _format_tick_label(value, integer=True),
        y_tick_label=lambda value: _format_tick_label(value, decimals=1),
    )

    for row, error in zip(rows, errors):
        x = frame.x(float(row["length"]), spec.x_min, spec.x_max)
        y = frame.y(error, spec.y_min, spec.y_max)
        body.append(_svg_circle(x, y, 4.2, "#ea580c", opacity=0.72))

    trend = _binned_median_points(list(zip(lengths, errors)))
    if len(trend) >= 2:
        body.append(_svg_polyline([(frame.x(length, spec.x_min, spec.x_max), frame.y(error, spec.y_min, spec.y_max)) for length, error in trend], "#b45309", stroke_width=2.4, opacity=0.9))

    _write_svg(plot_dir / "pair_error_vs_length.svg", spec.title, frame.width, frame.height, body)


def write_error_analysis_report(
    rows: list[dict[str, object]],
    plot_dir: Path,
    *,
    micro_precision: float,
    micro_recall: float,
    micro_f1: float,
) -> Path:
    """Write the standard diagnostic plots and a small HTML index."""

    plot_dir.mkdir(parents=True, exist_ok=True)
    _render_f1_vs_length(rows, plot_dir)
    _render_metric_distributions(rows, plot_dir)
    _render_pair_count_scatter(rows, plot_dir)
    _render_pair_error_vs_length(rows, plot_dir)

    report_path = plot_dir / "error_analysis_report.html"
    report_path.write_text(
        "\n".join(
            [
                "<!doctype html>",
                "<html lang=\"en\">",
                "<head>",
                "<meta charset=\"utf-8\" />",
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
                "<title>RNAfold baseline error analysis</title>",
                "<style>",
                "body { font-family: Arial, Helvetica, sans-serif; margin: 24px; color: #111827; }",
                "h1 { margin-bottom: 0.3rem; }",
                "p { color: #4b5563; }",
                "section { margin: 24px 0 36px; }",
                "img { max-width: 100%; height: auto; border: 1px solid #e5e7eb; }",
                "</style>",
                "</head>",
                "<body>",
                "<h1>RNAfold baseline error analysis</h1>",
                f"<p>Examples evaluated: {len(rows)}</p>",
                f"<p>Micro precision: {micro_precision:.3f}</p>",
                f"<p>Micro recall: {micro_recall:.3f}</p>",
                f"<p>Micro F1: {micro_f1:.3f}</p>",
                "<section><h2>F1 vs length</h2><img src=\"f1_vs_length.svg\" alt=\"F1 vs length\" /></section>",
                "<section><h2>Metric distributions</h2><img src=\"metric_distributions.svg\" alt=\"Metric distributions\" /></section>",
                "<section><h2>Pair-count scatter</h2><img src=\"pair_count_scatter.svg\" alt=\"Pair-count scatter\" /></section>",
                "<section><h2>Absolute pair-count error</h2><img src=\"pair_error_vs_length.svg\" alt=\"Absolute pair-count error vs length\" /></section>",
                "</body>",
                "</html>",
            ]
        ),
        encoding="utf-8",
    )
    return report_path
