# CHANGELOG V2 — Table Graph

## Problema corregido

El grafo bipartito Spike→ADR no era legible cuando había muchos nodos o líneas largas.

## Cambio

`graph.png` ahora se genera como una tabla visual más representativa:

```text
Spike | Priority | Signal categories | Informs ADR | Blocks spike
```

El grafo bipartito anterior se conserva como:

```text
graph_bipartite_original.png
```

## Archivos modificados

- `graph_builder.py`
  - Nuevo `visualize_bipartite_dependency_table()`.
  - `generate_visual_artifacts()` ahora genera `graph.png` como tabla y `graph_bipartite_original.png` como complemento.
- `latex_report.py`
  - Inserta la tabla de dependencias antes del resto de figuras.
- `pipeline.py`
  - Actualiza el listado de artefactos en `SPIKES_ADR.md`.
- `README.md`
  - Documenta el cambio.
