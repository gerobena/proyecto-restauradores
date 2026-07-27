# Métricas: qué mide cada una y qué supone

Referencia de las columnas que produce `notebooks/analisis.ipynb`. Si un número
del panel no cuadra con la intuición, la explicación está aquí.

**Regla que atraviesa todo el proyecto:** los cálculos se anclan a
`FECHA_CORTE_DATOS`, el último movimiento registrado en el libro, **nunca** a la
fecha de ejecución. Volver a correr el pipeline sobre los mismos archivos da
exactamente el mismo resultado.

---

## 1. Antigüedad del inventario (FIFO)

El libro de cada producto se reproduce como una cola: cada entrada (`COMPRA` o
`APERTURA`) agrega una capa con su fecha, y cada salida (`VENTA` o `AJUSTE`)
consume de la capa más antigua.

| Columna | Qué mide |
|---|---|
| `ANTIGUEDAD_STOCK_DIAS` | Días que lleva parado lo que **todavía está** en bodega, ponderado por unidad |
| `DIAS_ESTANTERIA_VENDIDO` | Días que estuvo en tienda lo que **ya se vendió**, ponderado por unidad |

Ejemplo: con 10 unidades, una que llegó hace 400 días y nueve hace 30:

```
ANTIGUEDAD = (1×400 + 9×30) / 10 = 67 días
```

**Por qué está ponderada por unidad.** El promedio simple diría 215 días, que no
representa a nada real. Ponderar por unidad hace que el número siga al dinero.

**Los `AJUSTE` consumen cola pero no cuentan como venta.** Un ajuste de migración
no es una operación comercial y no debe ensuciar el tiempo de estantería.

**Un producto sin stock no tiene antigüedad** (queda vacío, no cero). Si el
inventario dice 0 pero la cola FIFO tiene unidades, manda el inventario, que es
el dato verificable.

### Por qué no se usa el promedio entre ventas

La métrica anterior (`PROMEDIO_DIAS_VENTAS`, eliminada) medía **cada cuánto
ocurre una venta**. Ignoraba la cantidad vendida y la profundidad del stock, así
que un producto que vende 1 unidad cada 40 días se veía igual que uno que vende
50 cada 40 días.

El caso que lo dejó claro: el O-RING T458 vendía cada 35 días, así que figuraba
como "Estrella". Pero vendía 1,6 unidades al mes y había 419 en bodega: 21 años
de inventario. De los 357 productos clasificados como Estrella, 107 tenían más de
12 meses de cobertura.

---

## 2. Cobertura

```
COBERTURA_DIAS = unidades en stock / (unidades vendidas en los últimos 180 días / 180)
```

Cuántos días dura el stock al ritmo de venta reciente. Mira **hacia adelante**.

- **Cobertura 0** — no hay stock pero el producto se vende: reposición urgente
- **Cobertura vacía** — ninguna venta en 180 días, la división no tiene sentido
- **Cobertura alta** — hay inventario para años

Cobertura y antigüedad responden preguntas distintas. Un producto que acaba de
recibir un pedido grande tiene antigüedad baja y cobertura altísima; uno con
stock viejo que empezó a rotar tiene lo contrario. Por eso el mapa de decisión
las cruza en dos ejes.

---

## 3. Rotación en disponibilidad

```
VENTA_MENSUAL_EN_STOCK = unidades vendidas / meses en que SÍ hubo stock
```

Para productos agotados, donde la cobertura siempre da 0 y la antigüedad no
existe. La pregunta ahí es otra: **¿vendía bien cuando sí había mercadería?**

El denominador son los meses con existencias, no los meses de calendario. Así el
producto no queda castigado por los periodos en que el proveedor no despachó.

| Columna | Qué mide |
|---|---|
| `MESES_CON_STOCK` | Meses con existencias (la evidencia sobre la que se calcula) |
| `MESES_AGOTADO` | Meses consecutivos en cero al cierre |
| `DISPONIBILIDAD_PCT` | Qué porción de su vida estuvo disponible |
| `UNIDADES_PERDIDAS_EST` | Rotación en disponibilidad × meses agotado |

> ⚠️ **`UNIDADES_PERDIDAS_EST` es una estimación frágil, no una cifra contable.**
> Supone que habrías seguido vendiendo al mismo ritmo durante todo el periodo sin
> stock. Con poca historia se dispara: 879 productos tuvieron stock un solo mes y
> concentraban $391.703 de "utilidad perdida". Exigiendo 3 meses mínimos de
> historia la cifra baja a $12.381. Por eso el panel filtra por
> `MESES_CON_STOCK` y muestra esa columna. Sirve para priorizar, no para
> presupuestar.

---

## 4. Utilidad mensual en disponibilidad

```
UTILIDAD_MES = VENTA_MENSUAL_EN_STOCK × beneficio_promedio_por_producto
```

Se calcula en la app. Es la medida de **qué tan buen negocio es un producto**, y
no depende de si hoy tiene stock.

**Por qué no basta la rotación.** Un generador que vende 0,4 al mes y deja $810
por unidad es mejor negocio que un tornillo que vende 5 al mes y deja $0,10. Hay
405 productos que rotan menos de 0,5/mes pero dejan más de $5/mes: con un
criterio de rotación pura irían a "no comprar", y sería un error caro.

---

## 5. Utilidad neta

```
margen_bruto      = ingresos_sin_iva − costo_variable
margen_bruto_%    = margen_bruto / ingresos × 100

Por producto, dentro de su intervalo de exposición:
  intervalo       = [primer movimiento .. FECHA_CORTE_DATOS si tiene stock,
                     o último movimiento si no]
  cf_total        = costos fijos de esos meses, de SU comercio (ALMACEN o TALLER)
  pct_ingresos    = ingresos del producto / ingresos de la empresa en esos meses
  costo_asignado  = pct_ingresos × cf_total

  beneficio_neto  = margen_bruto − costo_asignado
  beneficio_promedio_por_producto = beneficio_neto / unidades vendidas
```

Los costos fijos salen de `costos_fijos_historico.xlsx`, mes a mes y separados
por división. Si el archivo no cubre algún mes del rango, se completa con el
valor conocido más cercano y el ETL avisa cuántos meses extrapoló.

`metrica_margen_bruto` agrupa `beneficio_promedio_por_producto` en Pérdida /
Beneficio Bajo / Medio / Alto con cortes en 0, 10 y 100 dólares.

> ⚠️ **Limitación conocida.** El denominador `ingresos_emp` suma las ventas de
> toda la empresa (ALMACEN y TALLER juntos), pero `cf_total` toma solo la columna
> del comercio del producto. Eso diluye la participación y hace que el reparto no
> absorba la totalidad de los costos fijos: sobre los datos actuales asigna
> ~$169.812 de ~$363.950 reales. La utilidad reportada es optimista en agregado.
> Viene del diseño original y no se ha corregido.

---

## 6. Capital inmovilizado

```
VALOR_STOCK = STOCK × COSTO       (COSTO viene del reporte de inventario)
```

Se reparte por tramo de antigüedad en `VALOR_0_60`, `VALOR_61_120`,
`VALOR_121_180` y `VALOR_MAS_180`.

**La distribución la pone FIFO; el monto lo pone el inventario.** En los
productos cuyo libro no cuadra, ambos difieren, así que el reparto se reescala
para sumar exactamente el capital reportado. Con eso el KPI y el gráfico de al
lado siempre dan el mismo porcentaje.

---

## 7. Cortes unificados

Definidos una sola vez en el notebook (`CORTES_DIAS`) y consumidos por todo lo
demás: KPI, gráficos, serie mensual y descargas.

| Días de antigüedad | Etiqueta (`ROTACION`) |
|---|---|
| 0 – 60 | Estrella |
| 61 – 120 | Optimo |
| 121 – 180 | Tomar Acción |
| > 180 | Tomar Acción Urgente |

`ROTACION` se calcula sobre la **antigüedad del stock**, no sobre la frecuencia
entre ventas, y solo existe para productos con stock.

### Umbrales del panel

Los tres primeros son deslizadores en la vista Operación. Los otros son
constantes al inicio de `app/app.py`, calibrados contra la distribución real del
catálogo:

| Parámetro | Valor | Significado |
|---|---|---|
| Reponer si cobertura < | 30 días | Ajustable |
| Exceso si cobertura > | 365 días | Ajustable |
| Liquidar si parado > | 180 días | Ajustable |
| `ROTACION_MINIMA` | 0,5 uds/mes | Entre el percentil 75 y el 90 |
| `MESES_AGOTADO_MAX` | 12 meses | Más tiempo se trata como descontinuado |
| `MESES_HISTORIA_MIN` | 3 meses | Mínimo para fiarse de la rotación |
| `UTILIDAD_MES_MINIMA` | $5/mes | La mediana del catálogo es $1,18 |

---

## 8. Reconstrucción del libro y banderas de calidad

El inventario inicial nunca se cargó como compras, y hubo una migración de
software que dejó productos sin corregir e ingresos manuales sin registrar. El
stock acumulado quedaba negativo en 22.060 registros producto-mes (18%).

**Criterio de reconstrucción:** la apertura de un producto es la cantidad que
hace cerrar el libro contra el inventario que hoy reporta el sistema.

```
desfase            = STOCK_HOY − neto_movimientos
STOCK_APERTURA_EST = max(0,  desfase)    entra un día antes del primer movimiento
AJUSTE_SALIDA      = max(0, −desfase)    sale en la fecha del último movimiento
```

Se ancla en el inventario actual porque es un dato verificable, a diferencia de
"lo mínimo para que no haya negativos", que es solo una cota inferior.

Resultado: los registros negativos bajaron de 22.060 (18%) a 2.342 (1,9%), y los
productos afectados de 1.265 a 278. **Ninguno quedó sin marcar.**

### Banderas

| `CALIDAD_DATOS` | Qué pasó | Qué se hizo |
|---|---|---|
| `OK` | El libro cuadra con el inventario | Nada |
| `APERTURA_ESTIMADA` | Salieron más unidades de las que entraron | Se inyectó capa inicial |
| `SALIDA_NO_REGISTRADA` | Sobran entradas: hay salidas nunca registradas | Se retiraron unidades al cierre |
| `NO_INVENTARIABLE` | Categoría SERVICIO | Nada, no llevan stock |
| `SIN_MOVIMIENTOS` | Está en inventario pero no en compras ni ventas | Nada |

Banderas independientes: `NEGATIVO_RESIDUAL` (el libro sigue sin cuadrar, sus
días no son confiables), `SIN_COMPRAS`, `VENTA_ANTICIPADA`.

> ⚠️ **La bandera de más cuidado es `SALIDA_NO_REGISTRADA`.** No se sabe *cuándo*
> ocurrió la salida real, así que se imputa al cierre. Para esos productos la
> antigüedad puede quedar subestimada: si la salida fue antes, las unidades que
> quedan son más viejas de lo que muestra el panel.

La lista de categorías no inventariables es editable en el notebook
(`CATEGORIAS_NO_INVENTARIABLES`). Hoy solo contiene `SERVICIO`, que cubre 20
productos. Si hay servicios de reparación facturados como REPUESTO, se les está
reconstruyendo un stock que no significa nada.

---

## Estado de los datos al 31/10/2025

| | |
|---|---|
| Productos | 5.876 (3.020 con stock) |
| Capital inmovilizado | $259.065 |
| Parado más de 180 días | $182.845 — **70,6%** |
| Antigüedad mediana del stock | **387 días** |
| Utilidad neta histórica | $696.616 |
| ALMACEN / TALLER estancado | 74,0% / 54,0% |

Reconstrucción aplicada: 17.015 unidades inyectadas como apertura y 9.486
retiradas como ajuste, sobre **3.234 productos ajustados** de 5.876 (2.622
cuadraban sin tocar nada y 20 son no inventariables).
