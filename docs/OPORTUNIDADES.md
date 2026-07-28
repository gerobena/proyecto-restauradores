# Oportunidades de mejora — backlog

Ideas evaluadas contra los datos reales (corte 31/10/2025) el 28/07/2026.
**Ninguna está implementada.** Este documento es la lista de trabajo pendiente,
no una descripción del panel actual — para eso están [METRICAS.md](METRICAS.md)
y [CAMBIOS.md](CAMBIOS.md).

Los números de abajo salieron de `data/summary.parquet`,
`data/historico_mensual.parquet` y los reportes en `data/raw/`.

---

## Orden recomendado

| # | Qué | Depende de | Esfuerzo |
|---|---|---|---|
| 1 | Frescura de datos: semáforo y alerta de carga | — | Bajo |
| 2 | Cohortes "vence en 30/60/90 días" + Top 20 por capital | — | Bajo (solo panel) |
| 3 | Métrica de cruce mensual como objetivo | — | Bajo (solo panel) |
| 4 | Cliente + factura + proveedor al ETL | — | Medio |
| 5 | Corregir el reparto de costos fijos | — | Medio |
| 6 | Punto de reorden con lead time real | #4 | Medio |

Los puntos 2 y 3 no tocan el ETL: los datos ya están en los parquets.

---

## 0. Frescura de datos (bloquea todo lo demás)

`data_version.txt` marca `meses_desfase=9`: el panel muestra el 31/10/2025.
La carga de los tres reportes a OneDrive sigue siendo manual y es el cuello de
botella real del proyecto.

- Carpeta por mes en OneDrive (`2026-07/ventas.xlsx`) — elimina el error de nombrado
- Issue automático el día 5 si `data_cut` no avanzó (hoy solo avisa si el ETL **falla**,
  no si corre con datos viejos)
- Semáforo en el panel: verde <35 días, ámbar <70, rojo después

---

## 1. Objetivos mensuales y trimestrales

### Métrica madre: capital que cruza a >180 días

Capital que pasó de ≤180 a >180 días, por mes:

| Mes | Productos | Capital |
|---|---|---|
| 2025-05 | 79 | $26.847 |
| 2025-06 | 62 | **$70.931** |
| 2025-07 | 36 | $2.051 |
| 2025-08 | 70 | $4.460 |
| 2025-09 | 109 | $5.095 |
| 2025-10 | 106 | $6.655 |
| **Promedio 12 meses** | **100** | **$15.345/mes** |

Es un indicador **adelantado**: se mueve el mes en que ocurre el problema. El KPI
actual (70,6% del capital en >180) es acumulado y tarda trimestres en reaccionar.

Objetivo trimestral propuesto: *que crucen menos de $10.000/mes*.

### Cohortes por vencer

| Cohorte | Productos | Capital |
|---|---|---|
| 121–180 días | 241 | $17.958 |
| **151–180 días** (cruzan en 30 d) | **80** | **$7.151** |

El panel hoy solo muestra lo que **ya** cruzó, cuando el descuento necesario para
moverlo ya es mayor. Falta la lista de los que están por cruzar.

### Los tres números del tablero

| Objetivo | Tipo | Base actual |
|---|---|---|
| Capital que cruza a >180 | Flujo | $15.345/mes |
| Capital liberado de >180 | Flujo | — |
| % del capital en >180 | Resultado | 70,6% |

Los de flujo sirven para gestionar; el de resultado, para reportar. Mezclarlos es
lo que vuelve inútiles los tableros.

---

## 2. Concentración: dónde está realmente el dinero

> **11 productos concentran el 50% del capital estancado. 219 concentran el 80%.**

De esos 11, nueve son generadores:

| Código | Producto | Capital | Antigüedad | Rotación |
|---|---|---|---|---|
| 5813 | GENERADOR JC8000 SUKRA | $18.116 | 325 d | **0,00/mes** |
| 5812 | GENERADOR DG6500L SUKRA | $16.376 | 325 d | 0,09/mes |
| 5776 | GENERADOR HYUNDAI HYDG775E | $12.400 | 344 d | 0,42/mes |
| 5814 | GENERADOR JD2500 SUKRA | $11.495 | 325 d | 0,09/mes |
| 5816 | GENERADOR JD1200 SUKRA | $7.890 | 325 d | 0,09/mes |

Agregados:

- **GENERADORES**: 16 productos, $87.127 → **47% de todo el capital estancado**
- **SUKRA**: 6 productos, $61.873
- Sin subcategoría: 1.849 productos, $77.240

No es un problema difuso de inventario: es una decisión de compra puntual
(junio 2025, los $70.931 de la tabla anterior) que sigue costando plata.

**Idea:** KPI de concentración y vista *Top 20 a atacar* ordenada por capital, no
por antigüedad. Una lista de 1.993 productos es inmanejable; una de 11 es una
reunión de una hora.

**Contrapeso:** 1.744 productos tienen stock y cero ventas en 180 días, sumando
$151.121 (58% del capital). Eso es un remate por lote o una baja de catálogo, no
1.744 decisiones individuales.

---

## 3. Datos que los reportes ya traen y el ETL descarta

El reporte de ventas tiene 16 columnas y el pipeline usa cinco.

| Dimensión | Volumen | Qué habilita |
|---|---|---|
| Cliente | 7.682 únicos | Recompra, concentración, fuga |
| Nº de factura | 34.045 tickets | Ticket promedio, líneas/ticket, venta cruzada |
| Hora | En cada línea | Carga por hora y día → horarios de personal |
| Vendedor | 8 (3 con volumen real) | Ticket promedio por persona |
| Proveedor | 159 | Negociación, lead time, deriva de costo |

Columnas reales del reporte de ventas (`skiprows=6`, sin encabezado):

```
FECHA, CLIENTE, FACTURA, HORA, CATEGORIA, CODIGO, PRODUCTO,
CANT, PRECIO, DESC, IVA, TOTAL, COSTO, VENDEDOR, ACUM1, ACUM2
```

Y de compras:

```
CODIGO, TS, PROVEEDOR, TIPO, CANT, PRODUCTO, FECHA, COSTO
```

Hallazgos con solo agregarlas:

- **Ticket promedio $60,18, mediana $17, 1,67 líneas/ticket.** La distancia entre
  media y mediana dice que el negocio vive de pocas ventas grandes. Subir a 1,9
  líneas por ticket es un objetivo barato (góndola + sugerencia en mostrador).
- **57% de los clientes compraron una sola vez** (4.397 de 7.682).
- **Top 20 clientes = 18,9% de la venta; top 50 = 26,2%.** Poco concentrado para
  ferretería: el cliente contratista/empresa está sub-explotado.
- **Lead time real por proveedor** (fecha de orden vs. recepción). Hoy la regla de
  reposición usa 30 días fijos para los 5.876 productos, cuando un proveedor local
  repone en 3 días y uno importado en 60.

### Costo de no tener stock (ya calculable, sin tocar el ETL)

266 productos agotados que rendían ≥$5/mes y llevan ≤12 meses en cero suman
**$5.460/mes de utilidad no capturada**.

| Producto | Utilidad/mes perdida | Meses agotado |
|---|---|---|
| GENERADOR YDE8500E YORKING | $423 | 3 |
| GENERADOR KHOOLER DG-8500S | $193 | 0 |
| COMPRESOR CARIOCA 5.5HP 300LT | $154 | 8 |
| MOLINO ELECTRICO 1.5HP | $113 | 0 |

Se tienen $87.127 en generadores que no rotan y al mismo tiempo se está agotado
en los generadores que sí rotaban.

---

## 4. Operación del día a día

1. **Lista diaria de reposición imprimible** — una página, ordenada por urgencia,
   con espacio para marcar a mano. Un panel que hay que navegar se abre una vez
   por semana.
2. **Punto de reorden por producto**: `venta_diaria × lead_time_proveedor + colchón`.
   Requiere el lead time de la sección 3. Es la mejora que más ahorra de la lista.
3. **Higiene de catálogo** — 1.849 productos sin subcategoría, $77.240 de capital
   estancado. Mientras siga así ningún análisis por categoría es confiable ni
   delegable.
4. **Alerta de compra contra sobre-stock** — avisar en el ETL cuando entra
   mercadería de un producto con más de 365 días de cobertura. Es exactamente el
   error de junio 2025, detectable el mes en que ocurre.
5. **Carga por hora y día de la semana** — para horarios de personal y para
   decidir cuándo hacer inventario físico.

---

## 5. Control del estado del negocio

- **Cierre mensual de una página** el día 2: ventas, margen, capital inmovilizado,
  capital cruzado a >180 y los tres objetivos con semáforo. Por correo o como issue.
- **Comparativo contra el mismo mes del año anterior** — el histórico cubre 51
  meses desde 2021-08. La ferretería es estacional y el mes contra mes engaña.
- **Separar ALMACÉN y TALLER en la vista de gerencia** — los costos fijos ya se
  calculan por separado pero el panel los mezcla en varios lugares.
- **Corregir el reparto de costos fijos** — asigna ~$169.812 de ~$363.950 reales
  (ver limitación en METRICAS.md §5). Si el panel va a fijar objetivos de
  rentabilidad, este número tiene que estar bien primero.
