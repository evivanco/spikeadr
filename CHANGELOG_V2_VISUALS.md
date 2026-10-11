# CHANGELOG V2 Visuals

## Cambios principales

1. `graph_builder.py`
   - Agrega `visualize_traceability_matrix()`.
   - Agrega `visualize_category_heatmap()`.
   - Agrega `visualize_agent_heatmap()`.
   - Agrega `visualize_layered_process()`.
   - Agrega `generate_visual_artifacts()` para generar todas las figuras.

2. `pipeline.py`
   - Reemplaza la salida visual única por cinco artefactos:
     - `graph.png`
     - `graph_traceability_matrix.png`
     - `graph_category_heatmap.png`
     - `graph_agent_heatmap.png`
     - `graph_layered_process.png`
   - Envía esas figuras al reporte LaTeX.

3. `latex_report.py`
   - Agrega soporte para `graph_paths`.
   - Crea sección `Visual Traceability Artifacts`.
   - Incluye matriz, heatmaps, diagrama por capas y grafo original.

4. `run_batch_by_folder.py`
   - Conserva ejecución N veces sobre PDFs de una carpeta.
   - Cada carpeta por proyecto contiene las nuevas figuras.

## Recomendación de uso

Para lectura humana y reporte académico:
- Usar primero `graph_layered_process.png`.
- Luego `graph_traceability_matrix.png`.
- Luego `graph_category_heatmap.png` y `graph_agent_heatmap.png`.
- Dejar `graph.png` como artefacto complementario.
