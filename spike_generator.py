"""
spike_generator.py — Generación de spikes candidatos desde señales
===================================================================
Recibe señales de incertidumbre y produce Spike objects con los
4 elementos pedagógicos:
  1. implicit_decision   — qué decidieron sin documentar
  2. uncertainty         — pregunta que el spike debe responder
  3. alternatives        — opciones no consideradas
  4. expected_evidence   — qué debe producir el spike

Catálogo de alternativas:
  El knowledge base está codificado como un diccionario de patrones
  de señal → lista de alternativas. Para el paper, este catálogo
  representa el conocimiento del instructor materializado en código.
"""

from __future__ import annotations
import re
from typing import List, Dict, Tuple, Optional
from models import (
    UncertaintySignal, Spike, Alternative,
    SignalType, SpikeADRPattern
)


# ─── Knowledge base: catálogo de alternativas por dominio ─────────────────────
# Estructura: keyword_pattern → [(name, advantage, risk, evidence_required)]

ALTERNATIVES_CATALOG: Dict[str, List[Tuple[str, str, str, str]]] = {

    # ── On-device AI / Edge inference ────────────────────────────────────────
    "tflite|tensorflow lite": [
        ("TFLite MobileNetV3",    "Liviano, bien soportado en Flutter",        "Menor accuracy en clases visualmente similares", "Benchmark latencia + accuracy en dispositivo real"),
        ("TFLite EfficientNet-Lite0","Mejor accuracy/tamaño que MobileNetV3",  "Ligeramente más lento en gama baja",              "Mismo benchmark, comparar con MobileNetV3"),
        ("ONNX Runtime Mobile",   "Framework agnóstico al modelo",             "Menor soporte nativo en Flutter",                 "Prueba de integración + overhead de conversión"),
        ("BirdNET (aves)",        "Especializado, fine-tuned en aves",         "Mayor tamaño de modelo, requiere adaptación",     "Test de accuracy sobre especies del proyecto"),
        ("CoreML (iOS)",          "Nativo iOS, menor latencia en Apple Silicon","Solo iOS, rompe la promesa multiplataforma",      "Benchmark iOS vs Android para balancear decisión"),
    ],
    "llama|mistral|gpt|llm|modelo de lenguaje": [
        ("LLaMA 3.2 1B",          "50-70% menos latencia que 3B, misma privacidad","Menor calidad de respuesta, mayor tasa de error", "Benchmark latencia 1B vs 3B con prompts clínicos"),
        ("Mistral 7B Instruct",   "Mejor calidad de respuesta que LLaMA 3B",   "Requiere GPU más potente, mayor costo",           "Benchmark latencia + calidad en GPU objetivo"),
        ("GPT-4o via API",        "Latencia ~1-3s, sin fine-tuning necesario", "Datos salen del servidor — problema normativo",   "Análisis legal + benchmar latencia API"),
        ("Streaming + LLaMA 3B",  "Primer token en ~1s, mejor UX percibida",  "Más complejidad en cliente, manejo de stream",    "Test de percepción subjetiva de latencia con usuarios"),
        ("Fine-tuning + output classifier","Doble capa de seguridad clínica",  "Mayor complejidad de entrenamiento y evaluación", "Evaluación clínica de 50 respuestas por profesional"),
    ],

    # ── Mobile frameworks ────────────────────────────────────────────────────
    "flutter|react native|kotlin|swift": [
        ("Flutter + Dart",        "Único codebase, buen soporte TFLite",       "Menor ecosistema de AI que RN en algunas áreas", "Comparar plugins disponibles para el caso de uso"),
        ("React Native + Vision Camera","Ecosistema maduro, fast-tflite plugin","Más overhead JS bridge para inferencia en tiempo real","Benchmark inferencia RN vs Flutter con mismo modelo"),
        ("Kotlin Multiplatform",  "Acceso nativo completo, máximo rendimiento","Dos bases de código UI (Android/iOS)",           "Prueba de concepto con la funcionalidad más crítica"),
        ("Expo + ONNX Runtime",   "Setup rápido, updates over-the-air",        "Restricciones de módulos nativos en Expo Go",    "Test de viabilidad con módulos nativos requeridos"),
    ],

    # ── Bases de datos y sincronización ─────────────────────────────────────
    "sqlite|supabase|postgresql|mongodb": [
        ("SQLite + Supabase Realtime","Sync reactivo cuando hay conexión",     "Requiere manejo explícito de conflictos offline", "Prueba: 2 dispositivos offline → sync → verificar conflicto"),
        ("SQLite + sync manual con timestamps","Más simple, control total",    "Mayor código de sincronización a mantener",       "Test de idempotencia y resolución de conflictos"),
        ("SQLite solo (sin cloud)","Sin dependencia de servidor, máximo offline","Sin dashboard en tiempo real para administradores","Evaluar si el caso de uso real necesita sync"),
        ("Room + WorkManager (Android)","Patrón estándar Android para offline","Solo Android, pierde multiplataforma",           "Comparar con solución Flutter equivalente"),
        ("CouchDB/PouchDB (CRDT)","Resolución de conflictos automática",       "Complejidad alta, overkill para proyectos semestre","Solo si hay evidencia de conflictos frecuentes"),
    ],

    # ── Cifrado y seguridad ──────────────────────────────────────────────────
    "pgcrypto|cifrado|luks|aes": [
        ("Solo LUKS (sin pgcrypto)",      "Menor overhead CPU en operaciones DB","Menos granularidad de control por campo",       "Revisión legal: ¿LUKS solo cumple la ley aplicable?"),
        ("TDE PostgreSQL + LUKS",         "Cifrado transparente a nivel DB",    "Depende de versión/build de PostgreSQL",         "Benchmark overhead TDE vs pgcrypto en carga objetivo"),
        ("Cifrado en capa aplicación",    "Independiente del motor de BD",      "Mayor complejidad en el código de la aplicación","Comparar rendimiento vs pgcrypto bajo carga concurrente"),
        ("HashiCorp Vault para claves",   "Gestión de claves enterprise-grade", "Overhead operacional, complejidad de setup",     "Evaluar si el proyecto justifica esta complejidad"),
    ],

    # ── Aislamiento de sesiones / containers ────────────────────────────────
    "docker|contenedor|sandbox|aislamiento": [
        ("Docker por sesión (actual)",    "Aislamiento fuerte, destroy garantiza privacidad","Overhead creación ~200ms-2s por sesión",      "Medir overhead de inicio en el servidor objetivo"),
        ("Pool de contenedores precalentados","Latencia ~10-50ms en cold start","Requiere limpieza verificada entre sesiones",   "Test de limpieza: estado de sesión anterior no filtra"),
        ("Proceso por sesión + seccomp",  "Más liviano que Docker",            "Menor garantía de aislamiento que container",   "Prueba de penetración cross-session"),
        ("gVisor / kata-containers",      "VM-like isolation sin VM overhead", "Mayor complejidad de setup y menor soporte",    "Benchmark overhead gVisor vs Docker en el caso de uso"),
        ("WebAssembly sandbox",           "Overhead mínimo ~5-20ms",           "Funcional solo para código no privilegiado",    "Evaluar si el chatbot puede ejecutar en WASM"),
    ],

    # ── APIs y vectores (RAG / semantic search) ──────────────────────────────
    "qdrant|weaviate|pinecone|vector|embedding|rag": [
        ("Qdrant (actual/considerado)",   "Open source, Rust, alta performance","Requiere gestión de infraestructura propia",    "Stress test: indexar 1000 docs, medir latencia búsqueda"),
        ("pgvector (PostgreSQL extension)","Sin servicio adicional, misma DB",  "Menor rendimiento que Qdrant para >1M vectores","Benchmark pgvector vs Qdrant en volumen del proyecto"),
        ("Chroma (local embeddings)",     "Setup simple, ideal para MVP",       "No escala a producción grande",                 "Prueba de concepto rápida antes de decidir"),
        ("Weaviate",                      "Hybrid search (vector + keyword)",   "Más pesado operacionalmente que Qdrant",         "Comparar feature set vs Qdrant para el caso de uso"),
        ("Elasticsearch + dense vectors", "Ecosystem maduro, hybrid search",    "Alto costo operacional",                        "Solo si el equipo ya tiene experiencia con ES"),
    ],

    # ── Fine-tuning y alineación ─────────────────────────────────────────────
    "fine.?tuning|entrenamiento|dataset": [
        ("Fine-tuning domain-specific",   "Mejor control del comportamiento",  "Requiere dataset de calidad (¿existe para el dominio?)","Inventario de datasets disponibles en el dominio/idioma"),
        ("System prompt engineering",     "Sin costo de entrenamiento",        "Menos robusto ante distributional shift",        "Test: 50 prompts adversariales vs prompts normales"),
        ("RLHF / Constitutional AI",      "Alineación más robusta",            "Muy alta complejidad, requiere feedback humano", "Solo viable con acceso a feedback de expertos del dominio"),
        ("RAG + KB clínica/dominio",      "Información actualizable sin reentrenar","Latencia adicional por retrieval",          "Benchmark: RAG vs fine-tuning en 20 preguntas del dominio"),
        ("Output classifier (guardrail)", "Capa de seguridad adicional",       "Latencia adicional, falsos positivos posibles",  "Evaluación de 100 respuestas por experto del dominio"),
    ],

    # ── Protocolos de comunicación interna ──────────────────────────────────
    "grpc|rest|graphql|websocket|rabbitmq": [
        ("REST/JSON",                     "Más simple, tooling ubicuo",        "Mayor overhead de serialización",                "Benchmark: REST vs gRPC en volumen y latencia objetivo"),
        ("gRPC + Protocol Buffers",       "Bajo overhead, tipado estricto",    "Curva de aprendizaje, debug más complejo",       "Implementar endpoint de prueba y medir"),
        ("WebSocket",                     "Bidireccional en tiempo real",      "Stateful, más complejo de escalar",              "Test de concurrencia con número de usuarios objetivo"),
        ("Message Queue (RabbitMQ/Redis)","Desacoplamiento, resiliencia",      "Complexity operacional, eventual consistency",   "Prueba de latencia cola bajo carga pico"),
    ],
}


# ─── Mapeo señal → categoría de catálogo ────────────────────────────────────

def _match_catalog_key(signal: UncertaintySignal) -> Optional[str]:
    """
    Encuentra la clave del catálogo más relevante para una señal.
    Busca en source_text e implicit_decision.
    """
    search_text = (signal.source_text + " " + signal.implicit_decision).lower()
    best_key = None
    best_count = 0

    for catalog_key in ALTERNATIVES_CATALOG:
        keywords = catalog_key.split("|")
        count = sum(1 for kw in keywords if kw in search_text)
        if count > best_count:
            best_count = count
            best_key = catalog_key

    return best_key if best_count > 0 else None


def _get_alternatives(catalog_key: str) -> List[Alternative]:
    """Convierte tuplas del catálogo en objetos Alternative."""
    raw = ALTERNATIVES_CATALOG.get(catalog_key, [])
    return [
        Alternative(
            name=name,
            advantage=adv,
            risk=risk,
            evidence_required=ev,
        )
        for name, adv, risk, ev in raw
    ]


# ─── Determinación de prioridad ──────────────────────────────────────────────

def _compute_priority(signal: UncertaintySignal, doc_text: str) -> str:
    """
    Prioridad del spike basada en tipo de señal y presencia de keywords críticos.
    """
    critical_keywords = {
        "seguridad", "safety", "clínico", "médico", "salud", "ley", "gdpr",
        "privacidad", "cifrado", "crisis", "suicid", "emergencia", "paciente",
    }
    text_lower = signal.source_text.lower() + signal.uncertainty_statement.lower()

    if signal.signal_type == SignalType.TIPO_III:
        return "Alta"
    if any(kw in text_lower for kw in critical_keywords):
        return "Alta"
    if signal.signal_type == SignalType.TIPO_II:
        return "Alta"
    if signal.signal_type == SignalType.TIPO_I:
        return "Alta" if "o " in signal.source_text.lower() else "Media"
    return "Media"


# ─── Agrupación de señales relacionadas ──────────────────────────────────────

def _group_related_signals(
    signals: List[UncertaintySignal]
) -> List[List[UncertaintySignal]]:
    """
    Agrupa señales que comparten catálogo o metadata similar.
    Señales del mismo tipo con el mismo catalog_key → un spike.
    """
    catalog_groups: Dict[str, List[UncertaintySignal]] = {}
    ungrouped: List[UncertaintySignal] = []

    for signal in signals:
        key = _match_catalog_key(signal)
        if key:
            catalog_groups.setdefault(key, []).append(signal)
        else:
            ungrouped.append(signal)

    groups = list(catalog_groups.values())
    groups.extend([[s] for s in ungrouped])
    return groups


# ─── Generador de spikes ─────────────────────────────────────────────────────

def generate_spikes(
    signals: List[UncertaintySignal],
    project_name: str,
) -> List[Spike]:
    """
    Genera spikes candidatos desde señales de incertidumbre.

    Estrategia de agrupación:
      - Señales que apuntan al mismo componente tecnológico → un spike
      - Señales Tipo III (normativas) siempre generan spike propio
      - Señales sin catálogo → spike genérico de exploración

    Args:
        signals:      Lista de señales detectadas por signal_extractor.
        project_name: Nombre del proyecto (para IDs legibles).

    Returns:
        Lista de Spike con todos los campos completos.
    """
    print(f"  [spike_generator] Generando spikes para {project_name} …")

    groups = _group_related_signals(signals)
    spikes: List[Spike] = []
    prefix = project_name[:3].upper()

    for i, group in enumerate(groups, start=1):
        if not group:
            continue

        # Señal representativa del grupo (la de mayor prioridad / más informativa)
        primary = max(group, key=lambda s: len(s.uncertainty_statement))
        catalog_key = _match_catalog_key(primary)
        alternatives = _get_alternatives(catalog_key) if catalog_key else []

        # Combinar incertidumbres si son múltiples señales
        if len(group) == 1:
            uncertainty = primary.uncertainty_statement
            implicit    = primary.implicit_decision
        else:
            uncertainty = primary.uncertainty_statement + " (múltiples señales relacionadas)"
            implicit    = "; ".join(set(s.implicit_decision[:80] for s in group))

        # Por qué importa (derivado del tipo de señal)
        why_matters = _build_why_it_matters(primary, group)

        # Evidencia esperada genérica si no hay catálogo
        if not alternatives:
            alternatives = [
                Alternative(
                    name="Exploración y prototipo mínimo",
                    advantage="Produce evidencia directa para la decisión",
                    risk="Puede subestimar el esfuerzo real",
                    evidence_required=(
                        "Documento con alternativas evaluadas, criterios de selección "
                        "y resultado medible de la exploración."
                    ),
                )
            ]

        spike = Spike(
            id=f"SPIKE-{prefix}-{i:02d}",
            title=_build_spike_title(primary, catalog_key),
            signal_ids=[s.id for s in group],
            implicit_decision=implicit,
            uncertainty=uncertainty,
            why_it_matters=why_matters,
            alternatives=alternatives,
            expected_evidence=_build_expected_evidence(primary, alternatives),
            priority=_compute_priority(primary, ""),
            feeds_adr_ids=[f"ADR-{prefix}-{i:02d}"],
        )
        spikes.append(spike)

    # Detectar dependencias entre spikes (si un spike bloquea a otro)
    _add_blocking_dependencies(spikes)

    print(f"    → {len(spikes)} spikes generados "
          f"(Alta:{sum(1 for s in spikes if s.priority=='Alta')}, "
          f"Media:{sum(1 for s in spikes if s.priority=='Media')}, "
          f"Baja:{sum(1 for s in spikes if s.priority=='Baja')})")

    return spikes


def _build_spike_title(signal: UncertaintySignal, catalog_key: Optional[str]) -> str:
    """Construye un título descriptivo para el spike."""
    if catalog_key:
        domain = catalog_key.split("|")[0].replace(".", " ").title()
        type_label = signal.signal_type.value.split(" - ")[1]
        return f"Validación de {domain} — {type_label}"
    # Fallback: usar primeras palabras de la decisión implícita
    words = signal.implicit_decision.split()[:6]
    return " ".join(words).rstrip(".,;")


def _build_why_it_matters(
    primary: UncertaintySignal,
    group: List[UncertaintySignal]
) -> str:
    """Genera el texto explicativo de por qué importa ejecutar el spike."""
    base = {
        SignalType.TIPO_I: (
            "Si la tecnología elegida no cumple los requerimientos del proyecto bajo "
            "condiciones reales, el retrabajo en sprints posteriores puede ser muy costoso. "
            "La ausencia de benchmark documentado significa que el equipo está asumiendo, no sabiendo."
        ),
        SignalType.TIPO_II: (
            "Un umbral de calidad sin validación empírica es un supuesto, no una garantía. "
            "Si el sistema no lo alcanza en producción, el contrato con el cliente (criterio de aceptación) "
            "no se puede cumplir, y el retrabajo ocurre en la fase más cara del proyecto."
        ),
        SignalType.TIPO_III: (
            "El incumplimiento de requisitos legales hace que un sistema técnicamente correcto "
            "sea inoperable en el contexto institucional real. La validación legal no puede delegarse "
            "a suposiciones del equipo de desarrollo."
        ),
        SignalType.TIPO_IV: (
            "Las integraciones con sistemas externos (hardware, APIs, servicios de terceros) "
            "son las fuentes de fallo más frecuentes en proyectos reales. Los rate limits, "
            "formatos de datos y condiciones de fallo raramente coinciden con la documentación."
        ),
        SignalType.TIPO_V: (
            "Las particularidades del contexto local (idioma, regulación, datos disponibles) "
            "pueden invalidar soluciones que funcionan perfectamente en otros contextos. "
            "Un modelo de IA entrenado fuera de Chile puede tener sesgo que afecte la calidad del servicio."
        ),
    }
    return base.get(primary.signal_type, "Esta incertidumbre puede generar retrabajo costoso si no se resuelve temprano.")


def _build_expected_evidence(
    signal: UncertaintySignal,
    alternatives: List[Alternative]
) -> str:
    """Construye la descripción de evidencia esperada del spike."""
    evidences = list(dict.fromkeys(a.evidence_required for a in alternatives[:3]))
    base = "; ".join(evidences) if evidences else "Documento con hallazgos, métricas y decisión."
    return (
        f"El spike debe producir: (1) comparación de alternativas bajo criterios medibles, "
        f"(2) {base}, "
        f"(3) una recomendación fundamentada que cierre o informe el ADR asociado."
    )


def _add_blocking_dependencies(spikes: List[Spike]) -> None:
    """
    Detecta y registra dependencias de bloqueo entre spikes.
    Heurística: si un spike Tipo I sobre un modelo de IA existe,
    cualquier spike Tipo II sobre umbrales de ese modelo depende de él.
    """
    type1_spikes = [s for s in spikes if any(
        sig_id.startswith("SIG") for sig_id in s.signal_ids
    )]

    for spike_a in spikes:
        for spike_b in spikes:
            if spike_a.id == spike_b.id:
                continue
            # Si A es sobre tecnología base y B es sobre umbral relacionado
            a_text = spike_a.uncertainty.lower()
            b_text = spike_b.uncertainty.lower()
            # Umbral de precisión/accuracy depende de la selección del modelo
            if ("modelo" in a_text or "selección" in a_text) and \
               ("recall" in b_text or "accuracy" in b_text or "umbral" in b_text or "precisi" in b_text):
                if spike_b.id not in spike_a.blocks_spike_ids:
                    spike_a.blocks_spike_ids.append(spike_b.id)
                if spike_a.id not in spike_b.blocks_spike_ids:
                    spike_b.blocks_spike_ids = spike_b.blocks_spike_ids  # no reverse
