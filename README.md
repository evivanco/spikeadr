# Spike--ADR Pipeline V2 Visuals

Esta versión agrega visualizaciones más legibles para reemplazar el grafo bipartito cuando las líneas Spike→ADR son demasiado largas.

## Nuevos artefactos visuales

Por cada proyecto se generan:

```text
graph.png                         # Tabla visual Spike × ADR, recomendada
graph_bipartite_original.png      # Grafo bipartito original, complementario
graph_traceability_matrix.png     # Matriz Spike × ADR
graph_category_heatmap.png        # Heatmap Spike × categoría de incertidumbre
graph_agent_heatmap.png           # Heatmap Spike × agente analítico
graph_layered_process.png         # Diagrama por capas del proceso
```

La tabla `graph.png`, la matriz y los heatmaps son los artefactos recomendados para el reporte principal. El grafo bipartito queda como `graph_bipartite_original.png` y se mantiene solo como complemento.

## Ejecución individual

```bash
python pipeline.py run ^
  --pdf "D:/USM/Feria del software/USMSpike/HdU2026/G02CC_247453_assignsubmission_file_G02_Historias_LunarScan.pdf" ^
  --name "LunarScan" ^
  --group "G02_LunarScan" ^
  --output "D:/USM/Feria del software/USMSpike/HdU2026/results_batch"
```

Con PDF opcional:

```bash
python pipeline.py run ^
  --pdf "D:/ruta/proyecto.pdf" ^
  --name "Proyecto" ^
  --group "Proyecto" ^
  --output "D:/ruta/results" ^
  --compile-pdf
```

## Batch por carpeta

```bash
python run_batch_by_folder.py ^
  --input-dir "D:/USM/Feria del software/USMSpike/HdU2026" ^
  --output-dir "D:/USM/Feria del software/USMSpike/HdU2026/results_batch"
```

Probar solo 2 PDFs:

```bash
python run_batch_by_folder.py ^
  --input-dir "D:/USM/Feria del software/USMSpike/HdU2026" ^
  --output-dir "D:/USM/Feria del software/USMSpike/HdU2026/results_batch" ^
  --limit 2
```

## Nota para Windows

Usa rutas con `/` o raw strings en Python:

```python
Path(r"D:\USM\Feria del software\USMSpike\HdU2026")
```

o:

```python
Path("D:/USM/Feria del software/USMSpike/HdU2026")
```

## PDF LaTeX

`report.tex` se genera sin requerir LaTeX. Para `report.pdf` necesitas `pdflatex` en el PATH, por ejemplo mediante MiKTeX o TeX Live.


## Cambio de legibilidad en títulos

Los gráficos ya no incluyen por defecto el nombre del archivo/proyecto en el título. Esto evita títulos demasiado largos en ejecuciones batch.

Los títulos quedan así:

```text
Spike--ADR graph
Spike--ADR traceability matrix
Spike composition by uncertainty category
Spike composition by analytical agent
Layered Spike--ADR process
```

Si por alguna razón quieres volver a incluir el proyecto en los títulos, cambia en `pipeline.py`:

```python
include_project_in_titles=False
```

por:

```python
include_project_in_titles=True
```


## Cambio aplicado al primer gráfico

El archivo `graph.png` ya no corresponde al grafo bipartito con líneas largas. Ahora es una **tabla visual Spike--ADR** más legible, con columnas:

```text
Spike | Priority | Signal categories | Informs ADR | Blocks spike
```

El grafo original se conserva como:

```text
graph_bipartite_original.png
```


## Cambio aplicado: fuentes grandes en gráficos

Se aumentó el tamaño de letra de las figuras para que sean legibles dentro de `report.tex` y `report.pdf`.

Cambios principales:
- `graph.png` usa una tabla visual más grande.
- `graph_layered_process.png` usa cajas más amplias y texto más grande.
- Matriz y heatmaps usan etiquetas más grandes.
- Las imágenes se exportan a mayor resolución (`dpi=220`).
