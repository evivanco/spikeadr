# Cambios aplicados en V2 modificada

Esta versión integra `latex_report.py` como una sexta etapa del pipeline.

## Cambios principales

1. `pipeline.py`
   - Importa `generate_latex_report` y `compile_latex_to_pdf`.
   - `run_pipeline()` ahora recibe:
     - `generate_latex: bool = True`
     - `compile_pdf: bool = False`
   - `_write_outputs()` genera:
     - `report.tex`
     - `report.pdf` si se usa `--compile-pdf` y `pdflatex` está disponible.
   - CLI actualizada:
     - `--no-latex`
     - `--compile-pdf`
   - `run_batch()` propaga las opciones de reporte.

2. `latex_report.py`
   - Se conserva como módulo independiente.
   - Se documenta que `graph_path="graph.png"` es la opción recomendada cuando el reporte y el grafo están en la misma carpeta.

3. `README.md`
   - Agrega salidas `report.tex` y `report.pdf`.
   - Agrega comandos de ejecución V2.
   - Agrega nota sobre instalación externa de LaTeX.

## Comando recomendado

```bash
python pipeline.py run \
  --pdf "./pdfs/G02_Historias_LunarScan.pdf" \
  --name "LunarScan" \
  --group G02 \
  --output results \
  --compile-pdf
```

## Salidas esperadas

```text
results/G02/
├── result.json
├── signals.json
├── SPIKES_ADR.md
├── evaluation_rubric.md
├── evaluation_data.csv
├── graph.dot
├── graph.png
├── report.tex
└── report.pdf   # solo si --compile-pdf funciona
```
