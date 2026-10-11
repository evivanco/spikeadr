"""
adr_generator.py — Generación de esqueletos ADR en formato MADR
===============================================================
Recibe spikes y produce ADRSkeleton objects listos para que los
equipos completen la decisión y la evidencia.

Formato: MADR (Markdown Architectural Decision Records)
Ref: https://adr.github.io/madr/

Cada ADR skeleton tiene:
  - Contexto lleno por el pipeline (del documento del proyecto)
  - Opciones consideradas llenas (del catálogo del pipeline)
  - Decisión, consecuencias y evidencia VACÍAS → el equipo las completa

El vacío pedagógico es intencional: el equipo debe confrontar
lo que no sabe y completar con evidencia real del spike.
"""

from __future__ import annotations
from typing import List, Dict, Tuple
from models import Spike, ADRSkeleton, UncertaintySignal, ProjectDocument


# ─── Plantillas de contexto por categoría de decisión ────────────────────────

CONTEXT_TEMPLATES: Dict[str, Tuple[str, str]] = {
    # (context_template, problem_template)
    "tflite|tensorflow|mobilenet|efficientnet|onnx|model": (
        "El proyecto requiere inferencia de un modelo de inteligencia artificial "
        "en condiciones de operación {conditions}. La selección del modelo y el "
        "framework de inferencia determina la latencia, el tamaño del APK/bundle, "
        "el consumo de batería y la accuracy sobre el dominio del proyecto.",
        "¿Qué modelo y framework de inferencia satisface los atributos de calidad "
        "del proyecto bajo las condiciones reales de operación?",
    ),
    "llama|llm|fine.?tuning|chatbot|modelo de lenguaje": (
        "El proyecto incorpora un modelo de lenguaje (LLM) para interacción "
        "en lenguaje natural. La selección del modelo, la estrategia de despliegue "
        "y el mecanismo de alineación determinan la latencia, la calidad de respuesta, "
        "los costos operativos y el cumplimiento de requisitos de privacidad.",
        "¿Qué LLM, en qué configuración de despliegue, satisface simultáneamente "
        "los requisitos de latencia, calidad clínica/funcional y privacidad de datos?",
    ),
    "docker|contenedor|sandbox|aislamiento": (
        "El proyecto requiere aislar sesiones de usuario para garantizar privacidad "
        "y seguridad. La estrategia de aislamiento afecta la latencia de inicio de sesión, "
        "el uso de recursos del servidor y el nivel de garantía de privacidad.",
        "¿Qué mecanismo de aislamiento de sesiones satisface los requisitos de "
        "privacidad con overhead compatible con el presupuesto de latencia del sistema?",
    ),
    "sqlite|supabase|sync|offline|sincronizaci": (
        "El proyecto opera en contextos de conectividad intermitente o nula. "
        "La estrategia de sincronización offline-first determina la consistencia "
        "de datos, la experiencia de usuario sin conexión y la complejidad del sistema.",
        "¿Cómo se garantiza la consistencia de datos entre el dispositivo y el servidor "
        "cuando la sincronización ocurre tras un período offline?",
    ),
    "pgcrypto|cifrado|luks|aes|encrypt": (
        "El proyecto maneja datos sensibles que requieren protección en reposo y "
        "en tránsito. La estrategia de cifrado debe satisfacer los requisitos legales "
        "aplicables sin comprometer los atributos de calidad de rendimiento.",
        "¿Qué estrategia de cifrado cumple los requisitos normativos del proyecto "
        "con el menor overhead sobre los atributos de rendimiento?",
    ),
    "qdrant|weaviate|vector|embedding|rag|semántico": (
        "El proyecto requiere búsqueda semántica sobre documentos o perfiles. "
        "La selección del motor vectorial y el modelo de embeddings determina "
        "la precisión del matching, la latencia de búsqueda y los costos de infraestructura.",
        "¿Qué motor vectorial y modelo de embeddings satisface los requisitos de "
        "precisión, latencia y escalabilidad del proyecto?",
    ),
    "ley|normativa|gdpr|dpia|legal|19.628|21.719|dicom": (
        "El proyecto opera bajo restricciones legales que afectan el diseño "
        "arquitectónico. El incumplimiento hace que el sistema sea inoperable "
        "en el contexto institucional real, independientemente de su calidad técnica.",
        "¿La arquitectura propuesta cumple efectivamente los requisitos de la "
        "normativa aplicable? ¿Qué artefacto legal lo confirma?",
    ),
    "flutter|react native|kotlin|framework|móvil": (
        "El proyecto requiere una aplicación móvil multiplataforma. El framework "
        "elegido determina el acceso a APIs nativas, el rendimiento, la disponibilidad "
        "de plugins y la velocidad de desarrollo del equipo.",
        "¿Qué framework móvil multiplataforma permite implementar las funcionalidades "
        "requeridas (incluyendo los NFRs críticos) con el menor riesgo técnico?",
    ),
}

_DEFAULT_CONTEXT = (
    "Esta decisión arquitectónica afecta uno o más atributos de calidad del sistema. "
    "Fue tomada implícitamente sin documentar el razonamiento ni las alternativas consideradas.",
    "¿Cuál es la mejor opción técnica para este componente dado el contexto y los "
    "atributos de calidad del proyecto?",
)


def _match_context_template(spike: Spike) -> Tuple[str, str]:
    """Encuentra la plantilla de contexto más relevante para un spike."""
    text = (spike.title + " " + spike.uncertainty + " " +
            " ".join(a.name for a in spike.alternatives)).lower()

    best_key = None
    best_count = 0
    for key in CONTEXT_TEMPLATES:
        keywords = key.split("|")
        count = sum(1 for kw in keywords if kw in text)
        if count > best_count:
            best_count = count
            best_key = key

    if best_key and best_count > 0:
        return CONTEXT_TEMPLATES[best_key]
    return _DEFAULT_CONTEXT


def _enrich_context(
    context_tpl: str,
    spike: Spike,
    doc: ProjectDocument,
) -> str:
    """Enriquece la plantilla con datos del documento del proyecto."""
    # Extraer condiciones de operación relevantes del documento
    conditions = "las condiciones operativas del proyecto"

    # Buscar condiciones especiales en los atributos de calidad
    offline_mention = any(
        "offline" in qa.meta.lower() or "sin conexión" in qa.meta.lower()
        for qa in doc.quality_attributes
    )
    if offline_mention:
        conditions = "modo offline / conectividad intermitente"

    concurrent_match = None
    for qa in doc.quality_attributes:
        import re
        m = re.search(r"(\d+)\s*usuarios?\s*concurrentes?", qa.meta, re.IGNORECASE)
        if m:
            concurrent_match = m.group(0)
            break
    if concurrent_match:
        conditions = f"{concurrent_match} en producción"

    return context_tpl.replace("{conditions}", conditions)


def _build_considered_options(spike: Spike) -> List[str]:
    """
    Construye la lista de opciones consideradas para el ADR.
    Incluye las alternativas del catálogo + marca la opción actual del equipo.
    """
    options = []
    # La primera opción es la que el equipo eligió (sin saberlo)
    implicit_tech = spike.implicit_decision.split("'")[1] if "'" in spike.implicit_decision else "Opción actual (no documentada)"
    options.append(f"{implicit_tech} *(elección implícita del equipo — sin ADR)*")
    for alt in spike.alternatives:
        options.append(f"{alt.name} — {alt.advantage[:80]}")
    return options


def generate_adrs(
    spikes: List[Spike],
    doc: ProjectDocument,
) -> List[ADRSkeleton]:
    """
    Genera esqueletos ADR para cada spike o conjunto de spikes relacionados.

    Args:
        spikes: Lista de spikes generados por spike_generator.
        doc:    Documento del proyecto (para contexto).

    Returns:
        Lista de ADRSkeleton listos para completar por el equipo.
    """
    print(f"  [adr_generator] Generando ADRs para {doc.project_name} …")

    adrs: List[ADRSkeleton] = []
    prefix = doc.project_name[:3].upper()

    for i, spike in enumerate(spikes, start=1):
        context_tpl, problem = _match_context_template(spike)
        context = _enrich_context(context_tpl, spike, doc)
        options = _build_considered_options(spike)

        adr_id = f"ADR-{prefix}-{i:02d}"

        # Determinar título descriptivo del ADR
        title = _build_adr_title(spike)

        # Evidence hint (apunta al spike correspondiente)
        evidence_hint = (
            f"<!-- COMPLETAR: adjuntar resultados de {spike.id}.\n"
            f"     El spike debe producir: {spike.expected_evidence[:200]} -->"
        )

        adr = ADRSkeleton(
            id=adr_id,
            title=title,
            spike_ids=[spike.id],
            context=context,
            problem=problem,
            considered_options=options,
            status="Propuesto",
            decision="<!-- COMPLETAR: ¿qué opción eligieron y por qué? -->",
            consequences_positive="<!-- COMPLETAR: beneficios de la decisión -->",
            consequences_negative=(
                "<!-- COMPLETAR: trade-offs aceptados y riesgos residuales -->"
            ),
            evidence=evidence_hint,
        )
        adrs.append(adr)

        # Actualizar el spike con el ID del ADR generado
        spike.feeds_adr_ids = [adr_id]

    print(f"    → {len(adrs)} ADRs generados")
    return adrs


def _build_adr_title(spike: Spike) -> str:
    """Construye el título del ADR desde el título del spike."""
    # Remover prefijo "Validación de" y convertir a estilo ADR
    title = spike.title
    title = title.replace("Validación de ", "").replace("validación de ", "")
    title = title.replace(" — ", ": ")
    # Capitalizar primera letra
    return title[:1].upper() + title[1:] if title else "Decisión arquitectónica sin título"


def render_adr_markdown(adr: ADRSkeleton, spike: Spike) -> str:
    """
    Renderiza un ADR completo en Markdown, incluyendo el contexto del spike.
    Produce el documento que se entrega al equipo estudiantil.
    """
    options_md = "\n".join(f"- {opt}" for opt in adr.considered_options)
    spike_alts_md = "\n".join(
        f"| {a.name} | {a.advantage} | {a.risk} | {a.evidence_required} |"
        for a in spike.alternatives
    )
    spike_refs = ", ".join(adr.spike_ids)

    return f"""# {adr.id}: {adr.title}

**Estado**: {adr.status}
**Spikes asociados**: {spike_refs}
**Prioridad del spike**: {spike.priority}

---

## Contexto y problema

{adr.context}

**{adr.problem}**

---

## Decisión implícita detectada

> {spike.implicit_decision}

*Esta decisión fue tomada sin documentar el razonamiento ni las alternativas.*
*El spike {spike_refs} debe producir la evidencia que la respalde o la revierta.*

---

## Incertidumbre que debe resolver el spike

> {spike.uncertainty}

### ¿Por qué importa resolver esto antes de implementar?

{spike.why_it_matters}

---

## Opciones consideradas

{options_md}

### Detalle de alternativas no consideradas en el documento

| Alternativa | Ventaja | Riesgo | Evidencia requerida |
|---|---|---|---|
{spike_alts_md}

---

## Decisión tomada

{adr.decision}

## Consecuencias positivas

{adr.consequences_positive}

## Consecuencias negativas / trade-offs aceptados

{adr.consequences_negative}

## Evidencia que respalda esta decisión

{adr.evidence}

---

## Evidencia esperada del spike

{spike.expected_evidence}

---

*Generado automáticamente por el pipeline Spike-ADR.*
*El equipo debe completar las secciones marcadas con `<!-- COMPLETAR -->`*
*después de ejecutar el spike correspondiente.*
"""
