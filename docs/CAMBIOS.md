# Historial de cambios

Qué cambió respecto a la versión anterior del panel, por qué, y qué efecto tuvo
sobre los números. Las definiciones completas están en [METRICAS.md](METRICAS.md).

---

## 2026-07 — Blindaje del ETL y anclaje temporal

Commit [`0e7a846`](https://github.com/gerobena/proyecto-restauradores/commit/0e7a846)

### El cálculo dependía de cuándo se ejecutaba

`TODAY = pd.Timestamp.today()` entraba en dos cálculos, así que volver a correr
el pipeline sobre los mismos archivos daba resultados distintos. Con las ventas
detenidas en 2025-10, cada corrida mensual sumaba costos fijos contra ingresos
que no existen en esos meses:

| Corrida | Multiplicador cf/ingresos | vs nov-2025 |
|---|---|---|
| 02/11/2025 | 8,71% | — |
| 02/07/2026 | 10,32% | +18,5% |
| 02/02/2027 | 11,73% | +34,7% |

Se reemplazó por `FECHA_CORTE_DATOS`, el último movimiento del libro.

**Efecto:**

| | Antes | Ahora |
|---|---|---|
| Utilidad neta total | $676.330 | **$696.616** (+3,0%) |
| Productos en Pérdida | 80 | **38** |
| Peor producto | −$116,86 | −$15,73 |

42 productos figuraban como pérdida solo por el calendario. Stock, unidades,
margen bruto, antigüedad y cobertura quedaron idénticos: las métricas FIFO ya
estaban ancladas.

### Un archivo mal nombrado ya no se ignora en silencio

El caso peligroso era `ventas_3_2026.xlsx` (mes de un dígito): no coincidía con
el patrón de dos dígitos, el ETL usaba el archivo viejo que sí coincidía, y nadie
se enteraba. Ahora la validación corta con el nombre del archivo y el formato
esperado. Probado con ocho escenarios:

| Escenario | Antes | Ahora |
|---|---|---|
| Mes de un dígito | Silencio | Error nombrando archivo y formato |
| Ventas sin su compra del mes | `IndexError: list index out of range` | Dice qué falta y lista lo disponible |
| Falta `costos_fijos_historico.xlsx` | `KeyError` a mitad del bucle | Se corta al inicio, explicando por qué |
| Falta el inventario | Error genérico | Lista los `.xlsx` encontrados |
| Temporal de Excel `~$...` | — | Se ignora correctamente |

La validación mira el **nombre**, no la extensión: un `.xls` es entrada legítima
porque el workflow lo convierte antes de ejecutar el notebook.

### Los costos fijos habrían roto el ETL en marzo de 2027

`costos_fijos_historico.xlsx` llega hasta 2027-02. El `.loc` con meses fuera de
rango habría lanzado `KeyError` en la corrida del 2027-03. Ahora se completa el
rango con el valor conocido más cercano y se avisa cuántos meses se extrapolaron.

### El panel dice la verdad sobre sus datos

`data_version.txt` separa dos cosas que antes se confundían:

```
data_cut=2025-10-31    ← fecha real de los datos, la escribe el notebook
last_run=...           ← cuándo corrió el pipeline, lo agrega el workflow
```

El panel mostraba la segunda como si fuera la primera. Ahora avisa arriba del
todo si los datos pasan de dos meses, y el pie dice **"Datos al DD/MM/YYYY"**.

### Workflow

- Deja de commitear cuando los parquets no cambian. El timestamp de
  `data_version.txt` forzaba un commit vacío cada mes.
- Abre un **issue automático** si la corrida falla, con enlace al log y las
  causas frecuentes. Antes un fallo era silencioso.

---

## 2026-07 — Antigüedad real del inventario y panel por rol

Commit [`aa7ac7c`](https://github.com/gerobena/proyecto-restauradores/commit/aa7ac7c)

### La métrica de rotación medía otra cosa

`PROMEDIO_DIAS_VENTAS` medía **cada cuánto ocurre una venta**: ignoraba la
cantidad vendida y la profundidad del stock. De 357 productos clasificados como
"Estrella", **107 tenían más de 12 meses de cobertura**; 46 más de 24 meses y 10
más de cinco años.

Se reemplazó por antigüedad FIFO y cobertura móvil. El motor FIFO se validó con
siete pruebas unitarias antes de integrarlo — una encontró un fallo real: sin
cortes mensuales, los movimientos no se procesaban.

### Utilidad neta con los costos fijos reales

El pipeline exportaba `resumen_final`, que repartía una constante de $300.000
entre todos los productos sin distinguir división. Ya existía calculado
`resumen_final_real`, que lee `costos_fijos_historico.xlsx` mes a mes y separado
por ALMACEN/TALLER, pero no se exportaba.

**Efecto:** 107 productos salieron de "Pérdida" (no lo eran) y 34 entraron (nadie
los veía). La utilidad media de ALMACEN pasó de $19,57 a $27,48 y la de TALLER de
$6,14 a $7,39: antes las dos divisiones estaban mezcladas. El margen bruto quedó
idéntico, que es el control esperado.

### Reconstrucción del libro de movimientos

El inventario inicial nunca se cargó como compras, más una migración de software
e ingresos manuales sin registrar. El stock acumulado era negativo en 22.060
registros producto-mes (18%), afectando a 1.265 productos.

| | Antes | Ahora |
|---|---|---|
| Registros negativos | 22.060 (18,2%) | **2.342 (1,9%)** |
| Productos afectados | 1.265 | **278** |
| Sin marcar | — | **0** |

El negativo más grande de todo el catálogo (−12.881) resultó ser el código 1160
"SERVICIO DE REPARACIÓN", que quedó correctamente clasificado como no
inventariable y sin tocar.

### El panel se separó en dos vistas

Antes era una sola pantalla con cuatro KPIs, dos gráficos de barras y tres
descargas. Ahora:

- **Gerencia** — capital inmovilizado y su antigüedad, evolución mensual,
  concentración del problema, pareto de utilidad
- **Operación** — tres listas de trabajo con columna `MOTIVO` y mapa de decisión

### "No comprar" juzga el producto, no el stock

Primero la lista solo miraba cobertura, así que un producto malo con poco stock
no aparecía. Se cambió a **utilidad mensual en disponibilidad** (rotación ×
margen), que es una propiedad del producto y sirve para revisar línea por línea
un pedido al proveedor.

Con rotación pura se habrían descartado 405 productos que rotan lento pero dejan
buen margen. Y aparecieron 1.071 productos **con stock** que antes no salían en
ninguna lista, entre ellos tres generadores de la misma marca con $35.761 de
capital atrapado rotando 0,09 unidades/mes.

### Correcciones

- **Etiquetas de los gráficos**: decían "61-90" y "91-180" sobre cortes reales de
  120 y 180 días.
- **KPI contra gráfico**: el mismo dato se mostraba como 81,2% y 74,8% en
  elementos contiguos. El reparto por tramo ahora se reescala para cuadrar con el
  capital total.
- **Filtros encadenados**: marca y subcategoría solo ofrecen valores existentes.
- **Caché por fecha de archivo**: antes había que limpiarlo a mano tras
  regenerar el parquet.
- **Excel cacheados**: se construían en cada rerun aunque nadie los descargara.

### Limpieza del pipeline

Se eliminaron `PROMEDIO_DIAS_VENTAS`, `TPA` y toda su maquinaria (33 celdas),
incluido un bucle que recalculaba lo mismo que la versión optimizada. Se verificó
con análisis de dependencias que nada fuera de ese conjunto las usaba.

**El ETL bajó de 5,6 a 1,9 minutos.**

---

## Verificaciones realizadas

- **Reproducibilidad, comprobada en producción**: la corrida real del ETL en
  GitHub Actions (`e30da62`, 27/07/2026) produjo valores **idénticos** a los
  generados en local — cero diferencias en las 33 columnas del summary y en los
  175.294 registros del histórico. Los archivos difieren en tamaño solo por la
  versión de pyarrow. El `data_version.txt` quedó con `data_cut` del notebook y
  `last_run` del workflow, como estaba diseñado.
- **Compatibilidad de versiones**: el notebook se ejecutó con los pines exactos
  del CI (Python 3.12, pandas 2.2.3, numpy 2.4.2, pyarrow 23.0.1) y produjo
  resultados idénticos a los de desarrollo, sin warnings.
- **Unificación de métricas**: la antigüedad de la foto coincide con el último
  mes de la serie histórica con diferencia máxima de 0,0 días sobre 3.019
  productos comparables.
- **Motor FIFO**: siete pruebas unitarias (orden de consumo, ponderación por
  unidad, ajustes que no cuentan como venta, salidas sin capa, series mensuales).
- **Cobertura de banderas**: de los 278 productos que siguen con algún mes
  negativo, ninguno quedó sin marcar.

---

## Pendientes conocidos

1. **El reparto de costos fijos no absorbe el total.** El denominador suma las
   ventas de ambas divisiones pero el numerador toma los costos de una sola:
   asigna ~$169.812 de ~$363.950 reales. Viene del diseño original.
2. **`tiempo_promedio_ventas` se sigue calculando** aunque sus columnas ya no se
   exportan, porque es el marco base de `resumen_final`. Quitarlo implica
   reconstruir ese marco desde otra fuente, que tiene 5.881 productos frente a
   los 5.876 que llegan al panel.
3. **Categorías no inventariables**: la lista solo contiene `SERVICIO` (20
   productos). Si hay servicios facturados como REPUESTO, se les reconstruye un
   stock sin sentido.
4. **Un producto con stock quedó sin antigüedad**: tiene inventario pero el libro
   no tiene capas que lo respalden. Sale marcado en el panel de calidad.
5. **Propuesta pendiente**: una carpeta por mes en OneDrive
   (`2026-07/ventas.xlsx`) eliminaría de raíz los errores de nombrado.
