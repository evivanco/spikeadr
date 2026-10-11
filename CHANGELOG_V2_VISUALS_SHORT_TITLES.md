# CHANGELOG V2 Visuals — Short Titles

## Cambio aplicado

Se modificó `graph_builder.py` para que `generate_visual_artifacts()` no incluya por defecto el nombre del archivo/proyecto en los títulos de los gráficos.

Esto corrige casos donde el título quedaba demasiado largo, por ejemplo:

```text
Spike-ADR: AppCopio (G4_MARTINA_PAZ_TEJO_ALARCON_4849300_assignsubmission_file_G04_Historias_AppCopio)
```

Ahora los gráficos usan títulos cortos:

```text
Spike--ADR graph
Spike--ADR traceability matrix
Spike composition by uncertainty category
Spike composition by analytical agent
Layered Spike--ADR process
```

## Archivos modificados

- `graph_builder.py`
- `pipeline.py`
- `README.md`

## Reversibilidad

Para volver a mostrar el nombre del proyecto en los títulos, usar:

```python
include_project_in_titles=True
```

en la llamada a `generate_visual_artifacts()` dentro de `pipeline.py`.
