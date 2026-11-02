# Error table comparing hand measurements against the shrimp analysis pipeline
import argparse
import csv
from dataclasses import dataclass
import io
from pathlib import Path
import sys
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

# Ensure repo root and venv packages are on sys.path when script is executed directly
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

py_ver = f"python{sys.version_info.major}.{sys.version_info.minor}"
venv_site = repo_root / ".venv" / "lib" / py_ver / "site-packages"
if venv_site.exists() and str(venv_site) not in sys.path:
    sys.path.insert(0, str(venv_site))

import numpy as np  # noqa: E402

from shrimp.main import read_setting  # noqa: E402
from shrimp.models import Analysis, Settings, ShrimpMeasure, TrayResult  # noqa: E402
from shrimp.sam import make_sam_segmenter  # noqa: E402
from shrimp.sizing import SizeTable  # noqa: E402
from shrimp.store import Store  # noqa: E402
from shrimp.tray import analyze_shrimp, summarize  # noqa: E402


@dataclass
class HandRow:
    # Single hand measurement row from CSV
    sample_id: int
    shrimp: int
    length_mm: float
    length_postorbital_mm: Optional[float] = None
    line_no: int = 0


@dataclass
class SkippedRow:
    # Row skipped during matching with reason
    sample_id: int
    shrimp: int
    reason: str


@dataclass
class TraySummary:
    # Comparison summary for one tray photo
    sample_id: int
    n_hand: int
    n_pipeline_default: int
    mean_hand_mm: float
    mean_pipeline_mm: float
    mae_mm: float
    mae_pct: float
    scale_px_per_mm: Optional[float]
    reference: str


@dataclass
class LengthFactorSuggestion:
    # Statistics for length factor calculation
    n: int
    mean_postorbital_rostrum_ratio: Optional[float] = None
    mean_pipeline_hand_ratio: Optional[float] = None
    has_enough_rows: bool = False


@dataclass
class ComparisonReport:
    # Overall comparison report data
    trays: List[TraySummary]
    total_shrimp: int
    mean_abs_error_mm: float
    mean_abs_error_pct: float
    largest_error_mm: float
    largest_error_shrimp: Optional[Tuple[int, int]]
    wrongly_left_out: List[Tuple[int, int]]
    skipped_rows: List[SkippedRow]
    length_factor: LengthFactorSuggestion
    target_met: bool
    scale_checks: List[Tuple[int, Optional[float], str]]


def parse_csv(text: str) -> List[HandRow]:
    # Parse hand measurements from CSV string
    reader = csv.reader(io.StringIO(text))
    header = None
    col_map: Dict[str, int] = {}
    rows: List[HandRow] = []

    for row in reader:
        line_no = reader.line_num
        if not row or not any(cell.strip() for cell in row):
            continue

        if header is None:
            header = [col.strip() for col in row]
            col_map = {col: i for i, col in enumerate(header)}
            required = ["sample_id", "shrimp", "length_mm"]
            for req in required:
                if req not in col_map:
                    raise ValueError(f"line {line_no}: missing required column '{req}'")
            continue

        try:
            sample_id = int(row[col_map["sample_id"]].strip())
            shrimp = int(row[col_map["shrimp"]].strip())
            length_mm = float(row[col_map["length_mm"]].strip())

            po_val = None
            if "length_postorbital_mm" in col_map:
                idx = col_map["length_postorbital_mm"]
                if idx < len(row):
                    raw_po = row[idx].strip()
                    if raw_po:
                        po_val = float(raw_po)

            rows.append(
                HandRow(
                    sample_id=sample_id,
                    shrimp=shrimp,
                    length_mm=length_mm,
                    length_postorbital_mm=po_val,
                    line_no=line_no,
                )
            )
        except Exception as exc:
            raise ValueError(f"line {line_no}: {exc}") from exc

    return rows


def load_csv(path: Union[str, Path]) -> List[HandRow]:
    # Read hand measurement CSV file from disk
    content = Path(path).read_text(encoding="utf-8")
    return parse_csv(content)


def format_sample_list(store: Store) -> str:
    # Format real samples as text listing id, day, measured count, and photo name
    lines: List[str] = []
    for s in store.samples():
        if s.demo:
            continue
        photo_name = Path(s.photo_path).name if s.photo_path else ""
        lines.append(f"{s.id} {s.day} {s.n_measured} {photo_name}".rstrip())
    return "\n".join(lines)


def compare(
    rows: List[HandRow],
    analyses: Mapping[int, Any],
    settings: Optional[Settings] = None,
) -> ComparisonReport:
    # Pure comparison logic comparing hand measurements against pipeline analyses
    if settings is None:
        settings = Settings()

    parsed_analyses: Dict[int, Tuple[Any, TrayResult]] = {}
    for sid, entry in analyses.items():
        if isinstance(entry, TrayResult):
            parsed_analyses[sid] = (entry, entry)
        elif isinstance(entry, tuple):
            parsed_analyses[sid] = entry
        elif isinstance(entry, Analysis):
            tray = summarize(entry, None, settings, None)
            parsed_analyses[sid] = (entry, tray)
        else:
            parsed_analyses[sid] = (entry, getattr(entry, "tray", entry))

    matched_by_tray: Dict[int, List[Tuple[HandRow, ShrimpMeasure, float, float]]] = {}
    wrongly_left_out: List[Tuple[int, int]] = []
    skipped_rows: List[SkippedRow] = []
    po_ratios: List[float] = []
    pipe_ratios: List[float] = []

    for row in rows:
        if row.sample_id not in parsed_analyses:
            skipped_rows.append(SkippedRow(row.sample_id, row.shrimp, "unknown sample id"))
            continue

        analysis, tray = parsed_analyses[row.sample_id]
        if row.shrimp < 1 or row.shrimp > len(analysis.shrimp):
            skipped_rows.append(
                SkippedRow(
                    row.sample_id,
                    row.shrimp,
                    f"shrimp number {row.shrimp} out of range (found {len(analysis.shrimp)})",
                )
            )
            continue

        shrimp_measure = analysis.shrimp[row.shrimp - 1]
        if shrimp_measure.length_mm is None:
            skipped_rows.append(
                SkippedRow(row.sample_id, row.shrimp, "length_mm is None (no reference)")
            )
            continue

        hand_mm = row.length_mm
        pipe_mm = shrimp_measure.length_mm
        err_mm = abs(pipe_mm - hand_mm)
        err_pct = (err_mm / hand_mm) * 100.0

        matched_by_tray.setdefault(row.sample_id, []).append(
            (row, shrimp_measure, err_mm, err_pct)
        )

        if shrimp_measure.index not in tray.included:
            wrongly_left_out.append((row.sample_id, row.shrimp))

        if row.length_postorbital_mm is not None:
            po_ratios.append(row.length_postorbital_mm / hand_mm)
            pipe_ratios.append(pipe_mm / hand_mm)

    seen_ids: List[int] = []
    for r in rows:
        if r.sample_id in parsed_analyses and r.sample_id not in seen_ids:
            seen_ids.append(r.sample_id)
    for sid in sorted(parsed_analyses.keys()):
        if sid not in seen_ids:
            seen_ids.append(sid)

    trays: List[TraySummary] = []
    scale_checks: List[Tuple[int, Optional[float], str]] = []

    for sid in seen_ids:
        analysis, tray = parsed_analyses[sid]
        scale_checks.append((sid, analysis.scale_px_per_mm, analysis.reference))
        if sid not in matched_by_tray:
            continue

        items = matched_by_tray[sid]
        n_hand = len(items)
        n_default = tray.n_measured
        mean_hand = float(np.mean([item[0].length_mm for item in items]))
        mean_pipe = float(np.mean([item[1].length_mm for item in items]))
        mae_mm = float(np.mean([item[2] for item in items]))
        mae_pct = float(np.mean([item[3] for item in items]))

        trays.append(
            TraySummary(
                sample_id=sid,
                n_hand=n_hand,
                n_pipeline_default=n_default,
                mean_hand_mm=mean_hand,
                mean_pipeline_mm=mean_pipe,
                mae_mm=mae_mm,
                mae_pct=mae_pct,
                scale_px_per_mm=analysis.scale_px_per_mm,
                reference=analysis.reference,
            )
        )

    all_matched = [item for items in matched_by_tray.values() for item in items]
    total_shrimp = len(all_matched)

    if total_shrimp > 0:
      mean_abs_error_mm = float(np.mean([item[2] for item in all_matched]))
      mean_abs_error_pct = float(np.mean([item[3] for item in all_matched]))
      max_item = max(all_matched, key=lambda x: x[2])
      largest_error_mm = float(max_item[2])
      largest_error_shrimp: Optional[Tuple[int, int]] = (
          max_item[0].sample_id,
          max_item[0].shrimp,
      )
      target_met = mean_abs_error_pct <= 5.0
    else:
      mean_abs_error_mm = 0.0
      mean_abs_error_pct = 0.0
      largest_error_mm = 0.0
      largest_error_shrimp = None
      target_met = False

    n_po = len(po_ratios)
    if n_po >= 5:
        length_factor = LengthFactorSuggestion(
            n=n_po,
            mean_postorbital_rostrum_ratio=float(np.mean(po_ratios)),
            mean_pipeline_hand_ratio=float(np.mean(pipe_ratios)),
            has_enough_rows=True,
        )
    else:
        length_factor = LengthFactorSuggestion(
            n=n_po,
            mean_postorbital_rostrum_ratio=None,
            mean_pipeline_hand_ratio=None,
            has_enough_rows=False,
        )

    return ComparisonReport(
        trays=trays,
        total_shrimp=total_shrimp,
        mean_abs_error_mm=mean_abs_error_mm,
        mean_abs_error_pct=mean_abs_error_pct,
        largest_error_mm=largest_error_mm,
        largest_error_shrimp=largest_error_shrimp,
        wrongly_left_out=wrongly_left_out,
        skipped_rows=skipped_rows,
        length_factor=length_factor,
        target_met=target_met,
        scale_checks=scale_checks,
    )


def render_markdown(report: ComparisonReport) -> str:
    # Render comparison report into Markdown formatted string
    lines: List[str] = ["# Error Table Report", "", "## 1. Per Tray Results"]

    if report.trays:
        lines.append(
            "| Sample ID | Hand Measured | Default Count | Mean Hand (mm) | "
            "Mean Pipeline (mm) | MAE (mm) | MAE (%) |"
        )
        lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for t in report.trays:
            lines.append(
                f"| {t.sample_id} | {t.n_hand} | {t.n_pipeline_default} | "
                f"{t.mean_hand_mm:.1f} | {t.mean_pipeline_mm:.1f} | "
                f"{t.mae_mm:.3f} | {t.mae_pct:.2f}% |"
            )
    else:
        lines.append("No matched tray data available.")

    lines.extend(["", "## 2. Totals", f"- Total shrimp measured: {report.total_shrimp}"])
    lines.append(
        f"- Mean absolute error: {report.mean_abs_error_mm:.3f} mm "
        f"({report.mean_abs_error_pct:.2f}%)"
    )

    if report.largest_error_shrimp:
        lines.append(
            f"- Largest single error: {report.largest_error_mm:.3f} mm "
            f"(sample {report.largest_error_shrimp[0]} #{report.largest_error_shrimp[1]})"
        )
    else:
        lines.append("- Largest single error: none")

    if report.wrongly_left_out:
        left_str = ", ".join(f"Sample {sid}, shrimp #{idx}" for sid, idx in report.wrongly_left_out)
        lines.append(f"- Wrongly left out: {left_str}")
    else:
        lines.append("- Wrongly left out: none")

    lines.extend(["", "## 3. Scale Check"])
    if report.scale_checks:
        lines.append("| Sample ID | Scale (px/mm) | Reference Used |")
        lines.append("| ---: | ---: | :--- |")
        for sid, sc, ref in report.scale_checks:
            sc_str = f"{sc:.3f}" if sc is not None else "None"
            lines.append(f"| {sid} | {sc_str} | {ref} |")
    else:
        lines.append("No scale information available.")

    lines.extend(["", "## 4. Length Factor Suggestion"])
    if report.length_factor.has_enough_rows:
        lines.append(
            f"- Mean ratio postorbital / rostrum: "
            f"{report.length_factor.mean_postorbital_rostrum_ratio:.3f} "
            f"(n={report.length_factor.n})"
        )
        lines.append(
            f"- Mean ratio pipeline / hand: "
            f"{report.length_factor.mean_pipeline_hand_ratio:.3f}"
        )
    else:
        lines.append(
            f"Not enough rows with postorbital length "
            f"(found {report.length_factor.n}, need at least 5)."
        )

    if report.skipped_rows:
        lines.extend(["", "## 5. Skipped Rows"])
        lines.append(f"- Found {len(report.skipped_rows)} skipped row(s):")
        for sk in report.skipped_rows:
            lines.append(f"  - Sample {sk.sample_id}, shrimp #{sk.shrimp}: {sk.reason}")

    status_str = "MET" if report.target_met else "NOT MET"
    lines.extend(
        [
            "",
            f"hand measurements by the author, n={report.total_shrimp}, market shrimp laid flat.",
            "",
            f"Target: mean error at most 5%: {status_str} "
            f"(measured {report.mean_abs_error_pct:.1f}%, n={report.total_shrimp})",
        ]
    )

    return "\n".join(lines)


def run_error_table(
    csv_path: Union[str, Path] = "data/labelled/trays.csv",
    db_path: Union[str, Path] = "data/shrimp.db",
    out_path: Optional[Union[str, Path]] = "docs/results/error-table.md",
    segmenter: Optional[Any] = None,
    store: Optional[Store] = None,
) -> Tuple[ComparisonReport, str]:
    # Run end-to-end pipeline comparison and optionally write Markdown report
    repo_root = Path(__file__).resolve().parent.parent
    if store is None:
        store = Store(db_path)

    settings = store.load_settings(Settings())
    table_path = repo_root / "shrimp" / "size_table.json"
    if not table_path.exists():
        table_path = repo_root / "scripts" / "size_table.json"
    table = SizeTable.load(table_path) if table_path.exists() else None

    if segmenter is None:
        api_key = read_setting("META_API_KEY", root=repo_root) or ""
        decode_script = repo_root / "node" / "decode.mjs"
        cache_dir = repo_root / "data" / "cache"
        segmenter = make_sam_segmenter(
            api_key=api_key,
            decode_script=str(decode_script),
            cache_dir=str(cache_dir),
        )

    rows = load_csv(csv_path)
    sample_ids = {r.sample_id for r in rows}
    saved_samples = {s.id: s for s in store.samples()}

    analyses: Dict[int, Tuple[Analysis, TrayResult]] = {}
    for sid in sample_ids:
        sample_rec = saved_samples.get(sid)
        if sample_rec is None or not sample_rec.photo_path:
            continue
        p = Path(sample_rec.photo_path)
        if not p.is_absolute():
            p = repo_root / p
        if not p.exists():
            continue
        photo_bytes = p.read_bytes()
        analysis = analyze_shrimp(photo_bytes, settings, segmenter)
        tray = summarize(analysis, None, settings, table)
        analyses[sid] = (analysis, tray)

    report = compare(rows, analyses, settings=settings)
    md = render_markdown(report)

    if out_path:
        out_target = Path(out_path)
        if not out_target.is_absolute():
            out_target = repo_root / out_target
        out_target.parent.mkdir(parents=True, exist_ok=True)
        out_target.write_text(md, encoding="utf-8")

    return report, md


def main(argv: Optional[List[str]] = None) -> int:
    # CLI entry point for error table generation or sample listing
    parser = argparse.ArgumentParser(description="Shrimp pipeline error table")
    parser.add_argument("--csv", default="data/labelled/trays.csv", help="Hand measurements CSV")
    parser.add_argument("--db", default="data/shrimp.db", help="SQLite database path")
    parser.add_argument(
        "--out", default="docs/results/error-table.md", help="Markdown output path"
    )
    parser.add_argument("--list", action="store_true", help="List real saved samples")

    args = parser.parse_args(argv)

    if args.list:
        store = Store(args.db)
        output = format_sample_list(store)
        if output:
            print(output)
        return 0

    _, md = run_error_table(csv_path=args.csv, db_path=args.db, out_path=args.out)
    print(md)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
