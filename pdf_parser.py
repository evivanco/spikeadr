"""
pdf_parser.py — Extracción estructurada de documentos PDF de proyectos estudiantiles
======================================================================================
Parsea los documentos generados con el template del curso GPI (INF360) UTFSM.

Estructura esperada del documento:
  1. Resumen del proyecto
  2. Cliente - Actores (usuarios) del sistema
  3. Historias de usuario del sistema
  4. Descripción de la tecnología a usar y Atributos de calidad
  5. Propuesta de prototipo mínimo viable (PMV)

Dependencias: pdfplumber
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pdfplumber

from models import ProjectDocument, QualityAttribute, UserStory


# ─── Patrones de sección ──────────────────────────────────────────────────────

# Cada entrada: (nombre_interno, regex para detectar el heading de la sección)
SECTION_HEADINGS: List[Tuple[str, str]] = [
    ("summary",    r"(?:1\s*[\.·\-]?\s*)?Resumen del proyecto"),
    ("actors",     r"(?:2\s*[\.·\-]?\s*)?Cliente\s*[-–]\s*Actores"),
    ("stories",    r"(?:3\s*[\.·\-]?\s*)?Historias de usuario"),
    ("tech_qa",    r"(?:4\s*[\.·\-]?\s*)?(?:Descripci[oó]n de la tecnolog[ií]a|Tecnolog[ií]as? a [Uu]sar|Stack)"),
    ("mvp",        r"(?:5\s*[\.·\-]?\s*)?Propuesta de prototipo|PMV"),
]

# Patrones de historia de usuario: HDU-01, HU01, HdU 3, MBI01, ST 01 …
STORY_PATTERN = re.compile(
    r"^\s*((?:[A-Z]{1,4}[-\s]?\d{1,3}|HDU[-\s]?\d+|HU[-\s]?\d+|HdU\s*\d+))"
    r"\s*\|?\s*([IEDOiedo])\s*\|?\s*(.{20,500}?)(?=\n\s*(?:[A-Z]{1,4}[-\s]?\d|\Z))",
    re.DOTALL | re.MULTILINE
)

# Patrones de atributos de calidad en texto libre (fallback si no hay tabla)
QA_PROSE_PATTERN = re.compile(
    r"(?:^|\n)\s*\*{0,2}([A-ZÁÉÍÓÚÑ][^:\n]{3,50})\*{0,2}\s*:"
    r"\s*(Meta[:\s]?.{10,300}?)(?=\n\s*\*{0,2}[A-ZÁÉÍÓÚÑ]|\Z)",
    re.DOTALL
)


# ─── Extracción de texto ──────────────────────────────────────────────────────

def extract_raw_text(pdf_path: str) -> str:
    """Extrae todo el texto del PDF página por página."""
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=2, y_tolerance=3)
            if text:
                parts.append(text)
    return "\n".join(parts)


def extract_all_tables(pdf_path: str) -> List[List[List[Optional[str]]]]:
    """Extrae todas las tablas del PDF."""
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_tables = page.extract_tables()
            if page_tables:
                tables.extend(page_tables)
    return tables


# ─── Segmentación en secciones ────────────────────────────────────────────────

def split_into_sections(text: str) -> Dict[str, str]:
    """
    Divide el texto en secciones según los headings del template del curso.
    Retorna un dict {nombre_sección: contenido}.
    """
    compiled = [(name, re.compile(pat, re.IGNORECASE)) for name, pat in SECTION_HEADINGS]

    # Encontrar posiciones de cada heading
    hits: List[Tuple[int, str]] = []
    for line_no, line in enumerate(text.splitlines()):
        for name, pattern in compiled:
            if pattern.search(line.strip()):
                # Usamos posición de carácter aproximada
                char_pos = sum(len(l) + 1 for l in text.splitlines()[:line_no])
                hits.append((char_pos, name))
                break  # sólo un match por línea

    # Ordenar por posición y extraer contenido entre heading i y i+1
    hits.sort(key=lambda x: x[0])
    sections: Dict[str, str] = {}

    for i, (start, name) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        sections[name] = text[start:end].strip()

    return sections


# ─── Extracción de atributos de calidad ───────────────────────────────────────

def _cell(v: Optional[str]) -> str:
    return str(v).strip() if v else ""


def extract_quality_attributes(
    tech_text: str,
    tables: List[List[List[Optional[str]]]]
) -> List[QualityAttribute]:
    """
    Extrae atributos de calidad desde tablas (preferido) o desde texto en prosa.

    Los documentos usan dos formatos:
      a) Tabla: Atributo | Meta SMART | Mecanismo de Verificación
      b) Prosa: Negrita con dos puntos seguido de descripción + meta

    Retorna lista de QualityAttribute.
    """
    qas: List[QualityAttribute] = []

    # ── Intento 1: desde tablas ────────────────────────────────────────────────
    qa_keywords = {"atributo", "meta", "verificac", "calidad", "objetivo"}
    for table in tables:
        if not table or len(table) < 2:
            continue
        header = [_cell(c).lower() for c in (table[0] or [])]
        if not any(kw in " ".join(header) for kw in qa_keywords):
            continue
        for row in table[1:]:
            if not row:
                continue
            cells = [_cell(c) for c in row]
            if len(cells) >= 2 and cells[0] and len(cells[0]) > 3:
                qas.append(QualityAttribute(
                    attribute=cells[0],
                    meta=cells[1] if len(cells) > 1 else "",
                    verification=cells[2] if len(cells) > 2 else "",
                    raw_text=" | ".join(cells),
                ))

    if qas:
        return qas

    # ── Intento 2: prosa ──────────────────────────────────────────────────────
    # Busca patrones como "**Rendimiento**: Meta: X. Verificación: Y."
    qa_section_kw = re.compile(
        r"(?:rendimiento|seguridad|disponibilidad|usabilidad|escalabilidad|"
        r"fiabilidad|mantenibilidad|privacidad|interoperabilidad|"
        r"tiempo de respuesta|uptime|precisi[oó]n)",
        re.IGNORECASE
    )
    meta_kw = re.compile(r"(?:meta|objetivo|el sistema debe|el \d+%)", re.IGNORECASE)

    paragraphs = re.split(r"\n{2,}", tech_text)
    for para in paragraphs:
        if qa_section_kw.search(para) and meta_kw.search(para):
            # Extraer nombre del atributo (primera palabra en negrita o mayúscula inicial)
            name_match = re.match(r"\*{0,2}([A-ZÁÉÍÓÚÑ][^:\n*]{3,50})\*{0,2}[:\s]", para)
            attr_name = name_match.group(1).strip() if name_match else para[:50]
            qas.append(QualityAttribute(
                attribute=attr_name,
                meta=para[:500],
                verification="",
                raw_text=para[:500],
            ))

    return qas


# ─── Extracción de historias de usuario ───────────────────────────────────────

def extract_user_stories(stories_text: str) -> List[UserStory]:
    """
    Extrae historias de usuario del texto de la sección 3.

    Maneja los dos formatos más comunes del corpus:
      a) Tabla: ID | C | Descripción
      b) Formato libre: HDU-01 I Como...
    """
    stories: List[UserStory] = []
    seen_ids: set = set()

    # Regex que captura: ID  CATEGORIA  Como ... para ...
    pattern = re.compile(
        r"((?:[A-Z]{1,4}[-\s]?\d{1,3}))\s+"          # ID
        r"([IEDOiedo])\s+"                              # Categoría
        r"(Como\s.+?(?:para\s.+?)?)"                   # Descripción completa
        r"(?=(?:[A-Z]{1,4}[-\s]?\d{1,3})\s+[IEDOiedo]\s+Como|\Z)",
        re.DOTALL | re.IGNORECASE,
    )

    for m in pattern.finditer(stories_text):
        story_id  = m.group(1).strip().upper()
        category  = m.group(2).strip().upper()
        desc      = " ".join(m.group(3).split())[:600]

        if story_id not in seen_ids and len(desc) > 20:
            seen_ids.add(story_id)
            stories.append(UserStory(
                id=story_id,
                category=category,
                description=desc,
            ))

    return stories


# ─── Extracción de stack tecnológico ─────────────────────────────────────────

_TECH_COMPONENTS = [
    ("frontend",      r"front[-\s]?end[:\s]+([^\n.]{10,200})"),
    ("backend",       r"back[-\s]?end[:\s]+([^\n.]{10,200})"),
    ("database",      r"(?:base de datos|almacenamiento|db)[:\s]+([^\n.]{10,200})"),
    ("ai_model",      r"(?:modelo|inteligencia artificial|ia|ml)[:\s]+([^\n.]{10,200})"),
    ("api",           r"(?:api|comunicaci[oó]n entre)[:\s]+([^\n.]{10,200})"),
    ("auth",          r"(?:autenticaci[oó]n|auth)[:\s]+([^\n.]{10,200})"),
    ("infrastructure",r"(?:infraestructura|despliegue|deploy|cloud)[:\s]+([^\n.]{10,200})"),
    ("framework",     r"(?:framework|bibliotecas?)[:\s]+([^\n.]{10,200})"),
]

def extract_tech_stack(tech_text: str) -> Dict[str, str]:
    """Extrae decisiones de stack tecnológico desde la sección 4."""
    stack: Dict[str, str] = {}
    for component, pattern in _TECH_COMPONENTS:
        m = re.search(pattern, tech_text, re.IGNORECASE)
        if m:
            stack[component] = " ".join(m.group(1).split())[:300]
    return stack


# ─── Punto de entrada ─────────────────────────────────────────────────────────

def parse_project_document(
    pdf_path: str,
    project_name: str,
    group_id: str,
) -> ProjectDocument:
    """
    Función principal del parser.

    Args:
        pdf_path:     Ruta al PDF del proyecto.
        project_name: Nombre del proyecto (e.g., "Biodex").
        group_id:     Identificador del grupo (e.g., "G01").

    Returns:
        ProjectDocument con toda la información estructurada.
    """
    print(f"  [pdf_parser] Procesando {project_name} ({group_id}) …")

    raw_text = extract_raw_text(pdf_path)
    tables   = extract_all_tables(pdf_path)
    sections = split_into_sections(raw_text)

    tech_text = sections.get("tech_qa", raw_text)
    stories_text = sections.get("stories", raw_text)

    return ProjectDocument(
        project_name=project_name,
        group_id=group_id,
        pdf_path=pdf_path,
        summary=sections.get("summary", "")[:3000],
        tech_stack=extract_tech_stack(tech_text),
        quality_attributes=extract_quality_attributes(tech_text, tables),
        user_stories=extract_user_stories(stories_text),
        raw_text=raw_text,
        sections=sections,
    )
