"""
pipeline.py — Orquestador principal del pipeline Spike-ADR V2
=============================================================
Ejecuta seis etapas:

  1. pdf_parser       → ProjectDocument
  2. signal_extractor → List[UncertaintySignal]
  3. spike_generator  → List[Spike]
  4. adr_generator    → List[ADRSkeleton]
  5. graph_builder    → NetworkX DiGraph + visualizaciones V2
  6. latex_report     → report.tex editable + report.pdf opcional

Salidas por proyecto:
  - result.json
  - signals.json
  - SPIKES_ADR.md
  - evaluation_rubric.md
  - evaluation_data.csv
  - graph.dot
  - graph.png
  - graph_traceability_matrix.png
  - graph_category_heatmap.png
  - graph_agent_heatmap.png
  - graph_layered_process.png
  - report.tex
  - report.pdf, si se usa --compile-pdf y pdflatex está disponible
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import List

from models import PipelineResult
from pdf_parser import parse_project_document
from signal_extractor import extract_signals
from spike_generator import generate_spikes
from adr_generator import generate_adrs, render_adr_markdown
from graph_builder import (
    build_graph,
    analyze_patterns,
    suggest_execution_order,
    export_to_dot,
    export_graph_json,
    generate_visual_artifacts,
)
from evaluate import (
    generate_evaluation_rubric,
    generate_csv_template,
    analyze_evaluation_results,
)
from latex_report import generate_latex_report, compile_latex_to_pdf


def run_pipeline(
    pdf_path: str,
    project_name: str,
    group_id: str,
    output_dir: str = "results",
    generate_latex: bool = True,
    compile_pdf: bool = False,
) -> PipelineResult:
    """
    Ejecuta el pipeline completo para un proyecto.

    Args:
        pdf_path: Ruta al PDF.
        project_name: Nombre legible del proyecto.
        group_id: ID o nombre de carpeta del proyecto.
        output_dir: Carpeta raíz de salida.
        generate_latex: Si True, genera report.tex.
        compile_pdf: Si True, intenta compilar report.pdf.
    """
    out = Path(output_dir) / group_id
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*72}")
    print(f"  Pipeline Spike-ADR V2 | {project_name} ({group_id})")
    print(f"{'='*72}")

    print("\n[1/6] Parseando documento PDF …")
    doc = parse_project_document(pdf_path, project_name, group_id)
    print(f"      {len(doc.user_stories)} historias · "
          f"{len(doc.quality_attributes)} QAs · "
          f"{len(doc.tech_stack)} componentes de stack")

    print("\n[2/6] Detectando señales de incertidumbre …")
    signals = extract_signals(doc)

    print("\n[3/6] Generando spikes candidatos …")
    spikes = generate_spikes(signals, project_name)

    print("\n[4/6] Generando ADR skeletons …")
    adrs = generate_adrs(spikes, doc)

    print("\n[5/6] Construyendo grafo y visualizaciones …")
    G = build_graph(spikes, adrs)
    graph_analysis = analyze_patterns(G)
    execution_order = suggest_execution_order(G)

    result = PipelineResult(
        project=doc,
        signals=signals,
        spikes=spikes,
        adrs=adrs,
        graph_data={
            **graph_analysis,
            "execution_order": execution_order,
            "graph_json": export_graph_json(G),
        },
    )

    _write_outputs(
        result=result,
        G=G,
        out=out,
        project_name=project_name,
        group_id=group_id,
        generate_latex=generate_latex,
        compile_pdf=compile_pdf,
    )

    print(f"\n✓ Pipeline completado. Artefactos en: {out}/")
    _print_summary(result)
    return result


def _write_outputs(
    result: PipelineResult,
    G,
    out: Path,
    project_name: str,
    group_id: str,
    generate_latex: bool = True,
    compile_pdf: bool = False,
) -> None:
    """Escribe todos los artefactos de salida."""

    # 1. JSON completo
    (out / "result.json").write_text(result.to_json(), encoding="utf-8")

    # 2. JSON de señales
    signals_data = [s.to_dict() for s in result.signals]
    (out / "signals.json").write_text(
        json.dumps(signals_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 3. Markdown principal
    _write_markdown_report(result, out, project_name, group_id)

    # 4. Rúbrica y CSV
    generate_evaluation_rubric(result, str(out / "evaluation_rubric.md"))
    generate_csv_template(result, str(out / "evaluation_data.csv"))

    # 5. DOT
    (out / "graph.dot").write_text(export_to_dot(G), encoding="utf-8")

    # 6. Visualizaciones V2
    graph_paths = generate_visual_artifacts(
        result=result,
        G=G,
        output_dir=str(out),
        project_name=project_name,
        group_id=group_id,
        include_project_in_titles=False,
    )

    # 7. LaTeX editable / PDF opcional
    if generate_latex:
        print("\n[6/6] Generando reporte LaTeX editable …")
        tex_path = generate_latex_report(
            result,
            output_path=out / "report.tex",
            graph_paths=graph_paths,
            title=f"Spike--ADR Report: {project_name} ({group_id})",
        )
        print(f"  [pipeline] Reporte LaTeX guardado en {tex_path}")

        if compile_pdf:
            print("  [pipeline] Intentando compilar PDF …")
            pdf_path = compile_latex_to_pdf(tex_path)
            if pdf_path:
                print(f"  [pipeline] Reporte PDF guardado en {pdf_path}")
            else:
                print("  [pipeline] No se pudo compilar PDF. El .tex quedó disponible.")


def _write_markdown_report(
    result: PipelineResult,
    out: Path,
    project_name: str,
    group_id: str,
) -> None:
    """Genera SPIKES_ADR.md."""
    md_lines = [
        f"# Spikes y ADRs candidatos — {project_name} ({group_id})",
        "",
        "> Generado por pipeline de detección de incertidumbre arquitectónica.",
        "> Este documento expone decisiones implícitas, evidencia faltante y ADRs candidatos.",
        "",
        f"## Resumen: {len(result.spikes)} spikes · {len(result.adrs)} ADRs · {len(result.signals)} señales",
        "",
        "## Artefactos visuales generados",
        "",
        "- `graph.png`: tabla visual Spike × ADR, recomendada para lectura principal.",
        "- `graph_bipartite_original.png`: grafo bipartito original, complementario.",
        "- `graph_traceability_matrix.png`: matriz Spike × ADR.",
        "- `graph_category_heatmap.png`: composición por categorías de incertidumbre.",
        "- `graph_agent_heatmap.png`: composición por agentes analíticos.",
        "- `graph_layered_process.png`: flujo por capas del proceso.",
        "",
        "| Spike | Título | Prioridad | ADR asociado |",
        "|---|---|---|---|",
    ]

    for spike in result.spikes:
        adr_id = spike.feeds_adr_ids[0] if spike.feeds_adr_ids else "—"
        md_lines.append(f"| {spike.id} | {spike.title} | {spike.priority} | {adr_id} |")

    md_lines.extend(["", "---", ""])

    for spike in result.spikes:
        adr = next((a for a in result.adrs if spike.id in a.spike_ids), None)
        if adr:
            md_lines.append(render_adr_markdown(adr, spike))
        else:
            md_lines.extend([
                f"## {spike.id}: {spike.title}",
                f"**Prioridad**: {spike.priority}",
                f"**Incertidumbre**: {spike.uncertainty}",
                "",
            ])

    md_lines.extend([
        "---",
        "",
        "## Grafo de dependencias N:M",
        "",
        "```text",
        _render_text_graph(result.spikes, result.adrs),
        "```",
        "",
        "### Patrones detectados",
        "",
    ])

    for pattern, count in result.graph_data.get("pattern_counts", {}).items():
        md_lines.append(f"- `{pattern}`: {count} instancia(s)")

    md_lines.extend([
        "",
        "### Orden sugerido de ejecución",
        "",
        " → ".join(result.graph_data.get("execution_order", [])),
        "",
    ])

    (out / "SPIKES_ADR.md").write_text("\n".join(md_lines), encoding="utf-8")


def _render_text_graph(spikes, adrs) -> str:
    lines = []
    for spike in spikes:
        adr_ids = " · ".join(spike.feeds_adr_ids) if spike.feeds_adr_ids else "(sin ADR)"
        blocked = " → bloquea: " + ", ".join(spike.blocks_spike_ids) if spike.blocks_spike_ids else ""
        lines.append(f"{spike.id} ──► {adr_ids}{blocked}")
    return "\n".join(lines)


def _print_summary(result: PipelineResult) -> None:
    stats = result.summary_stats()
    print(f"\n  Señales: {stats['n_signals']} | Spikes: {stats['n_spikes']} | ADRs: {stats['n_adrs']}")
    print(f"  Por tipo: {dict(stats['signals_by_type'])}")
    print(f"  Por prioridad: {dict(stats['spikes_by_priority'])}")


def run_batch(
    manifest_csv: str,
    pdf_dir: str,
    output_dir: str = "results",
    generate_latex: bool = True,
    compile_pdf: bool = False,
) -> List[PipelineResult]:
    """Procesa múltiples proyectos desde un CSV manifest."""
    results = []
    pdf_base = Path(pdf_dir)

    with open(manifest_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            group_id = row["group_id"].strip()
            project_name = row["project_name"].strip()
            pdf_filename = row["pdf_filename"].strip()
            pdf_path = str(pdf_base / pdf_filename)

            try:
                result = run_pipeline(
                    pdf_path,
                    project_name,
                    group_id,
                    output_dir,
                    generate_latex=generate_latex,
                    compile_pdf=compile_pdf,
                )
                results.append(result)
            except Exception as exc:
                print(f"✗ Error procesando {group_id} {project_name}: {exc}")

    return results


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Pipeline Spike--ADR V2")
    subparsers = parser.add_subparsers(dest="command")

    single = subparsers.add_parser("run", help="Procesar un PDF")
    single.add_argument("--pdf", required=True, help="Ruta al PDF")
    single.add_argument("--name", required=True, help="Nombre del proyecto")
    single.add_argument("--group", required=True, help="ID del grupo/carpeta")
    single.add_argument("--output", default="results", help="Directorio raíz de salida")
    single.add_argument("--no-latex", action="store_true", help="No generar report.tex")
    single.add_argument("--compile-pdf", action="store_true", help="Compilar report.pdf si pdflatex está disponible")

    batch = subparsers.add_parser("batch", help="Procesar múltiples PDFs desde manifest CSV")
    batch.add_argument("--manifest", required=True, help="CSV con group_id,project_name,pdf_filename")
    batch.add_argument("--pdf-dir", required=True, help="Carpeta base de PDFs")
    batch.add_argument("--output", default="results", help="Directorio raíz de salida")
    batch.add_argument("--no-latex", action="store_true", help="No generar report.tex")
    batch.add_argument("--compile-pdf", action="store_true", help="Compilar report.pdf si pdflatex está disponible")

    analyze = subparsers.add_parser("analyze", help="Analizar CSV de evaluación completado")
    analyze.add_argument("--csv", required=True, help="Ruta a evaluation_data.csv completado")

    args = parser.parse_args()

    if args.command == "run":
        run_pipeline(
            args.pdf,
            args.name,
            args.group,
            args.output,
            generate_latex=not args.no_latex,
            compile_pdf=args.compile_pdf,
        )
    elif args.command == "batch":
        run_batch(
            args.manifest,
            args.pdf_dir,
            args.output,
            generate_latex=not args.no_latex,
            compile_pdf=args.compile_pdf,
        )
    elif args.command == "analyze":
        analysis = analyze_evaluation_results(args.csv)
        print(json.dumps(analysis, ensure_ascii=False, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
