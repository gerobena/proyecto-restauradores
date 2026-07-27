# Proyecto Restauradores — Panel de control de inventario

Panel en Streamlit para **Servicentro Restauradores**. Responde tres preguntas:
cuánto dinero hay parado en bodega, hace cuánto lo está, y qué conviene comprar
o dejar de comprar.

Los reportes de ventas, compras e inventario se suben a OneDrive, un pipeline en
GitHub Actions los procesa con un notebook, y el resultado se publica en
Streamlit Cloud.

- 📖 **[Definición de cada métrica](docs/METRICAS.md)** — qué mide, cómo se calcula y qué supone
- 📝 **[Historial de cambios](docs/CAMBIOS.md)** — qué cambió respecto a la versión anterior y por qué

---

## El panel

Se elige división (**ALMACEN** o **TALLER**) y vista en la barra lateral, y se
filtra por categoría, subcategoría y marca. Los filtros están encadenados: cada
uno solo ofrece valores que existen en la selección anterior.

### Vista Gerencia — cómo va el negocio

- **Capital inmovilizado**, cuánto lleva más de 180 días parado y la antigüedad promedio
- **Evolución mensual**: cantidad y porcentaje de productos estancados, mes a mes
- **Dónde está el capital**: reparto por tramo de antigüedad
- **Dónde se concentra el problema**: top 10 por categoría, subcategoría o marca
- **Pareto de utilidad**: qué porcentaje de SKUs genera el 80% de la ganancia

### Vista Operación — qué hacer esta semana

Tres listas, cada una descargable en Excel, con una columna `MOTIVO` que explica
por qué entró cada producto:

| Lista | Contiene |
|---|---|
| 🔴 **Reponer** | *Por agotarse* (queda poco stock) y *Agotado* (en cero pero vendía bien) |
| 🟡 **No comprar** | *No rinde* (deja poco al mes, tenga stock o no) y *Exceso* (bueno pero sobrecomprado) |
| 🟠 **Liquidar** | Lleva demasiado tiempo en bodega sin salir |

Debajo, un **mapa de decisión** que cruza antigüedad contra cobertura, donde el
tamaño de cada punto es el capital inmovilizado.

Al pie de ambas vistas hay un panel de **calidad de los datos** que muestra, para
los filtros activos, cuántos productos tienen el libro de movimientos corregido y
con qué supuestos. Ningún ajuste es silencioso.

---

## Cómo operarlo

### 1. Subir los reportes

En la carpeta de OneDrive `Restauradores_Ingesta_Reportes`, con estos nombres
exactos:

```
ventas_MM_YYYY.xlsx          el mes SIEMPRE con dos dígitos: 03, no 3
compras_MM_YYYY.xlsx         debe existir la del MISMO mes que ventas
inventario_YYYYMMDD.xlsx
costos_fijos_historico.xlsx  se actualiza solo cuando cambian los costos
```

Se aceptan `.xls`: el pipeline los convierte antes de procesarlos.

Si un archivo no cumple el formato, **el ETL se detiene y dice cuál es y qué se
esperaba**. Antes ese archivo simplemente se ignoraba y el panel seguía mostrando
datos viejos sin avisar.

### 2. Ejecutar el pipeline

Corre solo el día 2 de cada mes a las 04:00 UTC. Para lanzarlo al momento:
pestaña **Actions** del repositorio → *Retail ETL mensual* → **Run workflow**.

Si la corrida falla, se abre un **issue automático** con el enlace al log y las
causas más frecuentes.

### 3. Revisar

El panel avisa arriba del todo si los datos tienen más de dos meses, y el pie
muestra siempre **la fecha real de los datos**, no la de la última corrida del
pipeline. Son cosas distintas: el ETL puede ejecutarse hoy sobre reportes de hace
meses.

---

## Cómo funciona por dentro

```
OneDrive ──rclone──> data/raw/ ──notebook (papermill)──> data/*.parquet ──> Streamlit Cloud
```

1. **rclone** copia los reportes de OneDrive a `data/raw/` (que está en `.gitignore`).
2. **LibreOffice headless** convierte los `.xls` a `.xlsx`.
3. **`notebooks/analisis.ipynb`** valida los archivos, reconstruye el libro de
   movimientos, calcula las métricas y escribe dos parquets.
4. **GitHub Actions** commitea los parquets solo si cambiaron, y ese push
   dispara el redespliegue en Streamlit Cloud.

### Archivos que produce

| Archivo | Contenido |
|---|---|
| `data/summary.parquet` | 5.876 productos × 33 columnas: la foto actual |
| `data/historico_mensual.parquet` | 175.294 registros producto-mes desde 2021-08: la evolución |
| `data/data_version.txt` | Fecha de los datos, desfase y archivos usados |

### Estructura del repositorio

```
app/app.py                    dashboard
notebooks/analisis.ipynb      ETL completo
.github/workflows/etl.yml     automatización mensual
data/                         parquets publicados (raw está ignorado)
docs/                         métricas y changelog
```

---

## Desarrollo local

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

Levantar el panel:

```bash
.venv/Scripts/python -m streamlit run app/app.py
```

Regenerar los parquets (necesita los reportes en `data/raw/`):

```bash
.venv/Scripts/python -m papermill notebooks/analisis.ipynb salida.ipynb -p RAW_DIR data/raw -p OUTPUT_PARQUET data/summary.parquet -p OUTPUT_HIST_PARQUET data/historico_mensual.parquet
```

Tarda unos dos minutos. El resultado **no depende de cuándo lo ejecutes**: todo
se ancla a la última fecha del libro de movimientos.

---

## Tecnologías

Python 3.12 · pandas · numpy · pyarrow · openpyxl · Streamlit · Plotly ·
papermill · rclone · LibreOffice headless · GitHub Actions
