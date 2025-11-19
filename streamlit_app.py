import streamlit as st
import pandas as pd
import requests
import pydeck as pdk

# --------------------------------------------------------
# CONFIG
# --------------------------------------------------------
st.set_page_config(page_title="Gestor de Visitas", layout="wide")

# Cargamos la URL desde los Secrets de Streamlit
API_URL = st.secrets["API_URL"]


# --------------------------------------------------------
# FUNCIONES PARA TRAER DATOS DESDE APPS SCRIPT
# --------------------------------------------------------

@st.cache_data(ttl=60)
def get_ranking():
    """Obtiene el ranking desde Google Apps Script."""
    try:
        url = f"{API_URL}?type=ranking"
        r = requests.get(url)
        r.raise_for_status()
        return r.json().get("ranking", [])
    except Exception as e:
        st.error(f"Error al cargar ranking: {e}")
        return []


@st.cache_data(ttl=60)
def get_visits():
    """Obtiene todas las visitas por zona."""
    try:
        url = f"{API_URL}?type=visits"
        r = requests.get(url)
        r.raise_for_status()
        return r.json().get("visits", {})
    except Exception as e:
        st.error(f"Error al cargar visitas: {e}")
        return {}


# --------------------------------------------------------
# UI PRINCIPAL
# --------------------------------------------------------

st.title("📋 Buscador de Visitas • 🗺️ Mapa • 🏆 Ranking")

opcion = st.sidebar.radio(
    "Selecciona una sección",
    ["🔍 Buscador de visitas", "🗺️ Mapa de visitas", "🏆 Ranking"]
)

visitas = get_visits()
ranking = get_ranking()


# --------------------------------------------------------
# 1. BUSCADOR DE VISITAS
# --------------------------------------------------------
if opcion == "🔍 Buscador de visitas":
    st.header("🔍 Buscar visitas por teléfono")

    telefono = st.text_input("Introduce el número de teléfono:")

    if telefono:
        resultados = []

        # Buscar en todas las zonas
        for zona, filas in visitas.items():
            for row in filas:
                if str(row.get("Telefono", "")).strip() == telefono.strip():
                    row["zona"] = zona
                    resultados.append(row)

        if resultados:
            st.success(f"Se encontraron {len(resultados)} visitas")
            st.dataframe(pd.DataFrame(resultados), use_container_width=True)
        else:
            st.warning("No se encontró ninguna visita con ese teléfono.")


# --------------------------------------------------------
# 2. MAPA DE VISITAS
# --------------------------------------------------------
if opcion == "🗺️ Mapa de visitas":
    st.header("🗺️ Mapa de puntos visitados")

    all_visits = []
    for zona, rows in visitas.items():
        for r in rows:
            r["zona"] = zona
            all_visits.append(r)

    if not all_visits:
        st.warning("No hay datos de visitas disponibles.")
    else:
        df = pd.DataFrame(all_visits)

        if "Latitud" not in df.columns or "Longitud" not in df.columns:
            st.error("❌ Tu hoja no tiene columnas 'Latitud' y 'Longitud'.")
        else:
            df = df.dropna(subset=["Latitud", "Longitud"])

            st.pydeck_chart(
                pdk.Deck(
                    map_style="mapbox://styles/mapbox/streets-v11",
                    initial_view_state=pdk.ViewState(
                        latitude=df["Latitud"].mean(),
                        longitude=df["Longitud"].mean(),
                        zoom=7,
                        pitch=0,
                    ),
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=df,
                            get_position="[Longitud, Latitud]",
                            get_radius=80,
                            pickable=True,
                            auto_highlight=True,
                        )
                    ],
                    tooltip={"text": "{Nombre}\nZona: {zona}"}
                )
            )


# --------------------------------------------------------
# 3. RANKING
# --------------------------------------------------------
if opcion == "🏆 Ranking":
    st.header("🏆 Ranking de puntos")

    if not ranking:
        st.warning("No hay datos en la hoja 'Resultados'.")
    else:
        st.dataframe(pd.DataFrame(ranking), use_container_width=True)
