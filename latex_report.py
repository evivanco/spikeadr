"""
latex_report.py — Exportador LaTeX/PDF para resultados del pipeline Spike-ADR
============================================================================

Este módulo agrega una etapa opcional al pipeline:

    PipelineResult / result.json
        -> LaTeX report editable
        -> PDF compilable

Uso desde Python:

    from latex_report import generate_latex_report, compile_latex_to_pdf

    tex_path = generate_latex_report(
        result,
        output_path="results/G02/report.tex",
        graph_path="results/G02/graph.png",
    )

    compile_latex_to_pdf(tex_path)

Uso desde terminal:

    python latex_report.py \
        --result results/G02/result.json \
        --output results/G02/report.tex \
        --graph results/G02/graph.png \
        --compile

Diseño:
- No depende de tcolorbox para evitar errores como "/tcb/breakable".
- Genera LaTeX editable, con tablas compactas y secciones por Spike/ADR.
- Acepta un PipelineResult en memoria o un result.json serializado.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades LaTeX
# ─────────────────────────────────────────────────────────────────────────────

_LATEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(value: Any) -> str:
    """Escapa texto para LaTeX, preservando saltos simples."""
    if value is None:
        return ""
    text = str(value)
    return "".join(_LATEX_REPLACEMENTS.get(ch, ch) for ch in text)


def latex_paragraph(value: Any) -> str:
    """Escapa texto y normaliza espacios/saltos para párrafos LaTeX."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return latex_escape(text)


def short(value: Any, max_chars: int = 180) -> str:
    """Recorta texto largo para tablas compactas."""
    if value is None:
        return ""
    text = " ".join(str(value).split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def safe_get(data: Dict[str, Any], key: str, default: Any = "") -> Any:
    return data.get(key, default)


def as_dict_result(result: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """
    Convierte PipelineResult o dict a dict serializable.
    Compatible con:
    - result.json generado por PipelineResult.to_json()
    - objeto PipelineResult en memoria
    """
    if isinstance(result, dict):
        return result

    if hasattr(result, "to_json"):
        return json.loads(result.to_json())

    raise TypeError(
        "generate_latex_report espera un dict/result.json o un objeto PipelineResult con to_json()."
    )


def load_result_json(path: Union[str, Path]) -> Dict[str, Any]:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Render principal
# ─────────────────────────────────────────────────────────────────────────────

def generate_latex_report(
    result: Union[Dict[str, Any], Any],
    output_path: Union[str, Path],
    graph_path: Optional[Union[str, Path]] = None,
    graph_paths: Optional[Dict[str, Union[str, Path]]] = None,
    title: Optional[str] = None,
    author: str = "Pipeline Spike--ADR",
    include_full_signals: bool = True,
    include_graph_analysis: bool = True,
) -> Path:
    """
    Genera un archivo .tex editable a partir de un PipelineResult o result.json.

    Args:
        result: PipelineResult o dict cargado desde result.json.
        output_path: ruta de salida .tex.
        graph_path: ruta opcional a graph.png generado por graph_builder.
        graph_paths: rutas opcionales a visualizaciones V2 generadas por graph_builder.
        title: título opcional del informe.
        author: autor mostrado en portada.
        include_full_signals: incluye tabla de señales detectadas.
        include_graph_analysis: incluye patrones Spike--ADR y orden sugerido.

    Returns:
        Path al archivo .tex generado.
    """
    data = as_dict_result(result)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    project_name = data.get("project_name", "Proyecto")
    group_id = data.get("group_id", "Grupo")
    title = title or f"Spike--ADR Report: {project_name} ({group_id})"

    tex = []
    tex.append(_render_preamble())
    tex.append(r"\begin{document}")
    tex.append(_render_title(title, author, data))
    tex.append(_render_executive_summary(data))

    if graph_paths:
        tex.append(_render_visual_artifacts_section(graph_paths))
    elif graph_path:
        tex.append(_render_graph_figure(graph_path))

    if include_full_signals:
        tex.append(_render_signals_table(data))

    tex.append(_render_spikes_and_adrs(data))

    if include_graph_analysis:
        tex.append(_render_graph_analysis(data))

    tex.append(_render_appendix_evaluation_template(data))
    tex.append(r"\end{document}")
    tex.append("")

    output_path.write_text("\n".join(tex), encoding="utf-8")
    return output_path


def _render_preamble() -> str:
    return r"""
\documentclass[11pt]{article}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[spanish,english]{babel}
\usepackage[a4paper,margin=2.2cm]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{tabularx}
\usepackage{array}
\usepackage{xcolor}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{float}
\usepackage{caption}
\usepackage{titlesec}
\usepackage{microtype}

\hypersetup{
    colorlinks=true,
    linkcolor=black,
    urlcolor=blue,
    citecolor=black
}

\setlength{\parskip}{0.5em}
\setlength{\parindent}{0pt}
\renewcommand{\arraystretch}{1.12}
\setlist[itemize]{leftmargin=1.3em,itemsep=0.15em,topsep=0.2em}

\newcommand{\SpikeADR}{Spike--ADR}
\newcommand{\smallcode}[1]{\texttt{\small #1}}

\titleformat{\section}{\Large\bfseries}{\thesection}{0.6em}{}
\titleformat{\subsection}{\large\bfseries}{\thesubsection}{0.6em}{}
\titleformat{\subsubsection}{\normalsize\bfseries}{\thesubsubsection}{0.6em}{}

\captionsetup{font=small,labelfont=bf}
""".strip()


def _render_title(title: str, author: str, data: Dict[str, Any]) -> str:
    generated_at = latex_escape(data.get("generated_at", ""))
    return rf"""
\begin{{titlepage}}
\centering
\vspace*{{2cm}}
{{\Huge\bfseries {latex_escape(title)}\par}}
\vspace{{0.8cm}}
{{\Large {latex_escape(author)}\par}}
\vspace{{0.4cm}}
{{\large Generated at: {generated_at}\par}}
\vfill
\begin{{tabular}}{{ll}}
\toprule
Project & {latex_escape(data.get("project_name", ""))} \\
Group & {latex_escape(data.get("group_id", ""))} \\
Signals & {len(data.get("signals", []))} \\
Spikes & {len(data.get("spikes", []))} \\
ADRs & {len(data.get("adrs", []))} \\
\bottomrule
\end{{tabular}}
\vfill
{{\small Editable LaTeX report generated from the Spike--ADR pipeline.}}
\end{{titlepage}}

\tableofcontents
\newpage
""".strip()


def _render_executive_summary(data: Dict[str, Any]) -> str:
    signals = data.get("signals", [])
    spikes = data.get("spikes", [])
    adrs = data.get("adrs", [])

    signal_counts = {}
    for s in signals:
        st = s.get("signal_type", "Unknown")
        signal_counts[st] = signal_counts.get(st, 0) + 1

    priority_counts = {}
    for s in spikes:
        p = s.get("priority", "Unknown")
        priority_counts[p] = priority_counts.get(p, 0) + 1

    signal_rows = "\n".join(
        rf"{latex_escape(k)} & {v} \\"
        for k, v in sorted(signal_counts.items(), key=lambda kv: kv[0])
    ) or r"None & 0 \\"

    priority_rows = "\n".join(
        rf"{latex_escape(k)} & {v} \\"
        for k, v in sorted(priority_counts.items(), key=lambda kv: kv[0])
    ) or r"None & 0 \\"

    return rf"""
\section{{Executive Summary}}

This report summarizes the architectural uncertainty signals, candidate spikes, ADR skeletons, and Spike--ADR dependency patterns generated for \textbf{{{latex_escape(data.get("project_name", ""))}}}.

\begin{{table}}[H]
\centering
\caption{{Summary of generated artifacts.}}
\label{{tab:summary_artifacts}}
\begin{{tabular}}{{lr}}
\toprule
\textbf{{Artifact}} & \textbf{{Count}} \\
\midrule
Uncertainty signals & {len(signals)} \\
Candidate spikes & {len(spikes)} \\
ADR skeletons & {len(adrs)} \\
\bottomrule
\end{{tabular}}
\end{{table}}

\begin{{minipage}}{{0.48\linewidth}}
\centering
\begin{{tabular}}{{lr}}
\toprule
\textbf{{Signal type}} & \textbf{{Count}} \\
\midrule
{signal_rows}
\bottomrule
\end{{tabular}}
\end{{minipage}}
\hfill
\begin{{minipage}}{{0.48\linewidth}}
\centering
\begin{{tabular}}{{lr}}
\toprule
\textbf{{Spike priority}} & \textbf{{Count}} \\
\midrule
{priority_rows}
\bottomrule
\end{{tabular}}
\end{{minipage}}

\section{{Project Context}}

\textbf{{Project:}} {latex_escape(data.get("project_name", ""))}

\textbf{{Group:}} {latex_escape(data.get("group_id", ""))}

The following sections present the detected uncertainty signals, the candidate spikes that should produce evidence, and the ADR skeletons that should record the architectural rationale.
""".strip()




def _render_visual_artifacts_section(graph_paths: Dict[str, Union[str, Path]]) -> str:
    """
    Renderiza las visualizaciones V2 del pipeline.

    Espera llaves como:
      - traceability_matrix
      - category_heatmap
      - agent_heatmap
      - layered_process
      - bipartite_graph
    """
    captions = {
        "layered_process": (
            "Layered process view of the Spike--ADR pipeline, showing how signals, "
            "analytical agents, spikes, ADRs, and cardinality patterns compose the decision process."
        ),
        "traceability_matrix": (
            "Spike--ADR traceability matrix. Filled cells indicate that a spike informs an ADR."
        ),
        "category_heatmap": (
            "Spike composition by uncertainty category. Cell values indicate how many detected signals "
            "of each category activate each spike."
        ),
        "agent_heatmap": (
            "Spike composition by analytical responsibility agent. Agents are inferred from the signal taxonomy."
        ),
        "dependency_table": (
            "Spike--ADR dependency table. Each row shows a candidate spike, its priority, "
            "the uncertainty categories that triggered it, the ADR skeletons it informs, and any blocking relation."
        ),
        "bipartite_graph": (
            "Original bipartite Spike--ADR dependency graph. This view is kept as a complementary artifact."
        ),
    }

    order = [
        "dependency_table",
        "layered_process",
        "traceability_matrix",
        "category_heatmap",
        "agent_heatmap",
        "bipartite_graph",
    ]

    parts = [r"\section{Visual Traceability Artifacts}"]
    parts.append(
        "This section includes compact visual artifacts that complement the original Spike--ADR graph. "
        "The matrix and heatmap views are intended to improve readability when the bipartite graph contains long edges."
    )

    for key in order:
        path = graph_paths.get(key)
        if not path:
            continue
        path = Path(path).as_posix()
        caption = captions.get(key, f"Generated visual artifact: {key}.")
        label = "fig:" + key.replace("_", "-")
        width = r"0.98\linewidth"
        if key == "bipartite_graph":
            width = r"0.90\linewidth"
        if key == "dependency_table":
            width = r"0.98\linewidth"

        parts.append(rf"""
\begin{{figure}}[H]
\centering
\includegraphics[width={width}]{{{latex_escape(path)}}}
\caption{{{latex_escape(caption)}}}
\label{{{label}}}
\end{{figure}}
""".strip())

    return "\n\n".join(parts)



def _render_graph_figure(graph_path: Union[str, Path]) -> str:
    graph_path = Path(graph_path)
    # LaTeX path relative-friendly: keep POSIX separators
    path = graph_path.as_posix()
    return rf"""
\section{{Spike--ADR Dependency Graph}}

\begin{{figure}}[H]
\centering
\includegraphics[width=0.95\linewidth]{{{latex_escape(path)}}}
\caption{{Generated Spike--ADR dependency graph.}}
\label{{fig:spike_adr_graph}}
\end{{figure}}
""".strip()


def _render_signals_table(data: Dict[str, Any]) -> str:
    signals = data.get("signals", [])
    if not signals:
        return r"\section{Detected Uncertainty Signals}\nNo uncertainty signals were detected."

    rows = []
    for s in signals:
        rows.append(
            rf"{latex_escape(s.get('id', ''))} & "
            rf"{latex_escape(short(s.get('signal_type', ''), 45))} & "
            rf"{latex_escape(short(s.get('source_section', ''), 25))} & "
            rf"{latex_escape(short(s.get('implicit_decision', ''), 130))} & "
            rf"{latex_escape(short(s.get('uncertainty_statement', ''), 160))} \\"
        )

    return rf"""
\section{{Detected Uncertainty Signals}}

\begin{{longtable}}{{p{{1.0cm}} p{{2.5cm}} p{{1.8cm}} p{{5.0cm}} p{{5.4cm}}}}
\caption{{Detected architectural uncertainty signals.}}
\label{{tab:signals}}\\
\toprule
\textbf{{ID}} & \textbf{{Type}} & \textbf{{Source}} & \textbf{{Implicit decision}} & \textbf{{Uncertainty}} \\
\midrule
\endfirsthead
\toprule
\textbf{{ID}} & \textbf{{Type}} & \textbf{{Source}} & \textbf{{Implicit decision}} & \textbf{{Uncertainty}} \\
\midrule
\endhead
{chr(10).join(rows)}
\bottomrule
\end{{longtable}}
""".strip()


def _find_adr_for_spike(adrs: List[Dict[str, Any]], spike_id: str) -> Optional[Dict[str, Any]]:
    for adr in adrs:
        if spike_id in adr.get("spike_ids", []):
            return adr
    return None


def _render_spikes_and_adrs(data: Dict[str, Any]) -> str:
    spikes = data.get("spikes", [])
    adrs = data.get("adrs", [])

    if not spikes:
        return r"\section{Candidate Spikes and ADR Skeletons}\nNo spikes were generated."

    parts = [r"\section{Candidate Spikes and ADR Skeletons}"]

    compact_rows = []
    for spike in spikes:
        sid = spike.get("id", "")
        adr = _find_adr_for_spike(adrs, sid)
        compact_rows.append(
            rf"{latex_escape(sid)} & "
            rf"{latex_escape(short(spike.get('title', ''), 70))} & "
            rf"{latex_escape(spike.get('priority', ''))} & "
            rf"{latex_escape(adr.get('id', '---') if adr else '---')} \\"
        )

    parts.append(rf"""
\begin{{table}}[H]
\centering
\caption{{Compact list of candidate spikes and associated ADR skeletons.}}
\label{{tab:spikes_compact}}
\scriptsize
\begin{{tabularx}}{{\linewidth}}{{p{{2.2cm}} X p{{1.8cm}} p{{2.2cm}}}}
\toprule
\textbf{{Spike}} & \textbf{{Title}} & \textbf{{Priority}} & \textbf{{ADR}} \\
\midrule
{chr(10).join(compact_rows)}
\bottomrule
\end{{tabularx}}
\end{{table}}
""".strip())

    for spike in spikes:
        parts.append(_render_single_spike(spike, adrs))

    return "\n\n".join(parts)


def _render_single_spike(spike: Dict[str, Any], adrs: List[Dict[str, Any]]) -> str:
    sid = spike.get("id", "")
    adr = _find_adr_for_spike(adrs, sid)
    alternatives = spike.get("alternatives", [])

    alt_rows = []
    for alt in alternatives:
        alt_rows.append(
            rf"{latex_escape(short(alt.get('name', ''), 42))} & "
            rf"{latex_escape(short(alt.get('advantage', ''), 95))} & "
            rf"{latex_escape(short(alt.get('risk', ''), 95))} & "
            rf"{latex_escape(short(alt.get('evidence_required', ''), 110))} \\"
        )

    alt_table = ""
    if alt_rows:
        alt_table = rf"""
\subsubsection*{{Alternatives}}
\begin{{longtable}}{{p{{3.0cm}} p{{4.0cm}} p{{4.0cm}} p{{4.8cm}}}}
\toprule
\textbf{{Alternative}} & \textbf{{Advantage}} & \textbf{{Risk}} & \textbf{{Evidence required}} \\
\midrule
\endfirsthead
\toprule
\textbf{{Alternative}} & \textbf{{Advantage}} & \textbf{{Risk}} & \textbf{{Evidence required}} \\
\midrule
\endhead
{chr(10).join(alt_rows)}
\bottomrule
\end{{longtable}}
""".strip()

    adr_text = _render_adr_skeleton(adr) if adr else "No ADR skeleton associated."

    return rf"""
\subsection{{{latex_escape(sid)} --- {latex_escape(spike.get("title", ""))}}}

\textbf{{Priority:}} {latex_escape(spike.get("priority", ""))}

\textbf{{Signal IDs:}} {latex_escape(", ".join(spike.get("signal_ids", [])))}

\subsubsection*{{Implicit decision}}
{latex_paragraph(spike.get("implicit_decision", ""))}

\subsubsection*{{Uncertainty}}
{latex_paragraph(spike.get("uncertainty", ""))}

\subsubsection*{{Why it matters}}
{latex_paragraph(spike.get("why_it_matters", ""))}

{alt_table}

\subsubsection*{{Expected evidence}}
{latex_paragraph(spike.get("expected_evidence", ""))}

\subsubsection*{{ADR skeleton}}
{adr_text}
""".strip()


def _render_adr_skeleton(adr: Optional[Dict[str, Any]]) -> str:
    if not adr:
        return ""

    options = adr.get("considered_options", [])
    options_tex = "\n".join(rf"\item {latex_escape(opt)}" for opt in options) or r"\item No options recorded."

    return rf"""
\textbf{{ADR ID:}} {latex_escape(adr.get("id", ""))}

\textbf{{Title:}} {latex_escape(adr.get("title", ""))}

\textbf{{Status:}} {latex_escape(adr.get("status", ""))}

\textbf{{Associated spikes:}} {latex_escape(", ".join(adr.get("spike_ids", [])))}

\paragraph{{Context and problem}}
{latex_paragraph(adr.get("context", ""))}

\textbf{{Problem:}} {latex_paragraph(adr.get("problem", ""))}

\paragraph{{Considered options}}
\begin{{itemize}}
{options_tex}
\end{{itemize}}

\paragraph{{Decision}}
{latex_paragraph(adr.get("decision", ""))}

\paragraph{{Positive consequences}}
{latex_paragraph(adr.get("consequences_positive", ""))}

\paragraph{{Negative consequences / trade-offs}}
{latex_paragraph(adr.get("consequences_negative", ""))}

\paragraph{{Evidence}}
{latex_paragraph(adr.get("evidence", ""))}
""".strip()


def _render_graph_analysis(data: Dict[str, Any]) -> str:
    graph = data.get("graph_data", {}) or {}
    counts = graph.get("pattern_counts", {}) or {}
    metrics = graph.get("metrics", {}) or {}
    execution_order = graph.get("execution_order", []) or []

    if not graph:
        return r"\section{Graph Analysis}\nNo graph analysis was available."

    count_rows = "\n".join(
        rf"{latex_escape(k)} & {v} \\"
        for k, v in sorted(counts.items(), key=lambda kv: kv[0])
    ) or r"None & 0 \\"

    metric_rows = "\n".join(
        rf"{latex_escape(k)} & {latex_escape(v)} \\"
        for k, v in sorted(metrics.items(), key=lambda kv: kv[0])
    ) or r"None & --- \\"

    order_text = " $\\rightarrow$ ".join(latex_escape(x) for x in execution_order) if execution_order else "No suggested order."

    return rf"""
\section{{Graph Analysis}}

\begin{{minipage}}{{0.48\linewidth}}
\centering
\begin{{tabular}}{{lr}}
\toprule
\textbf{{Pattern}} & \textbf{{Count}} \\
\midrule
{count_rows}
\bottomrule
\end{{tabular}}
\captionof{{table}}{{Spike--ADR cardinality patterns.}}
\label{{tab:graph_patterns}}
\end{{minipage}}
\hfill
\begin{{minipage}}{{0.48\linewidth}}
\centering
\begin{{tabular}}{{lr}}
\toprule
\textbf{{Metric}} & \textbf{{Value}} \\
\midrule
{metric_rows}
\bottomrule
\end{{tabular}}
\captionof{{table}}{{Graph metrics.}}
\label{{tab:graph_metrics}}
\end{{minipage}}

\subsection*{{Suggested execution order}}

{order_text}
""".strip()


def _render_appendix_evaluation_template(data: Dict[str, Any]) -> str:
    return r"""
\appendix
\section{Evaluation Template}

Each candidate spike can be evaluated by the team using four dimensions:

\begin{itemize}
    \item \textbf{Relevance:} Does this uncertainty actually apply to the project?
    \item \textbf{Novelty:} Had the team already identified this uncertainty?
    \item \textbf{Actionability:} Can the spike be executed in the current or next sprint?
    \item \textbf{Impact:} Could the spike change an architectural decision?
\end{itemize}

A suggested architectural gap indicator is:

\[
\mathrm{ArchitecturalGap} = \mathrm{RelevanceRate} \times \mathrm{NoveltyRate}
\]

This indicator should be interpreted as a preliminary signal of undocumented architectural uncertainty, not as a definitive quality score.
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# Compilación PDF opcional
# ─────────────────────────────────────────────────────────────────────────────

def compile_latex_to_pdf(
    tex_path: Union[str, Path],
    engine: str = "pdflatex",
    runs: int = 2,
    stop_on_error: bool = False,
) -> Optional[Path]:
    """
    Compila el .tex a PDF si pdflatex/xelatex está instalado.

    Returns:
        Path del PDF si se generó correctamente; None si no está disponible o falla.
    """
    tex_path = Path(tex_path)
    if shutil.which(engine) is None:
        print(f"[latex_report] {engine} no está instalado o no está en PATH. Se generó solo el .tex.")
        return None

    cmd = [
        engine,
        "-interaction=nonstopmode",
        "-halt-on-error" if stop_on_error else "-file-line-error",
        tex_path.name,
    ]

    cwd = tex_path.parent
    ok = True
    for _ in range(max(1, runs)):
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            ok = False
            (cwd / f"{tex_path.stem}_compile.log").write_text(proc.stdout, encoding="utf-8")
            print(f"[latex_report] Error compilando. Revisa {tex_path.stem}_compile.log")
            break

    pdf_path = tex_path.with_suffix(".pdf")
    return pdf_path if ok and pdf_path.exists() else None


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="Genera un informe LaTeX/PDF editable desde result.json del pipeline Spike-ADR."
    )
    parser.add_argument("--result", required=True, help="Ruta al result.json generado por pipeline.py")
    parser.add_argument("--output", required=True, help="Ruta de salida del archivo .tex")
    parser.add_argument("--graph", default=None, help="Ruta opcional a graph.png")
    parser.add_argument("--title", default=None, help="Título opcional del informe")
    parser.add_argument("--author", default="Pipeline Spike--ADR", help="Autor mostrado en portada")
    parser.add_argument("--compile", action="store_true", help="Compilar PDF con pdflatex si está disponible")
    parser.add_argument("--engine", default="pdflatex", help="Motor LaTeX: pdflatex, xelatex, lualatex")
    args = parser.parse_args()

    data = load_result_json(args.result)
    tex_path = generate_latex_report(
        data,
        output_path=args.output,
        graph_path=args.graph,
        title=args.title,
        author=args.author,
    )
    print(f"[latex_report] LaTeX generado en: {tex_path}")

    if args.compile:
        pdf = compile_latex_to_pdf(tex_path, engine=args.engine)
        if pdf:
            print(f"[latex_report] PDF generado en: {pdf}")


if __name__ == "__main__":
    _cli()
