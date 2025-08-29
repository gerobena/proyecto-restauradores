# Proyecto Restauradores — Dashboard de Inventario y Ventas

📊 **PANEL DE CONTROL - SERVICENTRO RESTAURADORES**

Este proyecto implementa un **dashboard interactivo en Streamlit** para monitorizar el desempeño de inventario, ventas y compras de la tienda **Servicentro Restauradores**.  

El flujo está **100% automatizado con herramientas open source**: los datos de **ventas, compras e inventario** se cargan mensualmente desde **OneDrive**, se procesan en un **Jupyter Notebook** y se publican en **Streamlit Cloud** a través de un pipeline en **GitHub Actions**.

---

## 🚀 Funcionalidad principal

El dashboard permite:

- Monitorear el **tiempo promedio de ventas (DSI)** por producto.
- Analizar el **margen bruto %** y la **utilidad neta promedio** por producto.
- Visualizar métricas clave:
  - ⏳ **Días promedio de venta (DSI)**
  - 💰 **Margen Bruto %**
  - 📈 **Utilidad Neta promedio por SKU**
  - 🔢 **Total SKUs activos**
- Gráficos interactivos:
  - 📦 Distribución de productos por rangos de tiempo de venta.
  - 💵 Distribución de productos según nivel de utilidad neta.
- Descarga en Excel de productos críticos:
  - Productos con **más de 180 días en stock**.
  - Productos “**Estrella**” (0–60 días) pero **faltantes en stock**.
  - Productos en **pérdida** (margen negativo).
- Ranking de **Top 5 slow movers** (productos más lentos en rotación).

---

## ⚙️ Flujo de datos (pipeline ETL)

1. **Carga de archivos fuente**  
   - Los administradores colocan mensualmente 3 archivos en OneDrive:
     - `ventas_MM_YYYY.xlsx`
     - `compras_MM_YYYY.xlsx`
     - `inventario_YYYYMMDD.xlsx`

2. **Ingesta automática con rclone**  
   - GitHub Actions sincroniza la carpeta `Restauradores_Ingesta_Reportes` de OneDrive → `data/raw/`.

3. **Procesamiento en Jupyter Notebook**  
   - El notebook `notebooks/analisis.ipynb`:
     - Detecta automáticamente los archivos más recientes.
     - Convierte `.xls` → `.xlsx` con LibreOffice (si es necesario).
     - Realiza cálculos de KPIs y métricas de negocio.
     - Genera un dataframe final `resumen_final`.

4. **Optimización y exportación**  
   - El dataframe se guarda como `data/summary.parquet` optimizado (tipos categóricos, compresión ZSTD).

5. **Visualización en Streamlit**  
   - La app `app/app.py` consume `summary.parquet` y muestra el dashboard interactivo.

6. **Automatización mensual con GitHub Actions**  
   - Workflow `.github/workflows/etl.yml`:
     - Se ejecuta cada mes (o manualmente).
     - Actualiza `summary.parquet`.
     - Hace commit y dispara redeploy en Streamlit Cloud.

---

## 🛠️ Tecnologías utilizadas

- **Python 3.12**  
- **Pandas, Numpy** (análisis de datos)  
- **OpenPyXL** (lectura y exportación a Excel)  
- **Plotly Express** (gráficos interactivos)  
- **Streamlit** + `streamlit-option-menu` (interfaz del dashboard)  
- **Papermill** (ejecución de notebooks en pipeline)  
- **PyArrow** (manejo de Parquet optimizado)  
- **Rclone** (sincronización con OneDrive)  
- **LibreOffice headless** (conversión automática de `.xls` a `.xlsx`)  
- **GitHub Actions** (automatización mensual)