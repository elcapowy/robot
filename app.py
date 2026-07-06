"""
app.py
======
Módulo 5 — Dashboard Streamlit.

Visualiza reporte_marcas_mensual.xlsx (generado por el Módulo 3):
  - KPIs de actividad de marcas rivales
  - Alertas de fuga de clientes
  - Alertas de presión de precio
  - Nuevas empresas POR_VALIDAR

Pensado para desplegarse en Streamlit Cloud, leyendo el reporte desde el
repositorio privado donde GitHub Actions lo commitea cada mes.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Radar de Marcas Competidoras",
    page_icon="📡",
    layout="wide",
)

REPORTE_PATH = Path("reporte_marcas_mensual.xlsx")

AZUL_MARINO = "#1F3864"


@st.cache_data(ttl=3600)
def cargar_hoja(nombre_hoja: str) -> pd.DataFrame:
    if not REPORTE_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_excel(REPORTE_PATH, sheet_name=nombre_hoja)
    except ValueError:
        return pd.DataFrame()


def main() -> None:
    st.markdown(
        f"<h1 style='color:{AZUL_MARINO};'>📡 Radar de Marcas Competidoras</h1>",
        unsafe_allow_html=True,
    )

    if not REPORTE_PATH.exists():
        st.warning(
            "Todavía no existe 'reporte_marcas_mensual.xlsx'. "
            "Se genera automáticamente el día 1 de cada mes vía GitHub Actions."
        )
        st.stop()

    fuga_df = cargar_hoja("Alertas Fuga Clientes")
    precio_df = cargar_hoja("Alertas Precio Bajo")
    nuevos_df = cargar_hoja("Nuevos Hallazgos")
    detalle_df = cargar_hoja("Detalle Completo")

    modificado = REPORTE_PATH.stat().st_mtime
    st.caption(f"Última actualización del reporte: {pd.to_datetime(modificado, unit='s'):%d/%m/%Y %H:%M}")

    # ------------------------------------------------------------------
    # Selector de marca propia (COEL / SANHUA / VHM / Todas)
    # Cada marca rival apunta a una de nuestras marcas propias vía la
    # columna "Marca_Propia_Afectada" que agrega analyzer.py. Este filtro
    # recorta las 4 hojas para ver el radar de una sola línea de negocio.
    # ------------------------------------------------------------------
    col_marca_propia = "Marca_Propia_Afectada"
    marcas_propias_disponibles = sorted(
        {
            v for df in (fuga_df, precio_df, detalle_df)
            for v in (df[col_marca_propia].dropna().unique() if col_marca_propia in df.columns else [])
        }
    )
    opciones_filtro = ["Todas"] + marcas_propias_disponibles
    marca_propia_sel = st.radio(
        "Marca propia", opciones_filtro, horizontal=True,
    )

    def _filtrar(df: pd.DataFrame) -> pd.DataFrame:
        if marca_propia_sel == "Todas" or col_marca_propia not in df.columns:
            return df
        return df[df[col_marca_propia] == marca_propia_sel]

    fuga_df = _filtrar(fuga_df)
    precio_df = _filtrar(precio_df)
    detalle_df = _filtrar(detalle_df)

    # ------------------------------------------------------------------
    # KPIs
    # ------------------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🚨 Alertas de Fuga", len(fuga_df))
    col2.metric("📉 Presión de Precio", len(precio_df))
    col3.metric("🕵️ Nuevos Hallazgos", len(nuevos_df))
    col4.metric("📄 Operaciones Analizadas", len(detalle_df))

    st.divider()

    # ------------------------------------------------------------------
    # Actividad por marca rival
    # ------------------------------------------------------------------
    st.subheader("Actividad de Marcas Rivales")
    if not detalle_df.empty and "Marca" in detalle_df.columns:
        actividad = detalle_df["Marca"].value_counts().rename_axis("Marca").reset_index(name="Operaciones")
        c1, c2 = st.columns([2, 1])
        with c1:
            st.bar_chart(actividad.set_index("Marca"))
        with c2:
            st.dataframe(actividad, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos de detalle para graficar actividad por marca.")

    st.divider()

    # ------------------------------------------------------------------
    # Alertas de fuga de clientes
    # ------------------------------------------------------------------
    st.subheader("🚨 Alertas de Fuga de Clientes")
    if fuga_df.empty:
        st.success("Sin clientes propios comprando marcas rivales este mes.")
    else:
        st.dataframe(fuga_df, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # Alertas de presión de precio
    # ------------------------------------------------------------------
    st.subheader("📉 Alertas de Presión de Precio")
    if precio_df.empty:
        st.success("Sin operaciones de competencia por debajo del precio techo.")
    else:
        st.dataframe(precio_df, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # Nuevos hallazgos (POR_VALIDAR)
    # ------------------------------------------------------------------
    st.subheader("🕵️ Nuevas Empresas — POR_VALIDAR")
    if nuevos_df.empty:
        st.info("No se detectaron importadores nuevos este mes.")
    else:
        st.dataframe(nuevos_df, use_container_width=True, hide_index=True)
        st.caption("Estas empresas ya fueron dadas de alta en Notion con Estado = POR_VALIDAR.")

    st.divider()

    # ------------------------------------------------------------------
    # Detalle completo + descarga
    # ------------------------------------------------------------------
    with st.expander("📋 Ver detalle completo de operaciones"):
        st.dataframe(detalle_df, use_container_width=True, hide_index=True)

    st.download_button(
        "⬇️ Descargar reporte completo (.xlsx)",
        data=REPORTE_PATH.read_bytes(),
        file_name="reporte_marcas_mensual.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    main()
