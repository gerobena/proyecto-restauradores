import io
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from openpyxl.styles import numbers
from openpyxl.utils import get_column_letter
from plotly.subplots import make_subplots
from streamlit_option_menu import option_menu

st.set_page_config(page_title="Dashboard Inventario", layout="wide")

APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent
DATA_PATH = ROOT_DIR / "data" / "summary.parquet"
HIST_PATH = ROOT_DIR / "data" / "historico_mensual.parquet"
VERSION_PATH = ROOT_DIR / "data" / "data_version.txt"
LOGO_PATH = APP_DIR / "logo2.png"

NARANJA = "#FF7F0E"
OSCURO = "#111827"

# Cortes de antiguedad. Son los mismos que usa el notebook (CORTES_DIAS).
# Si cambian alla, cambian aca.
UMBRAL_DIAS = 180
ETIQUETAS_TRAMO = ["0-60 días", "61-120 días", "121-180 días", ">180 días"]
ORDEN_ROTACION = ["Estrella", "Optimo", "Tomar Accion", "Tomar Accion Urgente"]
COLS_VALOR_TRAMO = ["VALOR_0_60", "VALOR_61_120", "VALOR_121_180", "VALOR_MAS_180"]

# Criterios para decidir sobre productos agotados. Van fijos y no como control en
# pantalla: se calibraron contra la distribución real del catálogo y no son
# decisiones del día a día. Para cambiarlos se editan aquí.
ROTACION_MINIMA = 0.5      # unidades/mes vendidas en los meses que sí hubo stock
MESES_AGOTADO_MAX = 12     # más tiempo en cero que esto se trata como descontinuado
MESES_HISTORIA_MIN = 3     # meses con stock necesarios para fiarse de la rotación
UTILIDAD_MES_MINIMA = 5.0  # USD/mes que debe dejar un producto para valer la pena pedirlo


# --------------------------------------------------------------------------- #
# Carga de datos
# --------------------------------------------------------------------------- #
@st.cache_data
def load_data(path: Path, mtime: float) -> pd.DataFrame:
    """El mtime entra en la firma para que el cache se invalide al regenerar el parquet."""
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def leer(path: Path) -> pd.DataFrame:
    return load_data(path, path.stat().st_mtime if path.exists() else 0.0)


@st.cache_data
def _version_datos(path: Path, mtime: float) -> dict:
    """data_version.txt: la fecha de los datos y la de la corrida no son lo mismo."""
    if not path.exists():
        return {}
    try:
        return dict(
            linea.split("=", 1)
            for linea in path.read_text(encoding="utf-8").splitlines()
            if "=" in linea
        )
    except Exception:
        return {}


def _fecha_es(valor) -> str:
    if not valor:
        return "N/D"
    try:
        return datetime.strptime(valor.split("T", 1)[0], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return "N/D"


version = _version_datos(
    VERSION_PATH, VERSION_PATH.stat().st_mtime if VERSION_PATH.exists() else 0.0
)
fecha_datos = _fecha_es(version.get("data_cut"))
fecha_corrida = _fecha_es(version.get("last_run"))

try:
    meses_desfase = int(version.get("meses_desfase", "0"))
except (TypeError, ValueError):
    meses_desfase = 0


df_full = leer(DATA_PATH)

if df_full.empty:
    st.title("PANEL DE CONTROL - SERVICENTRO RESTAURADORES")
    st.warning("⚠️ No se encontró `data/summary.parquet`. Ejecuta el notebook o el pipeline.")
    st.stop()


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
FORMATOS = {
    "moneda": numbers.FORMAT_CURRENCY_USD_SIMPLE,
    "entero": "0",
    "porcentaje": numbers.FORMAT_PERCENTAGE,
}


@st.cache_data
def construir_excel(datos: pd.DataFrame, hoja: str, formatos: dict) -> bytes:
    """Arma un Excel con formato. Cacheado: no se reconstruye en cada rerun."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        datos.to_excel(writer, index=False, sheet_name=hoja)
        ws = writer.sheets[hoja]

        for columna, tipo in formatos.items():
            if columna not in datos.columns:
                continue
            n = datos.columns.get_loc(columna) + 1
            for fila in ws.iter_rows(min_row=2, min_col=n, max_col=n):
                for celda in fila:
                    celda.number_format = FORMATOS[tipo]

        for celdas in ws.columns:
            ancho = max(len(str(c.value)) for c in celdas)
            ws.column_dimensions[get_column_letter(celdas[0].column)].width = ancho + 2

    return buffer.getvalue()


def boton_excel(datos: pd.DataFrame, etiqueta: str, archivo: str, hoja: str, formatos: dict):
    if datos.empty:
        st.caption(f"Sin productos en esta condición · {etiqueta}")
        return
    st.download_button(
        label=f"📥 {etiqueta} ({len(datos):,})",
        data=construir_excel(datos, hoja, formatos),
        file_name=archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


def kpi_dinero(valor: float) -> str:
    return f"${valor:,.0f}"


def titulo_grafico(fig, texto: str):
    fig.update_layout(
        title=dict(text=texto, x=0, xanchor="left"),
        margin=dict(t=60, b=40),
    )
    return fig


# --------------------------------------------------------------------------- #
# Barra lateral
# --------------------------------------------------------------------------- #
with st.sidebar:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)

    seleccion_div = option_menu(
        menu_title=None,
        options=["ALMACEN", "TALLER"],
        icons=["house", "gear"],
        menu_icon="list",
        default_index=0,
        orientation="vertical",
        styles={
            "container": {"padding": "0!important", "background-color": OSCURO},
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "margin": "0px",
                "color": "#ffffff",
                "padding": "8px 16px",
            },
            "nav-link-selected": {"background-color": NARANJA, "color": "#ffffff"},
            "icon": {"color": "#ffffff", "font-size": "18px"},
        },
    )

    st.markdown("---")
    vista = option_menu(
        menu_title="VISTA",
        options=["Gerencia", "Operación"],
        icons=["graph-up", "box-seam"],
        default_index=0,
        orientation="vertical",
        styles={
            "container": {"padding": "0!important", "background-color": OSCURO},
            "menu-title": {"color": "#9ca3af", "font-size": "12px"},
            "nav-link": {
                "font-size": "15px",
                "text-align": "left",
                "margin": "0px",
                "color": "#ffffff",
                "padding": "8px 16px",
            },
            "nav-link-selected": {"background-color": NARANJA, "color": "#ffffff"},
            "icon": {"color": "#ffffff", "font-size": "16px"},
        },
    )

st.title("PANEL DE CONTROL - SERVICENTRO RESTAURADORES")

if meses_desfase > 2:
    st.warning(
        f"**Los datos tienen {meses_desfase} meses de antigüedad** — el último movimiento "
        f"registrado es del {fecha_datos}. Todo lo que ves abajo es la foto de esa fecha, "
        "no la de hoy. Para actualizarlo hay que subir los reportes nuevos a la carpeta de "
        "ingesta en OneDrive y volver a ejecutar el pipeline.",
        icon="⚠️",
    )

# --------------------------------------------------------------------------- #
# Filtros
# --------------------------------------------------------------------------- #
df_div = df_full[df_full["COMERCIO"] == seleccion_div]

col1, col2, col3 = st.columns(3)
with col1:
    categorias = ["Todas"] + sorted(df_div["CATEGORIA"].dropna().unique().tolist())
    sel_cat = st.selectbox("Categoría", categorias)

# Los filtros se encadenan: solo se ofrecen valores que existen en la selección previa
df_paso = df_div if sel_cat == "Todas" else df_div[df_div["CATEGORIA"] == sel_cat]

with col2:
    subcats = ["Todas"] + sorted(df_paso["SUBCATEGORIA"].dropna().unique().tolist())
    sel_sub = st.selectbox("Subcategoría", subcats)

df_paso = df_paso if sel_sub == "Todas" else df_paso[df_paso["SUBCATEGORIA"] == sel_sub]

with col3:
    marcas = ["Todas"] + sorted(df_paso["MARCA"].dropna().unique().tolist())
    sel_mar = st.selectbox("Marca", marcas)

df = df_paso if sel_mar == "Todas" else df_paso[df_paso["MARCA"] == sel_mar]

if df.empty:
    st.warning("No hay datos para los filtros seleccionados.")
    st.stop()

con_stock = df[df["STOCK"] > 0]


# --------------------------------------------------------------------------- #
# Serie mensual (compartida por las dos vistas)
# --------------------------------------------------------------------------- #
@st.cache_data
def serie_mensual(hist: pd.DataFrame, umbral: int) -> pd.DataFrame:
    """Por mes: productos con stock, cuántos superan el umbral de antigüedad y qué % son."""
    activos = hist[hist["STOCK_MENSUAL"] > 0]
    serie = (
        activos.assign(SUPERA=lambda d: (d["ANTIGUEDAD_DIAS"] > umbral).astype(int))
        .groupby("FECHA_CORTE", as_index=False, observed=True)
        .agg(TOTAL_CON_STOCK=("CODIGO", "nunique"), CANTIDAD=("SUPERA", "sum"))
        .sort_values("FECHA_CORTE")
        .reset_index(drop=True)
    )
    serie["TASA_PCT"] = (serie["CANTIDAD"] / serie["TOTAL_CON_STOCK"] * 100).round(1)
    return serie


def hist_filtrado() -> pd.DataFrame:
    hist = leer(HIST_PATH)
    if hist.empty:
        return hist
    h = hist[hist["COMERCIO"] == seleccion_div]
    if sel_cat != "Todas":
        h = h[h["CATEGORIA"] == sel_cat]
    if sel_sub != "Todas":
        h = h[h["SUBCATEGORIA"] == sel_sub]
    if sel_mar != "Todas":
        h = h[h["MARCA"] == sel_mar]
    return h


def bloque_evolucion():
    st.subheader(f"EVOLUCIÓN MENSUAL — INVENTARIO SOBRE {UMBRAL_DIAS} DÍAS")

    h = hist_filtrado()
    if h.empty:
        st.info(
            "No se encontró `data/historico_mensual.parquet`. "
            "Ejecuta el notebook o el pipeline para generarlo."
        )
        return

    serie = serie_mensual(h, UMBRAL_DIAS)
    if serie.empty:
        st.warning("No hay histórico mensual para los filtros seleccionados.")
        return

    rangos = {"Últimos 12 meses": 12, "Últimos 24 meses": 24, "Todo el histórico": None}
    sel_rango = st.selectbox("Periodo", list(rangos.keys()), index=1)
    n = rangos[sel_rango]
    serie = serie.tail(n) if n else serie

    ultimo = serie.iloc[-1]
    previo = serie.iloc[-2] if len(serie) > 1 else None

    e1, e2, e3 = st.columns(3)
    e1.metric(
        f"Productos > {UMBRAL_DIAS} días",
        f"{int(ultimo['CANTIDAD']):,}",
        delta=None if previo is None else f"{int(ultimo['CANTIDAD'] - previo['CANTIDAD']):+,}",
        delta_color="inverse",
    )
    e2.metric(
        "Tasa sobre stock activo",
        f"{ultimo['TASA_PCT']:,.1f}%",
        delta=None if previo is None else f"{ultimo['TASA_PCT'] - previo['TASA_PCT']:+.1f} pp",
        delta_color="inverse",
        help="Qué porcentaje de los productos con stock lleva más del umbral parado.",
    )
    e3.metric(
        "Productos con stock",
        f"{int(ultimo['TOTAL_CON_STOCK']):,}",
        delta=None if previo is None else f"{int(ultimo['TOTAL_CON_STOCK'] - previo['TOTAL_CON_STOCK']):+,}",
    )

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(
            x=serie["FECHA_CORTE"],
            y=serie["CANTIDAD"],
            name=f"Cantidad > {UMBRAL_DIAS} días",
            marker_color=NARANJA,
            hovertemplate="<b>%{x|%b %Y}</b><br>Cantidad: %{y:,}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=serie["FECHA_CORTE"],
            y=serie["TASA_PCT"],
            name="Tasa [%]",
            mode="lines+markers",
            line=dict(color=OSCURO, width=2),
            hovertemplate="<b>%{x|%b %Y}</b><br>Tasa: %{y:.1f}%<extra></extra>",
        ),
        secondary_y=True,
    )
    fig.update_xaxes(title_text="Mes", tickformat="%b %Y")
    fig.update_yaxes(title_text="Cantidad de productos", tickformat="d", rangemode="tozero", secondary_y=False)
    fig.update_yaxes(title_text="Tasa sobre stock activo", range=[0, 100], ticksuffix="%", showgrid=False, secondary_y=True)
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
    )
    st.plotly_chart(titulo_grafico(fig, f"Antigüedad del inventario — {seleccion_div}"), use_container_width=True)
    st.caption(
        "Los primeros meses del histórico tienen pocos productos con stock, "
        "por lo que su tasa no es comparable con la de los meses recientes."
    )


# --------------------------------------------------------------------------- #
# Vista GERENCIA
# --------------------------------------------------------------------------- #
def vista_gerencia():
    valor_total = float(df["VALOR_STOCK"].sum())
    valor_viejo = float(df["VALOR_MAS_180"].sum())
    pct_viejo = (valor_viejo / valor_total * 100) if valor_total > 0 else 0.0

    unidades = float(con_stock["STOCK"].sum())
    antiguedad_pond = (
        float((con_stock["ANTIGUEDAD_STOCK_DIAS"] * con_stock["STOCK"]).sum() / unidades)
        if unidades > 0
        else 0.0
    )

    utilidad_total = float(
        (df["beneficio_promedio_por_producto"] * df["unidades_vendidas_totales"]).sum()
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Capital inmovilizado", kpi_dinero(valor_total), help="STOCK × COSTO de todo lo que hay en bodega.")
    k2.metric(
        f"Parado > {UMBRAL_DIAS} días",
        kpi_dinero(valor_viejo),
        delta=f"{pct_viejo:,.1f}% del total",
        delta_color="off",
    )
    k3.metric("Utilidad neta histórica", kpi_dinero(utilidad_total), help="Después de asignar costos fijos reales.")
    k4.metric(
        "Antigüedad promedio",
        f"{antiguedad_pond:,.0f} días",
        help="Días que lleva parado el inventario, ponderado por unidad.",
    )

    st.divider()
    bloque_evolucion()

    st.divider()
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("DÓNDE ESTÁ EL CAPITAL")
        valores = [float(df[c].sum()) for c in COLS_VALOR_TRAMO]
        datos = pd.DataFrame({"Tramo": ETIQUETAS_TRAMO, "Capital": valores})
        datos["Pct"] = (
            datos["Capital"] / datos["Capital"].sum() * 100 if datos["Capital"].sum() > 0 else 0
        )

        fig = px.bar(
            datos,
            x="Tramo",
            y="Capital",
            text="Pct",
            category_orders={"Tramo": ETIQUETAS_TRAMO},
            color_discrete_sequence=[NARANJA],
        )
        fig.update_traces(
            texttemplate="%{text:.1f}%",
            textposition="inside",
            textfont=dict(size=14, color="black"),
            hovertemplate="<b>%{x}</b><br>Capital: $%{y:,.0f}<br>%{text:.1f}% del total<extra></extra>",
        )
        fig.update_yaxes(title_text="Capital inmovilizado", tickprefix="$")
        fig.update_xaxes(title_text="Antigüedad del stock")
        st.plotly_chart(
            titulo_grafico(fig, f"Capital por antigüedad — {seleccion_div}"), use_container_width=True
        )

    with c2:
        st.subheader("DÓNDE SE CONCENTRA EL PROBLEMA")
        eje = st.radio("Agrupar por", ["CATEGORIA", "SUBCATEGORIA", "MARCA"], horizontal=True, key="eje_ger")
        top = (
            df.groupby(eje, observed=True)["VALOR_MAS_180"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        top = top[top["VALOR_MAS_180"] > 0]

        if top.empty:
            st.info("No hay capital estancado con los filtros actuales.")
        else:
            fig = px.bar(top, x="VALOR_MAS_180", y=eje, orientation="h", color_discrete_sequence=[NARANJA])
            fig.update_yaxes(title_text="", autorange="reversed")
            fig.update_xaxes(title_text=f"Capital parado > {UMBRAL_DIAS} días", tickprefix="$")
            fig.update_traces(hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>")
            st.plotly_chart(
                titulo_grafico(fig, f"Top 10 por capital estancado"), use_container_width=True
            )

    st.divider()
    st.subheader("CONCENTRACIÓN DE LA UTILIDAD")
    pareto = df.assign(
        UTILIDAD=lambda d: d["beneficio_promedio_por_producto"] * d["unidades_vendidas_totales"]
    )
    pareto = pareto[pareto["UTILIDAD"] > 0].sort_values("UTILIDAD", ascending=False)

    if pareto.empty:
        st.info("No hay utilidad positiva con los filtros actuales.")
    else:
        pareto["ACUM_PCT"] = pareto["UTILIDAD"].cumsum() / pareto["UTILIDAD"].sum() * 100
        pareto["RANK_PCT"] = np.arange(1, len(pareto) + 1) / len(pareto) * 100
        n80 = int((pareto["ACUM_PCT"] <= 80).sum()) + 1
        pct80 = n80 / len(pareto) * 100

        fig = px.area(pareto, x="RANK_PCT", y="ACUM_PCT", color_discrete_sequence=[NARANJA])
        fig.add_hline(y=80, line_dash="dash", line_color=OSCURO)
        fig.update_xaxes(title_text="% de SKUs (ordenados por utilidad)", ticksuffix="%", range=[0, 100])
        fig.update_yaxes(title_text="% de la utilidad acumulada", ticksuffix="%", range=[0, 100])
        fig.update_traces(hovertemplate="%{x:.1f}% de SKUs → %{y:.1f}% de la utilidad<extra></extra>")
        st.plotly_chart(
            titulo_grafico(fig, f"Pareto de utilidad — {seleccion_div}"), use_container_width=True
        )
        st.caption(
            f"**{n80:,} SKUs ({pct80:,.1f}% del catálogo con utilidad positiva) generan el 80%** "
            f"de la utilidad de {seleccion_div}."
        )


# --------------------------------------------------------------------------- #
# Vista OPERACIÓN
# --------------------------------------------------------------------------- #
def vista_operacion():
    st.caption(
        "Tres listas de trabajo: qué comprar, qué no comprar y qué sacar. "
        "La columna MOTIVO dice por qué entró cada producto."
    )

    u1, u2, u3 = st.columns(3)
    with u1:
        dias_reponer = st.slider("Reponer si la cobertura baja de (días)", 7, 120, 30, step=7)
    with u2:
        dias_exceso = st.slider("Exceso si la cobertura supera (días)", 180, 1095, 365, step=30)
    with u3:
        dias_liquidar = st.slider("Liquidar si lleva parado más de (días)", 90, 720, UMBRAL_DIAS, step=30)

    base = df.copy()

    # Cuánto deja el producto al mes cuando sí hay mercadería: rotación × margen.
    # Es la medida de "qué tan buen negocio es", y no depende de si hoy tiene stock.
    # Un generador que vende 0,4/mes con $800 de margen es mucho mejor negocio que
    # un tornillo que vende 5/mes con $0,10.
    base["UTILIDAD_MES"] = (
        base["VENTA_MENSUAL_EN_STOCK"] * base["beneficio_promedio_por_producto"]
    )

    hay_stock = base["STOCK"].fillna(0) > 0
    tiene_cobertura = base["COBERTURA_DIAS"].notna()
    con_historia = base["MESES_CON_STOCK"] >= MESES_HISTORIA_MIN

    # Mal negocio: con historia suficiente para juzgarlo, deja muy poco al mes.
    # Aplica tenga o no tenga stock hoy: es una propiedad del producto.
    mal_negocio = con_historia & (base["UTILIDAD_MES"] < UTILIDAD_MES_MINIMA)

    # Con stock: manda la cobertura
    por_agotarse = base[hay_stock & tiene_cobertura & (base["COBERTURA_DIAS"] < dias_reponer)]
    exceso = base[
        hay_stock & tiene_cobertura & (base["COBERTURA_DIAS"] > dias_exceso) & ~mal_negocio
    ]
    liquidar = base[hay_stock & (base["ANTIGUEDAD_STOCK_DIAS"] > dias_liquidar)].sort_values(
        "VALOR_STOCK", ascending=False
    )

    no_rinde = base[mal_negocio]

    # Agotados que sí valen la pena traer de vuelta
    agotados = base[~hay_stock & (base["MESES_AGOTADO"] > 0)].copy()
    agotados["UTILIDAD_PERDIDA"] = (
        agotados["UNIDADES_PERDIDAS_EST"] * agotados["beneficio_promedio_por_producto"].fillna(0)
    ).clip(lower=0)

    justifica = (
        (agotados["VENTA_MENSUAL_EN_STOCK"] >= ROTACION_MINIMA)
        & (agotados["MESES_AGOTADO"] <= MESES_AGOTADO_MAX)
        & (agotados["MESES_CON_STOCK"] >= MESES_HISTORIA_MIN)
        & (agotados["UTILIDAD_MES"] >= UTILIDAD_MES_MINIMA)
    )
    reponer_agotado = agotados[justifica]

    utilidad_perdida = float(reponer_agotado["UTILIDAD_PERDIDA"].sum())
    sin_juzgar = int((~con_historia).sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Reponer",
        f"{len(por_agotarse) + len(reponer_agotado):,}",
        delta=f"{len(por_agotarse):,} por agotarse · {len(reponer_agotado):,} agotados",
        delta_color="off",
    )
    k2.metric(
        "No comprar",
        f"{len(no_rinde) + len(exceso):,}",
        delta=f"{len(no_rinde):,} no rinden · {len(exceso):,} con exceso",
        delta_color="off",
        help=(
            f"«No rinden» dejan menos de {kpi_dinero(UTILIDAD_MES_MINIMA)}/mes cuando hay "
            "mercadería, tengan stock o no. «Exceso» son productos buenos pero sobrecomprados."
        ),
    )
    k3.metric("Liquidar", f"{len(liquidar):,}", delta=kpi_dinero(liquidar["VALOR_STOCK"].sum()), delta_color="off")
    k4.metric(
        "Utilidad perdida",
        kpi_dinero(utilidad_perdida),
        help=(
            "Estimación de lo dejado de ganar mientras los agotados estuvieron en cero: "
            "rotación en disponibilidad × meses en cero × utilidad unitaria. "
            "Sirve para priorizar, no para presupuestar."
        ),
    )

    st.divider()

    # Una sola tabla por lista, con MOTIVO explicando el criterio. Las columnas que
    # no aplican a un producto quedan vacías: la cobertura no existe si el stock es
    # cero, y los meses agotado no existen si todavía hay mercadería.
    COLUMNAS = {
        "CODIGO": "CODIGO",
        "PRODUCTO": "PRODUCTO",
        "MARCA": "MARCA",
        "MOTIVO": "MOTIVO",
        "STOCK": "STOCK",
        "VENTA_MENSUAL_EN_STOCK": "VENTA/MES",
        "UTILIDAD_MES": "UTILIDAD/MES [$]",
        "MESES_CON_STOCK": "MESES HISTORIA",
        "COBERTURA_DIAS": "COBERTURA [DIAS]",
        "ANTIGUEDAD_STOCK_DIAS": "PARADO [DIAS]",
        "MESES_AGOTADO": "MESES AGOTADO",
        "VALOR_STOCK": "CAPITAL [$]",
        "beneficio_promedio_por_producto": "UTILIDAD UNIT [$]",
        "CALIDAD_DATOS": "CALIDAD DATOS",
    }
    FORMATO = {
        "STOCK": "entero",
        "MESES HISTORIA": "entero",
        "COBERTURA [DIAS]": "entero",
        "PARADO [DIAS]": "entero",
        "MESES AGOTADO": "entero",
        "UTILIDAD/MES [$]": "moneda",
        "CAPITAL [$]": "moneda",
        "UTILIDAD UNIT [$]": "moneda",
    }

    def preparar(*bloques) -> pd.DataFrame:
        """Une varios grupos en una tabla, cada uno con su MOTIVO."""
        partes = []
        for datos, motivo in bloques:
            if datos.empty:
                continue
            p = datos.copy()
            p["MOTIVO"] = motivo
            # Se vacía fila por fila lo que no aplica, para no mostrar un cero que
            # en realidad significa "no existe": un producto sin stock no tiene
            # cobertura, y uno con stock no lleva meses agotado.
            con = p["STOCK"].fillna(0) > 0
            p.loc[con, "MESES_AGOTADO"] = np.nan
            p.loc[~con, "COBERTURA_DIAS"] = np.nan
            partes.append(p)

        if not partes:
            return pd.DataFrame(columns=list(COLUMNAS.values()))

        unido = pd.concat(partes, ignore_index=True)
        cols = [c for c in COLUMNAS if c in unido.columns]
        salida = unido[cols].rename(columns=COLUMNAS)
        for col in ("VENTA/MES", "UTILIDAD/MES [$]"):
            if col in salida.columns:
                salida[col] = salida[col].round(2)
        return salida

    t1, t2, t3 = st.tabs(
        [
            f"🔴 Reponer ({len(por_agotarse) + len(reponer_agotado):,})",
            f"🟡 No comprar ({len(no_rinde) + len(exceso):,})",
            f"🟠 Liquidar ({len(liquidar):,})",
        ]
    )

    with t1:
        st.markdown(
            f"**Por agotarse**: todavía hay stock pero queda para menos de {dias_reponer} días "
            "al ritmo reciente. · **Agotado**: está en cero y vendía bien cuando había "
            "mercadería."
        )
        v = preparar(
            (por_agotarse.sort_values("COBERTURA_DIAS"), "Por agotarse"),
            (reponer_agotado.sort_values("UTILIDAD_PERDIDA", ascending=False), "Agotado"),
        )
        st.dataframe(v.head(50), use_container_width=True, hide_index=True)
        boton_excel(v, "Descargar lista de reposición", "reponer.xlsx", "Reponer", FORMATO)

    with t2:
        st.markdown(
            f"**No rinde**: deja menos de {kpi_dinero(UTILIDAD_MES_MINIMA)} al mes cuando hay "
            "mercadería. Es una propiedad del producto, así que aparece tenga stock o no — "
            "sirve para revisar línea por línea un pedido al proveedor. · "
            f"**Exceso**: el producto es bueno, pero ya tienes para más de {dias_exceso} días."
        )
        v = preparar(
            (no_rinde.sort_values("UTILIDAD_MES"), "No rinde"),
            (exceso.sort_values("VALOR_STOCK", ascending=False), "Exceso"),
        )
        st.dataframe(v.head(50), use_container_width=True, hide_index=True)
        boton_excel(v, "Descargar lista de no comprar", "no_comprar.xlsx", "NoComprar", FORMATO)
        if sin_juzgar:
            st.caption(
                f"Quedan **{sin_juzgar:,} productos fuera de esta lista** porque tuvieron stock "
                f"menos de {MESES_HISTORIA_MIN} meses: no hay con qué juzgarlos. No están "
                "aprobados, están sin evaluar."
            )

    with t3:
        st.markdown(
            f"Llevan **más de {dias_liquidar} días** en bodega sin salir. "
            "Candidatos a promoción, descuento o devolución al proveedor."
        )
        v = preparar((liquidar, "Parado"))
        st.dataframe(v.head(50), use_container_width=True, hide_index=True)
        boton_excel(v, "Descargar lista de liquidación", "liquidar.xlsx", "Liquidar", FORMATO)

    st.caption(
        "Las tablas muestran las primeras 50 filas; el Excel trae la lista completa. "
        f"**UTILIDAD/MES** es lo que deja el producto al mes cuando hay mercadería "
        f"(rotación × margen unitario). Un agotado entra a reponer si vendía al menos "
        f"{ROTACION_MINIMA:g} unidades/mes, deja más de {kpi_dinero(UTILIDAD_MES_MINIMA)}/mes, "
        f"lleva menos de {MESES_AGOTADO_MAX} meses en cero y tiene al menos "
        f"{MESES_HISTORIA_MIN} meses de historia."
    )

    st.divider()
    st.subheader("MAPA DE DECISIÓN")

    mapa = df[(df["STOCK"] > 0) & df["COBERTURA_DIAS"].notna() & df["ANTIGUEDAD_STOCK_DIAS"].notna()].copy()
    if mapa.empty:
        st.info("No hay productos con cobertura y antigüedad calculadas para estos filtros.")
    else:
        mapa["COBERTURA_VIS"] = mapa["COBERTURA_DIAS"].clip(upper=1095)
        fig = px.scatter(
            mapa,
            x="ANTIGUEDAD_STOCK_DIAS",
            y="COBERTURA_VIS",
            size="VALOR_STOCK",
            color="ROTACION",
            hover_name="PRODUCTO",
            category_orders={"ROTACION": ORDEN_ROTACION},
            size_max=40,
            hover_data={
                "COBERTURA_VIS": False,
                "ANTIGUEDAD_STOCK_DIAS": ":.0f",
                "VALOR_STOCK": ":$,.0f",
                "STOCK": ":.0f",
            },
        )
        fig.add_vline(x=dias_liquidar, line_dash="dash", line_color=OSCURO)
        fig.add_hline(y=dias_exceso, line_dash="dash", line_color=OSCURO)
        fig.update_xaxes(title_text="Días parado (antigüedad del stock)")
        fig.update_yaxes(title_text="Cobertura en días (recortado a 1095)")
        st.plotly_chart(
            titulo_grafico(fig, f"Antigüedad vs cobertura — {seleccion_div}"), use_container_width=True
        )
        st.caption(
            "El tamaño del punto es el capital inmovilizado. "
            "Arriba a la derecha está lo peor: viejo y con stock para años."
        )


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
if vista == "Gerencia":
    vista_gerencia()
else:
    vista_operacion()


# --------------------------------------------------------------------------- #
# Calidad de datos y pie de página
# --------------------------------------------------------------------------- #
st.divider()
with st.expander("⚠️ Calidad de los datos en esta selección"):
    total = len(df)
    ajustados = int((df["CALIDAD_DATOS"] != "OK").sum())
    st.markdown(
        f"De **{total:,} productos**, **{ajustados:,}** tienen el libro de movimientos "
        "corregido para poder calcular su antigüedad."
    )
    resumen = (
        df["CALIDAD_DATOS"].value_counts().rename_axis("Situación").reset_index(name="Productos")
    )
    st.dataframe(resumen, use_container_width=True, hide_index=True)

    banderas = {
        "NEGATIVO_RESIDUAL": "El libro sigue sin cuadrar: sus días no son confiables",
        "SIN_COMPRAS": "Nunca registró una compra",
        "VENTA_ANTICIPADA": "Se facturó la venta antes de ingresar la compra",
    }
    filas = [
        {"Bandera": texto, "Productos": int(df[col].sum())}
        for col, texto in banderas.items()
        if col in df.columns
    ]
    if filas:
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    st.caption(
        "La antigüedad se mide por capas FIFO sobre el libro reconstruido: cada compra "
        "agrega unidades con su fecha y cada venta consume las más antiguas. Los productos "
        "sin stock no tienen antigüedad."
    )


# El pipeline agrega su propia fecha al correr; si todavía no lo hizo, se omite
# en vez de mostrar un "N/D" que parece un error.
_pie = [f"© {datetime.now().year} Importamaq S.A."]
if fecha_datos != "N/D":
    _pie.append(f"Datos al <strong>{fecha_datos}</strong>")
if fecha_corrida != "N/D":
    _pie.append(f"Pipeline ejecutado el {fecha_corrida}")

st.markdown(
    f"""
    <hr style="margin-top: 40px; margin-bottom: 10px;">
    <div style="text-align:center; font-size:14px; color:#6b7280;">
        {" | ".join(_pie)}<br>
        Elaborado por: <strong>Geovanny Benavides S.</strong>
    </div>
    """,
    unsafe_allow_html=True,
)
