import streamlit as st
import pandas as pd

st.set_page_config(page_title="📍 Buscador de Visitas - Lost Mary", layout="wide")

st.title("📋 Buscador de Visitas a Puntos de Venta")
st.markdown("Consulta la última visita registrada en los puntos de venta de **Valencia**, **Asturias** y **Málaga**.")

# ---- FUNCIONES ----
@st.cache_data
def cargar_datos():
    try:
        base_url = "https://docs.google.com/spreadsheets/d/1RzAMfJvg7OQmVITHw0rAeHPAnn34qocMzVa6qvARMAQ/export?format=csv&gid="
        hojas = {
            "VALENCIA": "1477439551",
            "ASTURIAS": "1676548503",
            "MALAGA": "1932656719"
        }

        dfs = []
        for nombre, gid in hojas.items():
            url = f"{base_url}{gid}"
            df = pd.read_csv(url)
            df["Provincia_origen"] = nombre
            dfs.append(df)

        df_total = pd.concat(dfs, ignore_index=True)
        df_total["Marca temporal"] = pd.to_datetime(df_total["Marca temporal"], errors="coerce")
        return df_total

    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        return pd.DataFrame()

# ---- CARGA ----
df_total = cargar_datos()
if df_total.empty:
    st.stop()

# ---- BUSCADOR ----
st.subheader("🔍 Buscar punto de venta por dirección")
busqueda = st.text_input("Introduce parte de la dirección (columna C):")

if busqueda:
    coincidencias = df_total[df_total["Dirección"].str.contains(busqueda, case=False, na=False)]
    if not coincidencias.empty:
        opciones = coincidencias["Dirección"].dropna().unique().tolist()
        seleccion = st.selectbox("Selecciona la dirección exacta:", opciones, key="direccion_select")

        if seleccion:
            df_filtrado = coincidencias[coincidencias["Dirección"] == seleccion].copy()
            ultima_visita = df_filtrado.sort_values("Marca temporal", ascending=False).head(1).T
            ultima_visita.columns = ["Última visita"]

            st.success(f"Mostrando información de la última visita para: **{seleccion}**")
            st.dataframe(ultima_visita, use_container_width=True)

            # Mostrar historial completo opcional
            with st.expander("📅 Ver historial completo de visitas"):
                historial = df_filtrado.sort_values("Marca temporal", ascending=False)
                st.dataframe(historial, use_container_width=True)
    else:
        st.warning("No se han encontrado coincidencias con esa dirección.")
else:
    st.info("Escribe parte de una dirección para comenzar la búsqueda.")

st.markdown("---")
st.caption("Desarrollado por Antonio Meca · Lost Mary · © 2025")
