"""
signal_extractor.py — Detección de señales de incertidumbre arquitectónica
===========================================================================
Recibe un ProjectDocument y retorna una lista de UncertaintySignal.

Estrategia:
  - Reglas + regex sobre texto (sin ML) → suficiente para señales explícitas
  - Cinco detectores, uno por tipo de señal (Tipo I–V)
  - Cada detector es independiente y testeable por separado

Señales explícitas detectables:
  Tipo I  — tecnologías no validadas: conjunción "X o Y", palabras clave de frameworks
  Tipo II — umbrales QA: números con unidades en contexto de atributos de calidad
  Tipo III— normativos: menciones de leyes y normas
  Tipo IV — integraciones externas: APIs, hardware, servicios de terceros
  Tipo V  — contexto local: especificidad chilena o de dominio
"""

from __future__ import annotations
import re
from typing import List, Dict, Tuple, Set
from models import (
    ProjectDocument, UncertaintySignal, SignalType, UserStory
)


# ─── Catálogos de keywords ────────────────────────────────────────────────────

# Tipo I — frameworks/modelos/librerías sin evidencia de benchmark
TECH_KEYWORDS: List[str] = [
    "tensorflow", "tflite", "pytorch", "keras",
    "mobilenet", "efficientnet", "yolo", "bert", "llama", "mistral", "gpt",
    "flutter", "react native", "next.js", "nestjs", "fastapi", "django", "go ",
    "docker", "kubernetes", "supabase", "firebase", "mongodb", "postgresql",
    "sqlite", "redis", "qdrant", "weaviate", "chromadb",
    "webassembly", "wasm", "mediapipe", "onnx", "llama.cpp",
    "grpc", "graphql", "websocket", "rabbitmq",
    "google adk", "langchain", "llamaindex", "openai",
]

# Tipo II — keywords de atributos de calidad cerca de un número
QA_CONTEXT_KEYWORDS: List[str] = [
    "latencia", "tiempo de respuesta", "inferencia", "procesamiento",
    "disponibilidad", "uptime", "tiempo de inactividad",
    "precisión", "recall", "accuracy", "auc", "f1",
    "usuarios concurrentes", "solicitudes", "throughput",
    "seguridad", "vulnerabilidad", "cifrado",
    "usabilidad", "completar", "tarea", "onboarding",
    "escalabilidad", "nodos", "instancias",
    "recuperabilidad", "reintentos", "timeout",
]

# Tipo III — referencias legales y normativas
NORMATIVE_KEYWORDS: List[Tuple[str, str]] = [
    (r"ley\s+(?:n[°º]?\s*)?\d{2,6}", "Ley chilena"),
    (r"19[,.]?628",                   "Ley 19.628 — Protección de datos personales"),
    (r"21[,.]?719",                   "Ley 21.719 — Datos personales sensibles"),
    (r"iso\s*\d{4,5}",                "Norma ISO"),
    (r"iso/iec\s*25010",              "ISO/IEC 25010 — Calidad del software"),
    (r"gdpr|rgpd",                    "GDPR/RGPD"),
    (r"dicom",                        "Estándar DICOM — Imágenes médicas"),
    (r"iucn",                         "Clasificación IUCN — Estado de conservación"),
    (r"cvss",                         "CVSS — Severidad de vulnerabilidades"),
]

# Tipo IV — integraciones externas (hardware o servicios de terceros)
EXTERNAL_INTEGRATION_KEYWORDS: List[str] = [
    "api de ", "api oficial", "api externa", "mercado público",
    "rtk", "imu", "lidar", "gps", "sensor", "micrófono", "cámara",
    "sumo", "openstreetmap", "google maps",
    "play integrity", "app attest",
    "anthropic", "openai", "hugging face",
    "chilecompra", "sii", "registro civil",
    "whatsapp", "smtp", "push notification",
    "oauth", "oidc",
]

# Tipo V — contexto local chileno
LOCAL_CONTEXT_KEYWORDS: List[str] = [
    "chileno", "chile", "chilena",
    "español chileno", "jerga universitaria",
    "utfsm", "usm", "puc", "uchile",
    "capsi", "cesfam", "fonasa", "isapre",
    "minsal", "chilecompra", "mercado público",
    "lsch", "lengua de señas chilena",
    "disfam", "fundación",
]


# ─── Regex utilitarios ────────────────────────────────────────────────────────

# Detecta "X o Y" donde X e Y son probablemente nombres de tecnologías
OR_PATTERN = re.compile(
    r"([A-Za-z][A-Za-z0-9+.\-]{2,25})\s+[ou]\s+([A-Za-z][A-Za-z0-9+.\-]{2,25})",
    re.IGNORECASE
)

# Detecta umbrales numéricos con unidades
THRESHOLD_PATTERN = re.compile(
    r"(?:(?:menos de|inferior a|menor a|mayor[a\s]+(?:o igual\s+)?a|"
    r"al menos|mínimo|máximo|entre\s+\d+\s+y\s+)?\s*)?"
    r"(\d+(?:[,\.]\d+)?)\s*"
    r"(%|ms|s(?:egundos?)?|minutos?|horas?|días?|usuarios?|nodos?|"
    r"mb|gb|tb|rpm|rps|tps|tokens?|páginas?)",
    re.IGNORECASE
)

# Detecta líneas con calidad + número (señal Tipo II)
QA_LINE_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(k) for k in QA_CONTEXT_KEYWORDS[:15]) + r")"
    r".{0,100}"
    r"(\d+(?:[,\.]\d+)?)\s*(%|ms|s(?:egundos?)?|minutos?|usuarios?)",
    re.IGNORECASE
)


# ─── Funciones auxiliares ─────────────────────────────────────────────────────

def _build_signal_id(prefix: str, index: int) -> str:
    return f"S-{prefix}-{index:02d}"


def _find_related_stories(
    text_fragment: str, stories: List[UserStory]
) -> List[str]:
    """Encuentra historias cuya descripción menciona keywords del fragmento."""
    words = set(re.findall(r"\b\w{4,}\b", text_fragment.lower()))
    related = []
    for story in stories:
        story_words = set(re.findall(r"\b\w{4,}\b", story.description.lower()))
        overlap = words & story_words
        if len(overlap) >= 3:
            related.append(story.id)
    return related[:5]


def _context_snippet(text: str, match_start: int, window: int = 150) -> str:
    """Extrae un fragmento de contexto alrededor de una posición."""
    start = max(0, match_start - window)
    end   = min(len(text), match_start + window)
    return text[start:end].replace("\n", " ").strip()


# ─── Detectores por tipo ──────────────────────────────────────────────────────

def detect_tipo_i(doc: ProjectDocument) -> List[UncertaintySignal]:
    """
    Tipo I — Factibilidad tecnológica.
    Detecta:
      a) conjunciones "X o Y" con nombres de tecnologías
      b) menciones de tecnologías sin evidencia de benchmark en el documento
    """
    signals: List[UncertaintySignal] = []
    text = doc.raw_text
    lower_text = text.lower()
    seen_techs: Set[str] = set()
    idx = 0

    # a) Conjunciones "X o Y" en la sección de tecnología
    tech_section = doc.sections.get("tech_qa", text)
    for m in OR_PATTERN.finditer(tech_section):
        x, y = m.group(1).lower(), m.group(2).lower()
        # Verificar que al menos uno es una tecnología conocida
        is_tech = any(kw in x or kw in y for kw in TECH_KEYWORDS)
        if is_tech:
            fragment = _context_snippet(tech_section, m.start())
            key = f"{x}_{y}"
            if key not in seen_techs:
                seen_techs.add(key)
                idx += 1
                signals.append(UncertaintySignal(
                    id=_build_signal_id("I", idx),
                    signal_type=SignalType.TIPO_I,
                    source_text=m.group(0),
                    source_section="tech_qa",
                    implicit_decision=(
                        f"El equipo no ha decidido entre '{m.group(1)}' y '{m.group(2)}'. "
                        f"La conjunción 'o' indica que la selección estaba abierta."
                    ),
                    uncertainty_statement=(
                        f"¿Cuál de las dos opciones — {m.group(1)} o {m.group(2)} — "
                        f"satisface mejor los atributos de calidad del proyecto bajo las "
                        f"condiciones reales de operación?"
                    ),
                    user_story_refs=_find_related_stories(fragment, doc.user_stories),
                    metadata={"or_option_a": m.group(1), "or_option_b": m.group(2)},
                ))

    # b) Tecnologías mencionadas sin aparición de "benchmark", "prueba", "validar"
    evidence_words = {"benchmark", "prueba", "ensayo", "validar", "medicion",
                      "medición", "latencia medida", "se verificó", "se probó"}
    for kw in TECH_KEYWORDS:
        if kw in lower_text and kw not in seen_techs:
            # Buscar si hay evidencia cerca
            positions = [m.start() for m in re.finditer(re.escape(kw), lower_text)]
            for pos in positions[:1]:  # solo primera ocurrencia
                context = lower_text[max(0, pos-200):pos+200]
                has_evidence = any(ew in context for ew in evidence_words)
                if not has_evidence:
                    seen_techs.add(kw)
                    idx += 1
                    snippet = _context_snippet(text, pos)
                    signals.append(UncertaintySignal(
                        id=_build_signal_id("I", idx),
                        signal_type=SignalType.TIPO_I,
                        source_text=snippet,
                        source_section="tech_qa",
                        implicit_decision=(
                            f"'{kw}' fue elegido sin evidencia de benchmark "
                            f"documentada en el proyecto."
                        ),
                        uncertainty_statement=(
                            f"¿{kw} cumple los atributos de calidad del proyecto "
                            f"(rendimiento, disponibilidad, usabilidad) bajo las "
                            f"condiciones reales de uso?"
                        ),
                        user_story_refs=_find_related_stories(snippet, doc.user_stories),
                        metadata={"technology": kw},
                    ))
    return signals


def detect_tipo_ii(doc: ProjectDocument) -> List[UncertaintySignal]:
    """
    Tipo II — Umbrales de calidad.
    Detecta valores numéricos (% , ms, s, usuarios…) en contexto de QA
    que no tienen referencia a su validación empírica.
    """
    signals: List[UncertaintySignal] = []
    idx = 0
    text = doc.raw_text
    lower = text.lower()

    # Buscar en cada atributo de calidad extraído
    for qa in doc.quality_attributes:
        threshold_matches = list(THRESHOLD_PATTERN.finditer(qa.meta + " " + qa.raw_text))
        if not threshold_matches:
            continue
        # Verificar si hay validación mencionada
        has_validation = any(w in qa.verification.lower() for w in
                             {"prueba", "benchmark", "test", "medici", "jmeter",
                              "locust", "k6", "snyk", "validaci"})
        if not has_validation:
            for m in threshold_matches[:2]:
                idx += 1
                value = m.group(1) + " " + m.group(2)
                signals.append(UncertaintySignal(
                    id=_build_signal_id("II", idx),
                    signal_type=SignalType.TIPO_II,
                    source_text=qa.raw_text[:300],
                    source_section="tech_qa",
                    implicit_decision=(
                        f"El umbral '{value}' para '{qa.attribute}' fue fijado "
                        f"sin evidencia empírica documentada."
                    ),
                    uncertainty_statement=(
                        f"¿El umbral de {value} para '{qa.attribute}' es alcanzable "
                        f"con el stack tecnológico elegido bajo las condiciones reales "
                        f"de operación del proyecto?"
                    ),
                    metadata={"threshold_value": value, "qa_attribute": qa.attribute},
                ))

    # Buscar también en texto libre de la sección tech_qa
    tech_text = doc.sections.get("tech_qa", "")
    for m in QA_LINE_PATTERN.finditer(tech_text):
        idx += 1
        value = m.group(1) + " " + m.group(2)
        fragment = _context_snippet(tech_text, m.start())
        signals.append(UncertaintySignal(
            id=_build_signal_id("II", idx),
            signal_type=SignalType.TIPO_II,
            source_text=fragment,
            source_section="tech_qa",
            implicit_decision=(
                f"El umbral '{value}' aparece en el texto sin respaldo de spike."
            ),
            uncertainty_statement=(
                f"¿El sistema puede garantizar {value} en condiciones de producción? "
                f"¿Se validó con datos representativos del caso de uso real?"
            ),
            user_story_refs=_find_related_stories(fragment, doc.user_stories),
            metadata={"threshold_value": value},
        ))

    # Deduplicar por source_text similar
    seen: Set[str] = set()
    unique = []
    for s in signals:
        key = s.metadata.get("threshold_value", s.source_text[:50])
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def detect_tipo_iii(doc: ProjectDocument) -> List[UncertaintySignal]:
    """
    Tipo III — Cumplimiento normativo.
    Detecta menciones de leyes y normas sin evidencia de validación legal.
    """
    signals: List[UncertaintySignal] = []
    text = doc.raw_text
    lower = text.lower()
    idx = 0
    seen: Set[str] = set()

    for pattern, description in NORMATIVE_KEYWORDS:
        for m in re.finditer(pattern, lower):
            key = m.group(0)
            if key in seen:
                continue
            seen.add(key)
            # Buscar si hay evidencia de revisión legal cercana
            context = lower[max(0, m.start()-300):m.end()+300]
            has_legal_validation = any(w in context for w in
                                       {"abogado", "dpia", "dpa", "asesor", "jurídico",
                                        "verificaci", "auditoria", "auditoría",
                                        "consentimiento", "titular"})
            idx += 1
            snippet = _context_snippet(text, m.start())
            signals.append(UncertaintySignal(
                id=_build_signal_id("III", idx),
                signal_type=SignalType.TIPO_III,
                source_text=snippet,
                source_section="tech_qa",
                implicit_decision=(
                    f"Se menciona '{description}' como requisito pero no se documenta "
                    f"cómo la arquitectura lo cumple ni quién lo validó."
                ),
                uncertainty_statement=(
                    f"¿La arquitectura propuesta satisface los requisitos de "
                    f"'{description}'? ¿Existe una revisión legal o DPIA que lo confirme?"
                ),
                metadata={
                    "norm": description,
                    "has_legal_validation": has_legal_validation
                },
            ))
    return signals


def detect_tipo_iv(doc: ProjectDocument) -> List[UncertaintySignal]:
    """
    Tipo IV — Integración externa.
    Detecta dependencias de hardware, APIs externas o servicios de terceros
    sin evidencia de spike de integración.
    """
    signals: List[UncertaintySignal] = []
    text = doc.raw_text
    lower = text.lower()
    idx = 0
    seen: Set[str] = set()

    for kw in EXTERNAL_INTEGRATION_KEYWORDS:
        if kw in lower:
            positions = [m.start() for m in re.finditer(re.escape(kw), lower)]
            for pos in positions[:1]:
                if kw in seen:
                    continue
                seen.add(kw)
                context = lower[max(0, pos-200):pos+300]
                # ¿Hay evidencia de que se probó?
                has_integration_test = any(w in context for w in
                                           {"prueba", "test", "integrac", "spike",
                                            "prototipo", "poc", "validar", "verificar"})
                if not has_integration_test:
                    idx += 1
                    snippet = _context_snippet(text, pos)
                    signals.append(UncertaintySignal(
                        id=_build_signal_id("IV", idx),
                        signal_type=SignalType.TIPO_IV,
                        source_text=snippet,
                        source_section="tech_qa",
                        implicit_decision=(
                            f"Se depende de '{kw}' sin evidencia de prueba de integración."
                        ),
                        uncertainty_statement=(
                            f"¿La integración con '{kw}' funciona correctamente bajo "
                            f"las condiciones reales (latencia, rate limits, fallos, "
                            f"formato de datos)? ¿Se probó con datos representativos?"
                        ),
                        user_story_refs=_find_related_stories(snippet, doc.user_stories),
                        metadata={"external_dependency": kw},
                    ))
    return signals


def detect_tipo_v(doc: ProjectDocument) -> List[UncertaintySignal]:
    """
    Tipo V — Contexto local.
    Detecta dependencias de datos, regulaciones o condiciones específicas
    del contexto chileno que no fueron validadas.
    """
    signals: List[UncertaintySignal] = []
    text = doc.raw_text
    lower = text.lower()
    idx = 0
    seen: Set[str] = set()

    # Buscar menciones de modelos de IA + "chileno/español" → dataset local
    ai_local_pattern = re.compile(
        r"(?:modelo|dataset|datos?|entrenamiento|fine.?tuning)"
        r".{0,60}"
        r"(?:chileno|español|chile|local|nacional)",
        re.IGNORECASE
    )
    for m in ai_local_pattern.finditer(text):
        key = m.group(0)[:40]
        if key not in seen:
            seen.add(key)
            idx += 1
            signals.append(UncertaintySignal(
                id=_build_signal_id("V", idx),
                signal_type=SignalType.TIPO_V,
                source_text=m.group(0),
                source_section="tech_qa",
                implicit_decision=(
                    "El proyecto asume disponibilidad de datos o modelos "
                    "adaptados al contexto chileno sin documentar su fuente."
                ),
                uncertainty_statement=(
                    "¿Existe un dataset en español chileno / contexto local con "
                    "la calidad y volumen suficientes para el entrenamiento o validación "
                    "del modelo? ¿Qué protocolo ético rige su uso?"
                ),
                metadata={"local_context_phrase": m.group(0)[:100]},
            ))

    # Buscar keywords locales en texto de resumen
    summary = doc.sections.get("summary", "")
    for kw in LOCAL_CONTEXT_KEYWORDS:
        if kw in summary.lower() and kw not in seen:
            seen.add(kw)
            idx += 1
            signals.append(UncertaintySignal(
                id=_build_signal_id("V", idx),
                signal_type=SignalType.TIPO_V,
                source_text=f"Mención: '{kw}' en resumen del proyecto.",
                source_section="summary",
                implicit_decision=(
                    f"El proyecto opera en el contexto '{kw}' con implicaciones "
                    f"locales no evaluadas arquitectónicamente."
                ),
                uncertainty_statement=(
                    f"¿Las decisiones arquitectónicas (modelo, datos, regulación) "
                    f"consideran las particularidades del contexto '{kw}'?"
                ),
                metadata={"local_keyword": kw},
            ))
    return signals


# ─── Extractor principal ──────────────────────────────────────────────────────

def extract_signals(doc: ProjectDocument) -> List[UncertaintySignal]:
    """
    Ejecuta los cinco detectores y retorna la lista consolidada de señales.
    Ordena por tipo y elimina duplicados por source_text similar.
    """
    print(f"  [signal_extractor] Analizando {doc.project_name} …")

    all_signals: List[UncertaintySignal] = []
    all_signals.extend(detect_tipo_i(doc))
    all_signals.extend(detect_tipo_ii(doc))
    all_signals.extend(detect_tipo_iii(doc))
    all_signals.extend(detect_tipo_iv(doc))
    all_signals.extend(detect_tipo_v(doc))

    # Re-numerar IDs de forma global y consistente
    for i, signal in enumerate(all_signals, start=1):
        signal.id = f"SIG-{i:03d}"

    print(f"    → {len(all_signals)} señales detectadas "
          f"(I:{sum(1 for s in all_signals if s.signal_type==SignalType.TIPO_I)}, "
          f"II:{sum(1 for s in all_signals if s.signal_type==SignalType.TIPO_II)}, "
          f"III:{sum(1 for s in all_signals if s.signal_type==SignalType.TIPO_III)}, "
          f"IV:{sum(1 for s in all_signals if s.signal_type==SignalType.TIPO_IV)}, "
          f"V:{sum(1 for s in all_signals if s.signal_type==SignalType.TIPO_V)})")

    return all_signals
