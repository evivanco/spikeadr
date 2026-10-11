"""
evaluate.py — Rúbrica de evaluación para el estudio empírico
=============================================================
Genera los instrumentos de evaluación que los equipos estudiantiles
completan al revisar los spikes y ADRs candidatos generados por el pipeline.

Propósito del paper:
  Los datos de esta rúbrica son la contribución empírica central.
  Permiten medir el "gap arquitectónico": la diferencia entre lo que
  el equipo cree haber considerado y lo que el pipeline revela.

Cuatro dimensiones de evaluación (Vivanco 2026):
  1. Relevancia   — ¿Esta incertidumbre existe realmente en nuestro proyecto?
  2. Novedad      — ¿Ya la habíamos identificado antes de leer este documento?
  3. Accionabilidad — ¿Podemos ejecutar este spike este sprint?
  4. Impacto      — Si ejecutamos el spike, ¿podría cambiar alguna decisión?

Salidas:
  - Archivo Markdown con la rúbrica para cada spike (para el equipo)
  - Archivo CSV template para que los equipos registren sus respuestas
  - Archivo JSON con la estructura de los datos para análisis estadístico
"""

from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import List, Dict, Any

from models import Spike, ADRSkeleton, PipelineResult


# ─── Escala de respuesta ──────────────────────────────────────────────────────

RELEVANCE_OPTIONS = {
    "1": "No relevante — Esta incertidumbre no aplica a nuestro proyecto",
    "2": "Parcialmente relevante — Aplica pero no es una preocupación actual",
    "3": "Relevante — Esta incertidumbre existe en nuestro proyecto",
    "4": "Muy relevante — Es una de nuestras principales preocupaciones",
}

NOVELTY_OPTIONS = {
    "1": "Ya identificada y resuelta — Tenemos evidencia documentada",
    "2": "Ya identificada, sin evidencia — Lo sabíamos pero no lo documentamos",
    "3": "Nueva para el equipo — No lo habíamos considerado",
    "4": "Nueva y crítica — No lo habíamos considerado y podría afectar el proyecto",
}

ACTIONABILITY_OPTIONS = {
    "1": "No ejecutable — No tenemos recursos para este spike este sprint",
    "2": "Ejecutable en 2-3 sprints — Requiere preparación significativa",
    "3": "Ejecutable este sprint — Tenemos los recursos necesarios",
    "4": "Ya ejecutándose — Estamos haciendo esto actualmente",
}

IMPACT_OPTIONS = {
    "1": "Sin impacto — El spike confirmaría la decisión actual sin cambios",
    "2": "Impacto menor — Podría ajustar detalles de implementación",
    "3": "Impacto significativo — Podría modificar una decisión arquitectónica",
    "4": "Impacto alto — Podría cambiar el stack o la arquitectura del sistema",
}


# ─── Generador de rúbrica Markdown ────────────────────────────────────────────

def generate_evaluation_rubric(
    result: PipelineResult,
    output_path: str,
) -> None:
    """
    Genera el documento Markdown de rúbrica para el equipo estudiantil.
    Un formulario por spike, con las 4 dimensiones y escala de respuesta.
    """
    project = result.project
    spikes  = result.spikes
    adrs    = result.adrs

    lines = [
        f"# Rúbrica de Evaluación — {project.project_name} ({project.group_id})",
        "",
        "> Este documento fue generado automáticamente por el pipeline Spike-ADR.",
        "> **Instrucciones**: Para cada spike, evalúen las 4 dimensiones.",
        "> Sean honestos. El objetivo no es validar lo que hicieron,",
        "> sino revelar lo que no sabían que no sabían.",
        "",
        "**Equipo**: ________________________________________________",
        "**Fecha de evaluación**: ____________________________________",
        "**Integrantes presentes**: __________________________________",
        "",
        "---",
        "",
    ]

    for i, spike in enumerate(spikes, start=1):
        adr = next((a for a in adrs if spike.id in a.spike_ids), None)
        adr_title = adr.title if adr else "—"

        lines.extend([
            f"## Spike {i} de {len(spikes)}: {spike.id}",
            f"**Título**: {spike.title}",
            f"**Prioridad asignada por pipeline**: {spike.priority}",
            f"**ADR asociado**: {adr.id if adr else '—'} — {adr_title}",
            "",
            "### Contexto del spike",
            "",
            f"**Decisión implícita detectada**:",
            f"> {spike.implicit_decision}",
            "",
            f"**Incertidumbre que debe resolver**:",
            f"> {spike.uncertainty}",
            "",
            f"**¿Por qué importa?**",
            f"> {spike.why_it_matters[:400]}",
            "",
            "### Alternativas que el pipeline identificó como no consideradas",
            "",
        ])

        for alt in spike.alternatives[:4]:
            lines.extend([
                f"- **{alt.name}**",
                f"  - Ventaja: {alt.advantage}",
                f"  - Riesgo: {alt.risk}",
                f"  - Evidencia: {alt.evidence_required}",
                "",
            ])

        lines.extend([
            "### Evaluación del equipo",
            "",
            "#### Dimensión 1 — Relevancia",
            "*¿Esta incertidumbre existe realmente en nuestro proyecto?*",
            "",
        ])
        for k, v in RELEVANCE_OPTIONS.items():
            lines.append(f"- [ ] **{k}** — {v}")

        lines.extend(["", "**Justificación**: _______________________________________________", ""])

        lines.extend([
            "#### Dimensión 2 — Novedad",
            "*¿Ya la habíamos identificado antes de leer este documento?*",
            "",
        ])
        for k, v in NOVELTY_OPTIONS.items():
            lines.append(f"- [ ] **{k}** — {v}")

        lines.extend(["", "**Evidencia de que ya la tenían identificada** (si aplica):",
                       "_______________________________________________", ""])

        lines.extend([
            "#### Dimensión 3 — Accionabilidad",
            "*¿Podemos ejecutar este spike este sprint?*",
            "",
        ])
        for k, v in ACTIONABILITY_OPTIONS.items():
            lines.append(f"- [ ] **{k}** — {v}")

        lines.extend(["", "**Plan de ejecución** (si accionable):",
                       "_______________________________________________", ""])

        lines.extend([
            "#### Dimensión 4 — Impacto arquitectónico",
            "*Si ejecutamos el spike, ¿podría cambiar alguna decisión?*",
            "",
        ])
        for k, v in IMPACT_OPTIONS.items():
            lines.append(f"- [ ] **{k}** — {v}")

        lines.extend([
            "",
            "**¿Qué decisión podría cambiar?**: _______________________________________________",
            "",
            "---",
            "",
        ])

    # Sección de cierre
    lines.extend([
        "## Reflexión final del equipo",
        "",
        "1. ¿Cuántos spikes resultaron ser **nuevos y críticos** para el equipo?",
        "   _______________________________________________",
        "",
        "2. ¿Qué spike tiene el mayor riesgo si **no** se ejecuta?",
        "   _______________________________________________",
        "",
        "3. ¿Qué decisión arquitectónica tomarían diferente si hubieran visto",
        "   este documento antes de elegir el stack tecnológico?",
        "   _______________________________________________",
        "",
        "4. ¿El pipeline identificó incertidumbres que el equipo considera",
        "   **incorrectas o no aplicables**? ¿Cuáles y por qué?",
        "   _______________________________________________",
        "",
        "---",
        "*Gracias por completar esta evaluación. Sus respuestas contribuyen",
        "a la investigación sobre generación automática de spikes arquitectónicos.*",
    ])

    Path(output_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"  [evaluate] Rúbrica guardada en {output_path}")


# ─── Generador de CSV para captura de datos ──────────────────────────────────

def generate_csv_template(
    result: PipelineResult,
    output_path: str,
) -> None:
    """
    Genera un CSV template donde los equipos registran sus respuestas
    de forma estructurada para análisis estadístico posterior.

    Columnas:
      project_name, group_id, spike_id, spike_title, signal_type,
      relevance (1-4), novelty (1-4), actionability (1-4), impact (1-4),
      justification, evaluator_notes
    """
    fieldnames = [
        "project_name", "group_id", "spike_id", "spike_title",
        "signal_types", "pipeline_priority",
        "relevance_score", "novelty_score", "actionability_score", "impact_score",
        "composite_score",
        "relevance_label", "novelty_label", "actionability_label", "impact_label",
        "justification", "would_execute", "decision_at_risk", "evaluator_notes",
    ]

    rows = []
    project = result.project

    for spike in result.spikes:
        # Obtener tipos de señal únicos
        signal_types = list(set(
            s.signal_type.value
            for s in result.signals
            if s.id in spike.signal_ids
        ))

        rows.append({
            "project_name":         project.project_name,
            "group_id":             project.group_id,
            "spike_id":             spike.id,
            "spike_title":          spike.title,
            "signal_types":         "; ".join(signal_types),
            "pipeline_priority":    spike.priority,
            "relevance_score":      "",   # a completar por el equipo
            "novelty_score":        "",
            "actionability_score":  "",
            "impact_score":         "",
            "composite_score":      "",   # calculado en análisis posterior
            "relevance_label":      "",
            "novelty_label":        "",
            "actionability_label":  "",
            "impact_label":         "",
            "justification":        "",
            "would_execute":        "",   # Sí / No / Tal vez
            "decision_at_risk":     "",   # nombre de la decisión que podría cambiar
            "evaluator_notes":      "",
        })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  [evaluate] CSV template guardado en {output_path}")


# ─── Análisis de resultados (post-evaluación) ────────────────────────────────

def analyze_evaluation_results(csv_path: str) -> Dict[str, Any]:
    """
    Analiza los resultados de la rúbrica completada por los equipos.
    Calcula el gap arquitectónico y métricas para el paper.

    Llama a esta función después de que los equipos completaron el CSV.

    Métricas calculadas:
      - precision:    % spikes con relevance ≥ 3
      - discovery:    % spikes con novelty ≥ 3 (nuevos para el equipo)
      - actionability:% spikes con actionability ≥ 3
      - impact:       % spikes con impact ≥ 3
      - architectural_gap: precision × discovery (spikes relevantes Y nuevos)
    """
    import statistics

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return {"error": "No hay datos en el CSV"}

    def safe_int(v: str) -> int:
        try:
            return int(v.strip())
        except (ValueError, AttributeError):
            return 0

    # Filtrar filas completadas
    completed = [r for r in rows if safe_int(r.get("relevance_score", "")) > 0]

    if not completed:
        return {"error": "No hay filas con datos completos"}

    relevance     = [safe_int(r["relevance_score"])     for r in completed]
    novelty       = [safe_int(r["novelty_score"])       for r in completed]
    actionability = [safe_int(r["actionability_score"]) for r in completed]
    impact        = [safe_int(r["impact_score"])        for r in completed]

    n = len(completed)
    precision_rate    = sum(1 for v in relevance     if v >= 3) / n
    discovery_rate    = sum(1 for v in novelty       if v >= 3) / n
    actionability_rate= sum(1 for v in actionability if v >= 3) / n
    impact_rate       = sum(1 for v in impact        if v >= 3) / n
    architectural_gap = precision_rate * discovery_rate

    # Por proyecto
    by_project: Dict[str, Dict] = {}
    for row in completed:
        proj = row.get("project_name", "unknown")
        by_project.setdefault(proj, {"relevance": [], "novelty": [], "n_spikes": 0})
        by_project[proj]["relevance"].append(safe_int(row["relevance_score"]))
        by_project[proj]["novelty"].append(safe_int(row["novelty_score"]))
        by_project[proj]["n_spikes"] += 1

    project_gaps = {}
    for proj, data in by_project.items():
        n_proj = data["n_spikes"]
        p = sum(1 for v in data["relevance"] if v >= 3) / n_proj
        d = sum(1 for v in data["novelty"] if v >= 3) / n_proj
        project_gaps[proj] = {
            "n_spikes_evaluated": n_proj,
            "precision": round(p, 3),
            "discovery": round(d, 3),
            "architectural_gap": round(p * d, 3),
        }

    return {
        "total_spikes_evaluated": n,
        "precision_rate":         round(precision_rate, 3),
        "discovery_rate":         round(discovery_rate, 3),
        "actionability_rate":     round(actionability_rate, 3),
        "impact_rate":            round(impact_rate, 3),
        "architectural_gap_score":round(architectural_gap, 3),
        "mean_relevance":         round(statistics.mean(relevance), 2),
        "mean_novelty":           round(statistics.mean(novelty), 2),
        "stdev_relevance":        round(statistics.stdev(relevance), 2) if n > 1 else 0,
        "stdev_novelty":          round(statistics.stdev(novelty), 2) if n > 1 else 0,
        "by_project":             project_gaps,
    }
