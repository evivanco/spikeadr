# CHANGELOG V2 — Large Fonts

## Problema corregido

Las figuras insertadas en `report.tex` tenían textos demasiado pequeños para lectura humana.

## Cambios

- `visualize_bipartite_dependency_table()`
  - Aumenta `figsize`.
  - Sube fuente de tabla a 13 pt.
  - Aumenta altura de filas.
  - Exporta con `dpi=220`.

- `visualize_layered_process()`
  - Aumenta tamaño global de figura.
  - Sube títulos de cajas a 14 pt.
  - Sube contenido a 12 pt.
  - Aumenta tamaño de flechas y separación.

- Heatmaps y matriz
  - Aumenta títulos, ejes, ticks y anotaciones.
  - Exporta con `dpi=220`.

## Archivos modificados

- `graph_builder.py`
- `README.md`
