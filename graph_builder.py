"""
graph_builder.py — Construcción del grafo N:M Spike ↔ ADR
===========================================================
Construye y analiza el grafo de dependencias entre spikes y ADRs
para un proyecto, identificando los patrones de cardinalidad.

El grafo es dirigido: spike → ADR (spike informa ADR)
                      spike → spike (spike bloquea spike)

Salidas:
  - Objeto NetworkX DiGraph
  - Análisis de patrones N:M
  - Export a DOT (Graphviz) y JSON

Dependencias: networkx, matplotlib (para visualización)
"""

from __future__ import annotations
from typing import List, Dict, Any, Tuple
from collections import defaultdict, Counter

import networkx as nx

from models import Spike, ADRSkeleton, SpikeADRPattern, PipelineResult


# ─── Construcción del grafo ───────────────────────────────────────────────────

def build_graph(
    spikes: List[Spike],
    adrs: List[ADRSkeleton],
) -> nx.DiGraph:
    """
    Construye un grafo dirigido con:
      - Nodos SPIKE y ADR
      - Aristas spike → ADR  (tipo: "informs")
      - Aristas spike → spike (tipo: "blocks")

    Atributos de nodo:
      - node_type: "spike" | "adr"
      - priority / status
      - label para visualización

    Returns:
        NetworkX DiGraph listo para análisis y exportación.
    """
    G = nx.DiGraph()

    # ── Añadir nodos spike ───────────────────────────────────────────────────
    for spike in spikes:
        G.add_node(
            spike.id,
            node_type="spike",
            label=f"{spike.id}\n{spike.title[:30]}",
            priority=spike.priority,
            signal_count=len(spike.signal_ids),
            title=spike.title,
        )

    # ── Añadir nodos ADR ─────────────────────────────────────────────────────
    for adr in adrs:
        G.add_node(
            adr.id,
            node_type="adr",
            label=f"{adr.id}\n{adr.title[:30]}",
            status=adr.status,
            title=adr.title,
        )

    # ── Aristas spike → ADR (informs) ────────────────────────────────────────
    for spike in spikes:
        for adr_id in spike.feeds_adr_ids:
            if G.has_node(adr_id):
                G.add_edge(spike.id, adr_id, edge_type="informs", weight=1)

    # ── Aristas spike → spike (blocks) ───────────────────────────────────────
    for spike in spikes:
        for blocked_id in spike.blocks_spike_ids:
            if G.has_node(blocked_id):
                G.add_edge(spike.id, blocked_id, edge_type="blocks", weight=2)

    return G


# ─── Análisis de patrones N:M ────────────────────────────────────────────────

def analyze_patterns(G: nx.DiGraph) -> Dict[str, Any]:
    """
    Identifica los patrones de cardinalidad Spike ↔ ADR presentes en el grafo.

    Patrones según Tabla 3 de Vera-Rivera et al. extendida:
      0S→0A  Clarificación sin decisión
      0S→1A  Policy ADR (sin spike)
      1S→0A  Learning spike (sin ADR)
      1S→1A  Focused decision
      NS→1A  Aggregated evidence
      1S→NA  Decision cascade
      NS→NA  Complex evolution

    Returns:
        Dict con conteo de patrones, métricas del grafo y lista de instancias.
    """
    spike_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "spike"]
    adr_nodes   = [n for n, d in G.nodes(data=True) if d.get("node_type") == "adr"]

    pattern_instances: List[Dict] = []
    pattern_counts = Counter()

    # ── Analizar cada ADR: ¿cuántos spikes lo informan? ─────────────────────
    for adr_id in adr_nodes:
        informing_spikes = [
            src for src, dst, d in G.in_edges(adr_id, data=True)
            if d.get("edge_type") == "informs"
            and G.nodes[src].get("node_type") == "spike"
        ]
        n_spikes = len(informing_spikes)

        if n_spikes == 0:
            pattern = SpikeADRPattern.ZERO_TO_ONE
        elif n_spikes == 1:
            # Verificar si ese spike informa sólo este ADR
            adr_count = sum(
                1 for _, dst, d in G.out_edges(informing_spikes[0], data=True)
                if d.get("edge_type") == "informs"
            )
            pattern = SpikeADRPattern.ONE_TO_ONE if adr_count == 1 \
                      else SpikeADRPattern.ONE_TO_MANY
        else:
            pattern = SpikeADRPattern.MANY_TO_ONE

        pattern_counts[pattern.value] += 1
        pattern_instances.append({
            "adr_id": adr_id,
            "informing_spikes": informing_spikes,
            "pattern": pattern.value,
            "n_spikes_to_1_adr": n_spikes,
        })

    # ── Analizar cada spike: ¿a cuántos ADRs informa? ───────────────────────
    for spike_id in spike_nodes:
        informed_adrs = [
            dst for _, dst, d in G.out_edges(spike_id, data=True)
            if d.get("edge_type") == "informs"
        ]
        n_adrs = len(informed_adrs)

        if n_adrs == 0:
            pattern_counts[SpikeADRPattern.ONE_TO_ZERO.value] += 1
        elif n_adrs > 1:
            pattern_counts[SpikeADRPattern.ONE_TO_MANY.value] += 1
            pattern_instances.append({
                "spike_id": spike_id,
                "informed_adrs": informed_adrs,
                "pattern": SpikeADRPattern.ONE_TO_MANY.value,
                "n_adrs_from_1_spike": n_adrs,
            })

    # ── Métricas del grafo ───────────────────────────────────────────────────
    informs_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "informs"]
    blocks_edges  = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "blocks"]

    metrics = {
        "n_spikes": len(spike_nodes),
        "n_adrs": len(adr_nodes),
        "n_informs_edges": len(informs_edges),
        "n_blocks_edges": len(blocks_edges),
        "density": nx.density(G),
        "is_dag": nx.is_directed_acyclic_graph(G),
    }

    # Grado de entrada de ADRs (cuántos spikes los informan)
    adr_in_degrees = {adr: G.in_degree(adr) for adr in adr_nodes}
    if adr_in_degrees:
        metrics["max_spikes_per_adr"] = max(adr_in_degrees.values())
        metrics["avg_spikes_per_adr"] = sum(adr_in_degrees.values()) / len(adr_in_degrees)

    # Grado de salida de spikes (cuántos ADRs informan)
    spike_out_degrees = {s: sum(1 for _, dst, d in G.out_edges(s, data=True)
                                if d.get("edge_type") == "informs")
                         for s in spike_nodes}
    if spike_out_degrees:
        metrics["max_adrs_per_spike"] = max(spike_out_degrees.values())
        metrics["avg_adrs_per_spike"] = sum(spike_out_degrees.values()) / len(spike_out_degrees)

    return {
        "pattern_counts": dict(pattern_counts),
        "pattern_instances": pattern_instances,
        "metrics": metrics,
        "spike_nodes": spike_nodes,
        "adr_nodes": adr_nodes,
        "edges": [
            {"from": u, "to": v, "type": d.get("edge_type")}
            for u, v, d in G.edges(data=True)
        ],
    }


# ─── Ordenación topológica (ejecución sugerida) ────────────────────────────────

def suggest_execution_order(G: nx.DiGraph) -> List[str]:
    """
    Retorna el orden sugerido de ejecución de spikes usando
    ordenamiento topológico del subgrafo de bloqueos.

    Los spikes sin dependencias van primero.
    Los spikes que bloquean a otros van antes de sus bloqueados.
    """
    spike_subgraph = nx.DiGraph()
    for u, v, d in G.edges(data=True):
        u_type = G.nodes[u].get("node_type")
        v_type = G.nodes[v].get("node_type")
        if u_type == "spike" and v_type == "spike" and d.get("edge_type") == "blocks":
            spike_subgraph.add_edge(u, v)

    # Añadir spikes sin dependencias
    spike_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "spike"]
    for s in spike_nodes:
        if s not in spike_subgraph:
            spike_subgraph.add_node(s)

    try:
        order = list(nx.topological_sort(spike_subgraph))
    except nx.NetworkXUnfeasible:
        # Hay ciclos (inusual), devolver orden arbitrario
        order = spike_nodes

    return order


# ─── Exportación ──────────────────────────────────────────────────────────────

def export_to_dot(G: nx.DiGraph) -> str:
    """
    Exporta el grafo en formato DOT (Graphviz) para visualización.

    Uso:
        dot_str = export_to_dot(G)
        with open("graph.dot", "w") as f:
            f.write(dot_str)
        # Luego: dot -Tpng graph.dot -o graph.png
    """
    lines = ["digraph spike_adr {", "  rankdir=LR;",
             '  node [fontname="Helvetica" fontsize=10];',
             '  edge [fontsize=9];', ""]

    # Nodos
    for node, data in G.nodes(data=True):
        node_type = data.get("node_type", "unknown")
        label = data.get("label", node).replace("\n", "\\n")
        if node_type == "spike":
            priority = data.get("priority", "Media")
            color = {"Alta": "#e74c3c", "Media": "#f39c12", "Baja": "#27ae60"}.get(priority, "#95a5a6")
            lines.append(
                f'  "{node}" [label="{label}" shape=box '
                f'style=filled fillcolor="{color}" fontcolor=white];'
            )
        elif node_type == "adr":
            lines.append(
                f'  "{node}" [label="{label}" shape=ellipse '
                f'style=filled fillcolor="#3498db" fontcolor=white];'
            )

    lines.append("")

    # Aristas
    for u, v, data in G.edges(data=True):
        edge_type = data.get("edge_type", "")
        if edge_type == "informs":
            lines.append(f'  "{u}" -> "{v}" [label="informs" color="#2c3e50"];')
        elif edge_type == "blocks":
            lines.append(f'  "{u}" -> "{v}" [label="blocks" color="#e74c3c" style=dashed];')

    lines.append("}")
    return "\n".join(lines)


def export_graph_json(G: nx.DiGraph) -> Dict:
    """Exporta el grafo a un dict serializable a JSON."""
    return {
        "nodes": [
            {"id": n, **{k: v for k, v in d.items() if k != "label"}}
            for n, d in G.nodes(data=True)
        ],
        "edges": [
            {"source": u, "target": v, "type": d.get("edge_type")}
            for u, v, d in G.edges(data=True)
        ],
    }


def visualize_graph(G: nx.DiGraph, output_path: str, title: str = "Spike-ADR Graph") -> None:
    """
    Genera una visualización PNG del grafo usando matplotlib.
    Requiere: matplotlib instalado.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("  [graph_builder] matplotlib no disponible. Saltando visualización.")
        return

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    # Posiciones: spikes a la izquierda, ADRs a la derecha
    spike_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "spike"]
    adr_nodes   = [n for n, d in G.nodes(data=True) if d.get("node_type") == "adr"]

    pos = {}
    for i, node in enumerate(spike_nodes):
        pos[node] = (-1.5, -i * 1.2)
    for i, node in enumerate(adr_nodes):
        pos[node] = (1.5, -i * 1.2 - 0.6)

    # Colores por prioridad (spikes) y status (ADRs)
    spike_colors = []
    for n in spike_nodes:
        p = G.nodes[n].get("priority", "Media")
        spike_colors.append({"Alta": "#e74c3c", "Media": "#f39c12", "Baja": "#27ae60"}.get(p, "#95a5a6"))

    adr_color = "#3498db"

    nx.draw_networkx_nodes(G, pos, nodelist=spike_nodes, node_color=spike_colors,
                           node_size=1500, node_shape="s", ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=adr_nodes, node_color=adr_color,
                           node_size=1500, node_shape="o", ax=ax)

    labels = {n: n for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=7, ax=ax)

    informs = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "informs"]
    blocks  = [(u, v) for u, v, d in G.edges(data=True) if d.get("edge_type") == "blocks"]

    nx.draw_networkx_edges(G, pos, edgelist=informs, edge_color="#2c3e50",
                           arrows=True, arrowsize=15, ax=ax)
    nx.draw_networkx_edges(G, pos, edgelist=blocks, edge_color="#e74c3c",
                           style="dashed", arrows=True, arrowsize=15, ax=ax)

    legend_elements = [
        mpatches.Patch(color="#e74c3c", label="Spike Alta prioridad"),
        mpatches.Patch(color="#f39c12", label="Spike Media prioridad"),
        mpatches.Patch(color="#3498db", label="ADR"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=9)
    ax.axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [graph_builder] Grafo guardado en {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Visualizaciones V2 más legibles
# ─────────────────────────────────────────────────────────────────────────────

def _require_matplotlib():
    """Carga matplotlib en modo headless."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        print("  [graph_builder] matplotlib no disponible. Saltando visualización.")
        return None


def visualize_traceability_matrix(
    G: nx.DiGraph,
    output_path: str,
    title: str = "Spike--ADR traceability matrix",
) -> None:
    """
    Genera una matriz Spike × ADR.

    Reemplaza al grafo bipartito cuando hay muchas líneas largas. Es ideal
    para leer relaciones 1S→1A, 1S→NA, NS→1A y NS→NA.
    """
    plt = _require_matplotlib()
    if plt is None:
        return

    import numpy as np

    spike_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "spike"]
    adr_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "adr"]

    if not spike_nodes or not adr_nodes:
        print("  [graph_builder] No hay spikes o ADRs para matriz de trazabilidad.")
        return

    matrix = np.zeros((len(spike_nodes), len(adr_nodes)))
    for i, s in enumerate(spike_nodes):
        for j, a in enumerate(adr_nodes):
            if G.has_edge(s, a) and G.edges[s, a].get("edge_type") == "informs":
                matrix[i, j] = 1

    fig_w = max(8, min(18, 2 + 0.6 * len(adr_nodes) + 0.28 * max(len(x) for x in spike_nodes)))
    fig_h = max(6.0, min(18, 2.2 + 0.60 * len(spike_nodes)))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    ax.imshow(matrix, aspect="auto", cmap="Greys", vmin=0, vmax=1)

    ax.set_title(title, fontsize=18, fontweight="bold", pad=16)
    ax.set_xlabel("ADR skeletons", fontsize=13)
    ax.set_ylabel("Candidate spikes", fontsize=13)

    ax.set_xticks(range(len(adr_nodes)))
    ax.set_xticklabels(adr_nodes, rotation=45, ha="right", fontsize=11)
    ax.set_yticks(range(len(spike_nodes)))
    ax.set_yticklabels(spike_nodes, fontsize=11)

    # Grid estilo matriz
    ax.set_xticks([x - 0.5 for x in range(1, len(adr_nodes))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(spike_nodes))], minor=True)
    ax.grid(which="minor", color="lightgray", linestyle="-", linewidth=0.8)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Marcas visibles
    for i in range(len(spike_nodes)):
        for j in range(len(adr_nodes)):
            if matrix[i, j] == 1:
                ax.text(j, i, "●", ha="center", va="center", fontsize=18)

    # Resumen en pie
    n_edges = int(matrix.sum())
    ax.text(
        0.0, -0.16,
        f"Traceability edges: {n_edges}. Filled cells indicate that a spike informs an ADR.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11,
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"  [graph_builder] Matriz Spike--ADR guardada en {output_path}")


def _short_signal_type(signal_type: str) -> str:
    text = str(signal_type)
    if "Tipo I" in text:
        return "T-I Tech"
    if "Tipo II" in text:
        return "T-II QA"
    if "Tipo III" in text:
        return "T-III Norm"
    if "Tipo IV" in text:
        return "T-IV Integr."
    if "Tipo V" in text:
        return "T-V Local"
    return text[:12]


def _infer_agent_from_signal_type(signal_type: str) -> str:
    text = str(signal_type)
    if "Tipo I" in text:
        return "Evidence/Deployment"
    if "Tipo II" in text:
        return "QA/Criteria"
    if "Tipo III" in text:
        return "QA/Traceability"
    if "Tipo IV" in text:
        return "Interaction"
    if "Tipo V" in text:
        return "Requirement"
    return "Other"


def visualize_category_heatmap(
    result: PipelineResult,
    output_path: str,
    title: str = "Spike composition by uncertainty category",
) -> None:
    """
    Genera un heatmap Spike × categoría de incertidumbre.

    Muestra composición: qué tipos de señales activan cada spike.
    Usa las señales del PipelineResult y los signal_ids asociados a cada Spike.
    """
    plt = _require_matplotlib()
    if plt is None:
        return

    import numpy as np

    spikes = result.spikes
    signals = result.signals

    if not spikes or not signals:
        print("  [graph_builder] No hay spikes o señales para heatmap categórico.")
        return

    signal_by_id = {s.id: s for s in signals}
    categories = ["T-I Tech", "T-II QA", "T-III Norm", "T-IV Integr.", "T-V Local"]
    cat_index = {c: i for i, c in enumerate(categories)}

    matrix = np.zeros((len(spikes), len(categories)))

    for i, spike in enumerate(spikes):
        for sid in spike.signal_ids:
            signal = signal_by_id.get(sid)
            if not signal:
                continue
            cat = _short_signal_type(signal.signal_type.value if hasattr(signal.signal_type, "value") else signal.signal_type)
            if cat in cat_index:
                matrix[i, cat_index[cat]] += 1

    fig_w = 11.5
    fig_h = max(6.0, min(18, 2.2 + 0.60 * len(spikes)))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    im = ax.imshow(matrix, aspect="auto", cmap="Blues")

    ax.set_title(title, fontsize=18, fontweight="bold", pad=16)
    ax.set_xlabel("Uncertainty category", fontsize=13)
    ax.set_ylabel("Candidate spikes", fontsize=13)

    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories, rotation=25, ha="right", fontsize=11)
    ax.set_yticks(range(len(spikes)))
    ax.set_yticklabels([s.id for s in spikes], fontsize=11)

    # Grilla
    ax.set_xticks([x - 0.5 for x in range(1, len(categories))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(spikes))], minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.0)
    ax.tick_params(which="minor", bottom=False, left=False)

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(matrix[i, j])
            if value > 0:
                ax.text(j, i, str(value), ha="center", va="center", fontsize=12)

    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cbar.ax.set_ylabel("Signals", rotation=90, fontsize=11)

    ax.text(
        0.0, -0.18,
        "Categories: T-I technology feasibility; T-II quality threshold; "
        "T-III normative compliance; T-IV external integration; T-V local context.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11,
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"  [graph_builder] Heatmap categórico guardado en {output_path}")


def visualize_agent_heatmap(
    result: PipelineResult,
    output_path: str,
    title: str = "Spike composition by analytical agent",
) -> None:
    """
    Genera un heatmap Spike × agente analítico inferido.

    El pipeline actual no tiene todavía AgentAssessment explícito, por lo que
    esta visualización mapea tipos de señal a agentes de responsabilidad.
    """
    plt = _require_matplotlib()
    if plt is None:
        return

    import numpy as np

    spikes = result.spikes
    signals = result.signals
    if not spikes or not signals:
        return

    signal_by_id = {s.id: s for s in signals}
    agents = [
        "Requirement",
        "QA/Criteria",
        "Interaction",
        "Evidence/Deployment",
        "QA/Traceability",
        "Other",
    ]
    agent_index = {a: i for i, a in enumerate(agents)}
    matrix = np.zeros((len(spikes), len(agents)))

    for i, spike in enumerate(spikes):
        for sid in spike.signal_ids:
            signal = signal_by_id.get(sid)
            if not signal:
                continue
            st = signal.signal_type.value if hasattr(signal.signal_type, "value") else signal.signal_type
            agent = _infer_agent_from_signal_type(st)
            if agent not in agent_index:
                agent = "Other"
            matrix[i, agent_index[agent]] += 1

    fig_w = 12.5
    fig_h = max(6.0, min(18, 2.2 + 0.60 * len(spikes)))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(matrix, aspect="auto", cmap="Purples")

    ax.set_title(title, fontsize=18, fontweight="bold", pad=16)
    ax.set_xlabel("Analytical responsibility agent", fontsize=13)
    ax.set_ylabel("Candidate spikes", fontsize=13)

    ax.set_xticks(range(len(agents)))
    ax.set_xticklabels(agents, rotation=25, ha="right", fontsize=11)
    ax.set_yticks(range(len(spikes)))
    ax.set_yticklabels([s.id for s in spikes], fontsize=11)

    ax.set_xticks([x - 0.5 for x in range(1, len(agents))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(spikes))], minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.0)
    ax.tick_params(which="minor", bottom=False, left=False)

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = int(matrix[i, j])
            if value > 0:
                ax.text(j, i, str(value), ha="center", va="center", fontsize=12)

    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cbar.ax.set_ylabel("Signals", rotation=90, fontsize=11)

    ax.text(
        0.0, -0.18,
        "Agents are inferred from the signal taxonomy. They are analytical responsibility units, "
        "not autonomous software agents.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=11,
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"  [graph_builder] Heatmap de agentes guardado en {output_path}")


def visualize_layered_process(
    result: PipelineResult,
    output_path: str,
    title: str = "Layered Spike--ADR decision process",
) -> None:
    """
    Genera un diagrama por capas con fuente grande para PDF/LaTeX.
    """
    plt = _require_matplotlib()
    if plt is None:
        return

    import matplotlib.patches as patches
    from collections import Counter

    signals = result.signals
    spikes = result.spikes
    adrs = result.adrs
    graph = result.graph_data or {}

    signal_counts = Counter(_short_signal_type(s.signal_type.value if hasattr(s.signal_type, "value") else s.signal_type) for s in signals)
    priority_counts = Counter(s.priority for s in spikes)
    pattern_counts = graph.get("pattern_counts", {}) or {}

    fig, ax = plt.subplots(figsize=(17.5, 9.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(title, fontsize=21, fontweight="bold", pad=18)

    def box(x, y, w, h, header, lines, face="#f7f7f7"):
        rect = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.014,rounding_size=0.014",
            linewidth=1.5,
            edgecolor="#333333",
            facecolor=face,
        )
        ax.add_patch(rect)
        ax.text(x + w/2, y + h - 0.055, header, ha="center", va="top", fontsize=14, fontweight="bold")
        yy = y + h - 0.125
        for line in lines[:7]:
            ax.text(x + 0.022, yy, line, ha="left", va="top", fontsize=12)
            yy -= 0.065
        return rect

    def arrow(x1, y1, x2, y2, label=None):
        arr = patches.FancyArrowPatch(
            (x1, y1), (x2, y2),
            arrowstyle="->",
            mutation_scale=20,
            linewidth=1.4,
            color="#333333",
        )
        ax.add_patch(arr)
        if label:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.04, label, ha="center", va="bottom", fontsize=11)

    sig_lines = [f"{k}: {v}" for k, v in sorted(signal_counts.items())] or ["No signals"]
    agent_lines = [
        "Requirement",
        "QA / Criteria",
        "Interaction",
        "Evidence / Deployment",
        "ADR Traceability",
    ]
    spike_lines = [f"{k}: {v}" for k, v in sorted(priority_counts.items())] or ["No spikes"]
    adr_lines = [f"ADR skeletons: {len(adrs)}", f"Evidence links: {graph.get('metrics', {}).get('n_informs_edges', 0)}"]
    pattern_lines = [f"{k}: {v}" for k, v in sorted(pattern_counts.items())] or ["No patterns"]

    xs = [0.035, 0.235, 0.435, 0.635, 0.815]
    w = 0.155
    h = 0.58
    y = 0.27

    box(xs[0], y, w, h, "Signals", sig_lines, "#F2F2F2")
    box(xs[1], y, w, h, "Agents", agent_lines, "#F7F7F7")
    box(xs[2], y, w, h, "Spikes / Evidence", spike_lines, "#F2F2F2")
    box(xs[3], y, w, h, "ADRs", adr_lines, "#F7F7F7")
    box(xs[4], y, w, h, "Patterns", pattern_lines, "#F2F2F2")

    for i in range(4):
        arrow(xs[i] + w, y + h/2, xs[i+1], y + h/2)

    arrow(xs[4] + w*0.70, y - 0.045, xs[0] + w*0.35, y - 0.045, "learning loop")

    ax.text(
        0.5, 0.12,
        "Interpretation: agile artifacts generate uncertainty signals; analytical agents classify them; "
        "spikes define evidence needs; ADRs preserve rationale and decision traceability.",
        ha="center",
        va="center",
        fontsize=12,
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"  [graph_builder] Diagrama por capas guardado en {output_path}")




def visualize_bipartite_dependency_table(
    result: PipelineResult,
    G: nx.DiGraph,
    output_path: str,
    title: str = "Spike--ADR dependency table",
) -> None:
    """
    Genera una tabla visual Spike--ADR con fuente grande para PDF/LaTeX.

    Esta versión está optimizada para que sea legible cuando se inserta en
    report.tex. El grafo bipartito original queda como artefacto complementario.
    """
    plt = _require_matplotlib()
    if plt is None:
        return

    spikes = result.spikes
    adrs = result.adrs
    signals = result.signals

    if not spikes:
        print("  [graph_builder] No hay spikes para tabla bipartita.")
        return

    signal_by_id = {s.id: s for s in signals}

    rows = []
    for spike in spikes:
        signal_types = []
        for sid in spike.signal_ids:
            signal = signal_by_id.get(sid)
            if signal:
                st = signal.signal_type.value if hasattr(signal.signal_type, "value") else signal.signal_type
                signal_types.append(_short_signal_type(st))
        signal_summary = ", ".join(sorted(set(signal_types))) if signal_types else "—"

        adr_ids = spike.feeds_adr_ids or [
            a.id for a in adrs if spike.id in getattr(a, "spike_ids", [])
        ]
        adr_summary = ", ".join(adr_ids) if adr_ids else "—"

        blocked = ", ".join(spike.blocks_spike_ids) if spike.blocks_spike_ids else "—"

        rows.append([
            spike.id,
            str(spike.priority),
            signal_summary,
            adr_summary,
            blocked,
        ])

    # Más alto y más ancho para evitar letra microscópica en PDF.
    fig_h = max(5.2, min(22, 1.8 + 0.72 * len(rows)))
    fig_w = 16.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    ax.set_title(title, fontsize=20, fontweight="bold", pad=18)

    col_labels = ["Spike", "Priority", "Signal categories", "Informs ADR", "Blocks spike"]
    col_widths = [0.16, 0.14, 0.30, 0.22, 0.18]

    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        colWidths=col_widths,
        loc="center",
        cellLoc="left",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(13)
    table.scale(1.0, 2.15)

    # Estilo simple y legible
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#BDBDBD")
        cell.set_linewidth(0.8)
        cell.PAD = 0.10
        if r == 0:
            cell.set_text_props(weight="bold", color="black", fontsize=13.5)
            cell.set_facecolor("#E8E8E8")
        else:
            priority = rows[r-1][1].lower()
            if c == 1:
                if "alta" in priority or "high" in priority:
                    cell.set_facecolor("#FDECEA")
                elif "media" in priority or "medium" in priority:
                    cell.set_facecolor("#FFF4E0")
                else:
                    cell.set_facecolor("#F7F7F7")
            elif r % 2 == 0:
                cell.set_facecolor("#FAFAFA")
            else:
                cell.set_facecolor("white")

    ax.text(
        0.0,
        0.02,
        "Interpretation: each row represents a candidate spike; the table shows which ADR skeletons it informs and which uncertainty categories triggered it.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=12,
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close()
    print(f"  [graph_builder] Tabla Spike--ADR guardada en {output_path}")


def generate_visual_artifacts(
    result: PipelineResult,
    G: nx.DiGraph,
    output_dir: str,
    project_name: str = "",
    group_id: str = "",
    include_project_in_titles: bool = False,
) -> Dict[str, str]:
    """
    Genera todas las visualizaciones V2 y retorna un diccionario con rutas relativas.

    Por defecto NO incluye el nombre del proyecto/archivo en los títulos, porque en
    batch esos nombres pueden ser demasiado largos y reducen la legibilidad.

    Archivos:
      - graph.png                         grafo bipartito original
      - graph_traceability_matrix.png     matriz Spike × ADR
      - graph_category_heatmap.png        heatmap Spike × categorías de incertidumbre
      - graph_agent_heatmap.png           heatmap Spike × agentes analíticos
      - graph_layered_process.png         flujo por capas
    """
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    project_suffix = f": {project_name} ({group_id})" if include_project_in_titles and project_name and group_id else ""

    paths = {
        "dependency_table": "graph.png",
        "bipartite_graph": "graph_bipartite_original.png",
        "traceability_matrix": "graph_traceability_matrix.png",
        "category_heatmap": "graph_category_heatmap.png",
        "agent_heatmap": "graph_agent_heatmap.png",
        "layered_process": "graph_layered_process.png",
    }

    visualize_bipartite_dependency_table(
        result,
        G,
        str(out / paths["dependency_table"]),
        title=f"Spike--ADR dependency table{project_suffix}",
    )
    # Se conserva el grafo bipartito original como artefacto complementario.
    visualize_graph(
        G,
        str(out / paths["bipartite_graph"]),
        title=f"Spike--ADR graph{project_suffix}",
    )
    visualize_traceability_matrix(
        G,
        str(out / paths["traceability_matrix"]),
        title=f"Spike--ADR traceability matrix{project_suffix}",
    )
    visualize_category_heatmap(
        result,
        str(out / paths["category_heatmap"]),
        title=f"Spike composition by uncertainty category{project_suffix}",
    )
    visualize_agent_heatmap(
        result,
        str(out / paths["agent_heatmap"]),
        title=f"Spike composition by analytical agent{project_suffix}",
    )
    visualize_layered_process(
        result,
        str(out / paths["layered_process"]),
        title=f"Layered Spike--ADR process{project_suffix}",
    )

    return paths
