"""
run_batch_by_folder.py — Ejecución batch por carpeta de PDFs
============================================================

Ejecuta el pipeline Spike--ADR V2 sobre todos los PDFs de una carpeta.
Por cada PDF crea una carpeta de salida con el mismo nombre base del archivo.

Ejemplo:
    python run_batch_by_folder.py --input-dir "./pdfs" --output-dir "./results_batch" --compile-pdf
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pipeline import run_pipeline


WINDOWS_RESERVED_CHARS = r'<>:"/\|?*'


def safe_folder_name(name: str, max_len: int = 140) -> str:
    cleaned = name.strip()
    for ch in WINDOWS_RESERVED_CHARS:
        cleaned = cleaned.replace(ch, "_")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace(" ", "_")
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip("._-")
    return (cleaned or "project")[:max_len]


def infer_project_name(pdf_path: Path) -> str:
    stem = pdf_path.stem
    name = re.sub(r"^G\d{2}CC_\d+_assignsubmission_file_+", "", stem, flags=re.IGNORECASE)
    name = re.sub(r"^Grupo\d+_+", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^\[?E\d\]?\s*", "", name, flags=re.IGNORECASE)
    m = re.search(r"Historias[_\s-]+(.+)$", name, flags=re.IGNORECASE)
    if m and len(m.group(1)) <= 60:
        name = m.group(1)
    name = re.sub(r"(?i)\b(Historias|Usuario|Usuarios|VF|V2|corregidas|Formulario)\b", " ", name)
    name = re.sub(r"[_\-\[\]\(\)]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or pdf_path.stem


def iter_pdfs(input_dir: Path, recursive: bool = False) -> List[Path]:
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(p for p in input_dir.glob(pattern) if p.is_file())


@dataclass
class BatchProjectStatus:
    pdf_file: str
    project_name: str
    output_folder: str
    status: str
    n_signals: int = 0
    n_spikes: int = 0
    n_adrs: int = 0
    error: str = ""


def summarize_result(result) -> dict:
    return {
        "n_signals": len(result.signals),
        "n_spikes": len(result.spikes),
        "n_adrs": len(result.adrs),
    }


def write_batch_summary(statuses: List[BatchProjectStatus], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now().isoformat(),
        "total_projects": len(statuses),
        "ok_projects": sum(1 for s in statuses if s.status == "ok"),
        "error_projects": sum(1 for s in statuses if s.status == "error"),
        "total_signals": sum(s.n_signals for s in statuses),
        "total_spikes": sum(s.n_spikes for s in statuses),
        "total_adrs": sum(s.n_adrs for s in statuses),
        "projects": [asdict(s) for s in statuses],
    }
    (output_dir / "batch_summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (output_dir / "batch_summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "pdf_file",
                "project_name",
                "output_folder",
                "status",
                "n_signals",
                "n_spikes",
                "n_adrs",
                "error",
            ],
        )
        writer.writeheader()
        for s in statuses:
            writer.writerow(asdict(s))


def run_folder_batch(
    input_dir: Path,
    output_dir: Path,
    recursive: bool = False,
    compile_pdf: bool = False,
    generate_latex: bool = True,
    continue_on_error: bool = True,
    limit: Optional[int] = None,
) -> List[BatchProjectStatus]:
    input_dir = Path(input_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = iter_pdfs(input_dir, recursive=recursive)
    if limit is not None:
        pdfs = pdfs[:limit]

    if not pdfs:
        print(f"[batch-folder] No se encontraron PDFs en: {input_dir}")
        return []

    print("=" * 72)
    print("Batch Spike--ADR V2 por carpeta")
    print("=" * 72)
    print(f"Input dir:      {input_dir}")
    print(f"Output dir:     {output_dir}")
    print(f"PDFs:           {len(pdfs)}")
    print(f"Generate LaTeX: {generate_latex}")
    print(f"Compile PDF:    {compile_pdf}")
    print("=" * 72)

    statuses: List[BatchProjectStatus] = []

    for idx, pdf_path in enumerate(pdfs, start=1):
        folder_name = safe_folder_name(pdf_path.stem)
        project_name = infer_project_name(pdf_path)
        group_id = folder_name

        print()
        print("-" * 72)
        print(f"[{idx}/{len(pdfs)}] {pdf_path.name}")
        print(f"Project name: {project_name}")
        print(f"Output:       {output_dir / folder_name}")
        print("-" * 72)

        try:
            result = run_pipeline(
                pdf_path=str(pdf_path),
                project_name=project_name,
                group_id=group_id,
                output_dir=str(output_dir),
                generate_latex=generate_latex,
                compile_pdf=compile_pdf,
            )
            statuses.append(
                BatchProjectStatus(
                    pdf_file=str(pdf_path),
                    project_name=project_name,
                    output_folder=str(output_dir / folder_name),
                    status="ok",
                    **summarize_result(result),
                )
            )
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"
            print(f"[batch-folder] ERROR en {pdf_path.name}: {error_msg}")
            error_folder = output_dir / folder_name
            error_folder.mkdir(parents=True, exist_ok=True)
            (error_folder / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
            statuses.append(
                BatchProjectStatus(
                    pdf_file=str(pdf_path),
                    project_name=project_name,
                    output_folder=str(error_folder),
                    status="error",
                    error=error_msg,
                )
            )
            if not continue_on_error:
                break

    write_batch_summary(statuses, output_dir)

    print()
    print("=" * 72)
    print("Batch finalizado")
    print("=" * 72)
    print(f"Proyectos OK:     {sum(1 for s in statuses if s.status == 'ok')}")
    print(f"Proyectos error:  {sum(1 for s in statuses if s.status == 'error')}")
    print(f"Señales totales:  {sum(s.n_signals for s in statuses)}")
    print(f"Spikes totales:   {sum(s.n_spikes for s in statuses)}")
    print(f"ADRs totales:     {sum(s.n_adrs for s in statuses)}")
    print(f"Resumen CSV:      {output_dir / 'batch_summary.csv'}")
    print(f"Resumen JSON:     {output_dir / 'batch_summary.json'}")

    return statuses


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta el pipeline Spike--ADR V2 sobre todos los PDFs de una carpeta."
    )
    parser.add_argument("--input-dir", required=True, help="Carpeta que contiene PDFs.")
    parser.add_argument("--output-dir", required=True, help="Carpeta raíz de salida.")
    parser.add_argument("--recursive", action="store_true", help="Buscar PDFs recursivamente.")
    parser.add_argument("--compile-pdf", action="store_true", help="Intentar compilar report.pdf.")
    parser.add_argument("--no-latex", action="store_true", help="No generar report.tex.")
    parser.add_argument("--stop-on-error", action="store_true", help="Detener ante primer error.")
    parser.add_argument("--limit", type=int, default=None, help="Procesar solo los primeros N PDFs.")
    args = parser.parse_args()

    run_folder_batch(
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
        recursive=args.recursive,
        compile_pdf=args.compile_pdf,
        generate_latex=not args.no_latex,
        continue_on_error=not args.stop_on_error,
        limit=args.limit,
    )


if __name__ == "__main__":
    _cli()
