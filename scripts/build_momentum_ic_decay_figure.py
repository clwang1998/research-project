#!/usr/bin/env python3
"""Render the traded-horizon momentum IC decay figure from archived artifacts.

The cloud runtime used for the paper loop does not always provide matplotlib, so
this script writes a small vector PDF directly. It intentionally keeps the plot
simple: mean Rank IC with block-bootstrap confidence intervals plus the
block-bootstrap t-stat on a secondary scale.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--input-csv",
        default=(
            "report/artifacts/momentum_ic_traded_horizons/"
            "momentum_traded_horizon_ic_robustness.csv"
        ),
    )
    p.add_argument("--out", default="report/figures/fig_momentum_ic_decay.pdf")
    return p.parse_args()


def pdf_text(x: float, y: float, text: str, size: int = 8, align: str = "left") -> str:
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    width = len(text) * size * 0.45
    if align == "center":
        x -= width / 2
    elif align == "right":
        x -= width
    return f"BT /F1 {size} Tf {x:.2f} {y:.2f} Td ({safe}) Tj ET\n"


def write_pdf(out: Path, commands: str, width: int = 460, height: int = 260) -> None:
    stream = commands.encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream",
    ]
    body = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"
    xref_pos = len(body)
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f\n".encode("ascii")
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n\n".encode("ascii")
    trailer = (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    out.write_bytes(body + xref + trailer)


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input_csv).sort_values("horizon_days")
    required = {
        "horizon_days",
        "mean_rank_ic",
        "block_boot_mean_ci_low",
        "block_boot_mean_ci_high",
        "block_boot_t",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"{args.input_csv} missing columns: {sorted(missing)}")

    x_vals = df["horizon_days"].astype(float).tolist()
    y_vals = df["mean_rank_ic"].astype(float).tolist()
    lo_vals = df["block_boot_mean_ci_low"].astype(float).tolist()
    hi_vals = df["block_boot_mean_ci_high"].astype(float).tolist()
    t_vals = df["block_boot_t"].astype(float).tolist()

    width, height = 460, 260
    left, right, bottom, top = 58, 52, 42, 32
    plot_w = width - left - right
    plot_h = height - bottom - top
    min_x, max_x = min(x_vals), max(x_vals)
    y_min = min(0.0, min(lo_vals)) - 0.004
    y_max = max(hi_vals) + 0.004
    t_min, t_max = 0.0, max(max(t_vals), 2.5) + 0.2

    def sx(v: float) -> float:
        return left + (v - min_x) / (max_x - min_x) * plot_w

    def sy(v: float) -> float:
        return bottom + (v - y_min) / (y_max - y_min) * plot_h

    def sty(v: float) -> float:
        return bottom + (v - t_min) / (t_max - t_min) * plot_h

    cmds = []
    cmds.append("1 1 1 rg 0 0 460 260 re f\n")
    cmds.append(pdf_text(width / 2, 242, "Momentum IC decay at traded horizons", 10, "center"))
    cmds.append("0.82 0.82 0.82 RG 0.4 w\n")
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = bottom + frac * plot_h
        cmds.append(f"{left:.2f} {y:.2f} m {left + plot_w:.2f} {y:.2f} l S\n")
    cmds.append("0 0 0 RG 0.8 w\n")
    cmds.append(f"{left:.2f} {bottom:.2f} m {left:.2f} {bottom + plot_h:.2f} l S\n")
    cmds.append(f"{left:.2f} {bottom:.2f} m {left + plot_w:.2f} {bottom:.2f} l S\n")
    cmds.append(f"{left + plot_w:.2f} {bottom:.2f} m {left + plot_w:.2f} {bottom + plot_h:.2f} l S\n")
    if y_min < 0 < y_max:
        y0 = sy(0.0)
        cmds.append("0.25 0.25 0.25 RG 0.7 w\n")
        cmds.append(f"{left:.2f} {y0:.2f} m {left + plot_w:.2f} {y0:.2f} l S\n")
    t196 = sty(1.96)
    cmds.append("0.77 0.31 0.32 RG 0.6 w\n")
    cmds.append(f"{left:.2f} {t196:.2f} m {left + plot_w:.2f} {t196:.2f} l S\n")

    cmds.append("0.30 0.45 0.69 RG 1.2 w\n")
    points = [(sx(x), sy(y)) for x, y in zip(x_vals, y_vals)]
    cmds.append(" ".join([f"{points[0][0]:.2f} {points[0][1]:.2f} m"] + [f"{x:.2f} {y:.2f} l" for x, y in points[1:]]) + " S\n")
    for x, y, lo, hi in zip(x_vals, y_vals, lo_vals, hi_vals):
        px, py, plo, phi = sx(x), sy(y), sy(lo), sy(hi)
        cmds.append(f"{px:.2f} {plo:.2f} m {px:.2f} {phi:.2f} l S\n")
        cmds.append(f"{px - 3:.2f} {plo:.2f} m {px + 3:.2f} {plo:.2f} l S\n")
        cmds.append(f"{px - 3:.2f} {phi:.2f} m {px + 3:.2f} {phi:.2f} l S\n")
        cmds.append(f"{px - 2.2:.2f} {py - 2.2:.2f} 4.4 4.4 re f\n")

    cmds.append("0.77 0.31 0.32 RG 1.0 w\n")
    t_points = [(sx(x), sty(t)) for x, t in zip(x_vals, t_vals)]
    dash = "[4 3] 0 d "
    cmds.append(dash + " ".join([f"{t_points[0][0]:.2f} {t_points[0][1]:.2f} m"] + [f"{x:.2f} {y:.2f} l" for x, y in t_points[1:]]) + " S [] 0 d\n")
    for px, py in t_points:
        cmds.append(f"{px - 2.3:.2f} {py - 2.3:.2f} 4.6 4.6 re S\n")

    for x in x_vals:
        px = sx(x)
        cmds.append("0 0 0 RG 0.6 w\n")
        cmds.append(f"{px:.2f} {bottom:.2f} m {px:.2f} {bottom - 3:.2f} l S\n")
        cmds.append(pdf_text(px, bottom - 16, f"{int(x)}d", 7, "center"))
    for val in [0.00, 0.02, 0.04, 0.06]:
        if y_min <= val <= y_max:
            cmds.append(pdf_text(left - 7, sy(val) - 2, f"{val:.2f}", 7, "right"))
    for val in [1.0, 2.0, 3.0]:
        if t_min <= val <= t_max:
            cmds.append(pdf_text(left + plot_w + 7, sty(val) - 2, f"{val:.1f}", 7, "left"))
    cmds.append(pdf_text(left + plot_w / 2, 14, "Traded prediction horizon", 8, "center"))
    cmds.append(pdf_text(15, bottom + plot_h / 2, "Mean rank IC", 8, "center"))
    cmds.append(pdf_text(width - 10, bottom + plot_h / 2, "t-stat", 8, "right"))
    cmds.append("0.30 0.45 0.69 RG 1.2 w 72 226 m 92 226 l S\n")
    cmds.append(pdf_text(97, 223, "Mean IC with 95% CI", 7, "left"))
    cmds.append("0.77 0.31 0.32 RG 1.0 w [4 3] 0 d 220 226 m 240 226 l S [] 0 d\n")
    cmds.append(pdf_text(245, 223, "Block-bootstrap t", 7, "left"))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_pdf(out, "".join(cmds), width=width, height=height)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
