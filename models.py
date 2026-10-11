"""
models.py — Entidades del pipeline Spike-ADR
============================================
Define los tipos de datos que circulan por cada etapa del pipeline.
Cada dataclass es serializable a JSON para reproducibilidad.

Referencia teórica:
  Vivanco, E. (2026). Spikes como señal temprana de arquitectura.
  UTFSM — Arquitectura de Software & Agile Requirements Engineering.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


# ─── Taxonomía de tipos de señal ──────────────────────────────────────────────

class SignalType(str, Enum):
    """
    Clasificación empírica de incertidumbres arquitectónicas,
    derivada del análisis del corpus UTFSM 2026-1 (12 proyectos).
    """
    TIPO_I  = "Tipo I  - Factibilidad tecnológica"   # tech no validada en el equipo
    TIPO_II = "Tipo II - Umbral de calidad"           # threshold no respaldado por evidencia
    TIPO_III= "Tipo III - Cumplimiento normativo"     # ley/norma no validada legalmente
    TIPO_IV = "Tipo IV - Integración externa"         # hardware, API externa, sistema 3rd party
    TIPO_V  = "Tipo V  - Contexto local"              # especificidad chilena/dominio local


# ─── Patrones de cardinalidad Spike ↔ ADR ─────────────────────────────────────

class SpikeADRPattern(str, Enum):
    """
    Patrones de la relación N:M entre spikes y ADRs.
    Derivados de la Tabla 3 de Vera-Rivera et al. y extendidos
    para el dominio de proyectos estudiantiles.
    """
    ONE_TO_ONE   = "1S→1A"   # un spike informa un ADR
    ONE_TO_MANY  = "1S→NA"   # un spike informa múltiples ADRs
    MANY_TO_ONE  = "NS→1A"   # múltiples spikes para cerrar un ADR
    MANY_TO_MANY = "NS→NA"   # red compleja de evidencias
    ZERO_TO_ONE  = "0S→1A"   # decisión de política sin spike (conocimiento existente)
    ONE_TO_ZERO  = "1S→0A"   # spike de aprendizaje sin ADR inmediato (e.g., MVP probe)


# ─── Entidades del dominio ─────────────────────────────────────────────────────

@dataclass
class QualityAttribute:
    """Un atributo de calidad con meta SMART y mecanismo de verificación."""
    attribute:    str
    meta:         str
    verification: str
    raw_text:     str = ""


@dataclass
class UserStory:
    """Historia de usuario extraída del backlog del proyecto."""
    id:          str
    category:    str   # I=Importante E=Esencial D=Deseable O=Opcional
    description: str
    source:      str = ""


@dataclass
class UncertaintySignal:
    """
    Señal de incertidumbre arquitectónica detectada en el documento.

    Una señal no es el spike; es la evidencia en el texto de que
    una decisión arquitectónica fue tomada sin evidencia suficiente.
    """
    id:                    str
    signal_type:           SignalType
    source_text:           str           # fragmento exacto del documento
    source_section:        str           # sección donde apareció
    implicit_decision:     str           # decisión tomada sin documentar
    uncertainty_statement: str           # pregunta que el spike debe responder
    user_story_refs:       List[str] = field(default_factory=list)
    metadata:              Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signal_type"] = self.signal_type.value
        return d


@dataclass
class Alternative:
    """Una alternativa técnica que el equipo no consideró explícitamente."""
    name:              str
    advantage:         str
    risk:              str
    evidence_required: str


@dataclass
class Spike:
    """
    Spike candidato generado por el pipeline.

    Contiene los 4 elementos pedagógicos:
      1. implicit_decision  — qué se decidió sin documentar
      2. uncertainty        — pregunta que el spike debe responder
      3. alternatives       — opciones no consideradas
      4. expected_evidence  — qué debe producir el spike
    """
    id:               str
    title:            str
    signal_ids:       List[str]           # señales que lo activan
    implicit_decision:str
    uncertainty:      str
    why_it_matters:   str
    alternatives:     List[Alternative]
    expected_evidence:str
    priority:         str                 # "Alta" / "Media" / "Baja"
    blocks_spike_ids: List[str] = field(default_factory=list)
    feeds_adr_ids:    List[str] = field(default_factory=list)
    pattern:          Optional[SpikeADRPattern] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.pattern:
            d["pattern"] = self.pattern.value
        return d


@dataclass
class ADRSkeleton:
    """
    Esqueleto de ADR en formato MADR.
    El contexto y opciones se llenan por el pipeline;
    la decisión y evidencia quedan para que el equipo complete.
    """
    id:                    str
    title:                 str
    spike_ids:             List[str]
    context:               str
    problem:               str
    considered_options:    List[str]
    status:                str = "Propuesto"
    decision:              str = "<!-- COMPLETAR: ¿qué eligieron y por qué? -->"
    consequences_positive: str = "<!-- COMPLETAR -->"
    consequences_negative: str = "<!-- COMPLETAR -->"
    evidence:              str = "<!-- COMPLETAR: resultados del spike asociado -->"

    def to_dict(self) -> dict:
        return asdict(self)

    def to_madr(self) -> str:
        """Exportar como Markdown en formato MADR."""
        options_md = "\n".join(f"- {o}" for o in self.considered_options)
        spike_refs  = ", ".join(self.spike_ids)
        return f"""# {self.id}: {self.title}

## Estado
- [ ] Propuesto  - [ ] Aceptado  - [ ] Rechazado  - [ ] Deprecado

*Spikes asociados: {spike_refs}*

## Contexto y problema
{self.context}

**{self.problem}**

## Opciones consideradas
{options_md}

## Decisión tomada
{self.decision}

## Consecuencias positivas
{self.consequences_positive}

## Consecuencias negativas / trade-offs aceptados
{self.consequences_negative}

## Evidencia que respalda esta decisión
{self.evidence}
"""


@dataclass
class ProjectDocument:
    """Documento de proyecto parseado y estructurado."""
    project_name:       str
    group_id:           str
    pdf_path:           str
    summary:            str = ""
    tech_stack:         Dict[str, str]         = field(default_factory=dict)
    quality_attributes: List[QualityAttribute] = field(default_factory=list)
    user_stories:       List[UserStory]        = field(default_factory=list)
    raw_text:           str = ""
    sections:           Dict[str, str]         = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Resultado completo del pipeline para un proyecto."""
    project:       ProjectDocument
    signals:       List[UncertaintySignal]
    spikes:        List[Spike]
    adrs:          List[ADRSkeleton]
    graph_data:    Dict
    generated_at:  str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {
                "project_name": self.project.project_name,
                "group_id":     self.project.group_id,
                "generated_at": self.generated_at,
                "signals":      [s.to_dict() for s in self.signals],
                "spikes":       [s.to_dict() for s in self.spikes],
                "adrs":         [a.to_dict() for a in self.adrs],
                "graph_data":   self.graph_data,
            },
            ensure_ascii=False,
            indent=indent,
        )

    def summary_stats(self) -> Dict[str, Any]:
        from collections import Counter
        return {
            "n_signals":          len(self.signals),
            "n_spikes":           len(self.spikes),
            "n_adrs":             len(self.adrs),
            "signals_by_type":    Counter(s.signal_type.value for s in self.signals),
            "spikes_by_priority": Counter(s.priority for s in self.spikes),
            "graph_edges":        self.graph_data.get("edges", []),
        }
