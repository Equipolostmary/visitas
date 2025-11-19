import streamlit as st
import pandas as pd
import requests
import pydeck as pdk

st.set_page_config(page_title="Gestor de Visitas", layout="wide")

# --- CONFIG ---
API_URL = "https://script.google.com/macros/s/AKfycbwwwflRG42o1J_EfwUn992UxqxvO4akkYp_j-8VretD4wEtEzFD0oJgS_DuSi-sNlGR-A/exec"   #


# --------------------------------------------------------
# --- FUNCIONES PARA TRAER DATOS DESDE APPS SCRIPT --------
# --------------------------------------------------------

@st.cache_data(ttl=60)
def get_ranking():
    url = f"{API_URL}?type=ranking"
    r = requests.get(url)
    return r.json().get("ranking", [])


@st.cache_data(ttl=60)
def get_visits():
    url = f"{API_URL}?type=visits"
    r = requests.get(url)
    return r.json().get("visits", {})


# --------------------------------------------------------
# --- UI PRINCIPAL ---------------------------------------
# --------------------------------------------------------

st.title("📋 Buscador de Visitas + 🗺️ Mapa + 🏆 Ranking")

option = st.sidebar.radio(
    "Selecciona una sección",
    ["🔍 Buscador de visitas", "🗺️ Mapa de visitas", "🏆 Ranking"]
)

visitas = get_visits()
ranking = get_ranking()


# --------------------------------------------------------
# --- 1. BUSCADOR DE VISITAS ------------------------------
# --------------------------------------------------------
if option == "🔍 Buscador de visitas":
    st.header("🔍 Buscar visitas por número de teléfono")

    telefono = st.text_input("Introduce número de teléfono:")

    if telefono:
        resultados = []
        for zona, filas in visitas.items():
            for row in filas:
                if str(row.get("Telefono", "")).strip() == telefono.strip():
                    row["zona"] = zona
                    resultados.append(row)

        if resultados:
            st.success(f"Se encontraron {len(resultados)} visitas")

            df = pd.DataFrame(resultados)
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No se encontró ninguna visita con ese teléfono.")



# --------------------------------------------------------
# --- 2. MAPA DE VISITAS ----------------------------------
# --------------------------------------------------------
if option == "🗺️ Mapa de visitas":
    st.header("🗺️ Mapa de puntos visitados")

    # Convertir todas las zonas en un DataFrame conjunto
    all_visits = []
    for zona, rows in visitas.items():
        for r in rows:
            r["zona"] = zona
            all_visits.append(r)

    if len(all_visits) == 0:
        st.warning("No hay datos de visitas en las hojas.")
    else:
        df = pd.DataFrame(all_visits)

        # Aseguramos nombres de columnas correctos
        if "Latitud" not in df.columns or "Longitud" not in df.columns:
            st.error("No hay columnas 'Latitud' y 'Longitud' en tu Google Sheet.")
        else:
            df = df.dropna(subset=["Latitud", "Longitud"])

            # Mapa con pydeck
            st.pydeck_chart(
                pdk.Deck(
                    map_style="mapbox://styles/mapbox/streets-v11",
                    initial_view_state=pdk.ViewState(
                        latitude=df["Latitud"].mean(),
                        longitude=df["Longitud"].mean(),
                        zoom=8,
                        pitch=0,
                    ),
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=df,
                            get_position="[Longitud, Latitud]",
                            get_radius=80,
                            pickable=True,
                        )
                    ],
                    tooltip={"text": "{Nombre}\nZona: {zona}"}
                )
            )


# --------------------------------------------------------
# --- 3. RANKING ------------------------------------------
# --------------------------------------------------------
if option == "🏆 Ranking":
    st.header("🏆 Ranking de puntos")

    if len(ranking) == 0:
        st.warning("No hay datos en la hoja 'Resultados'.")
    else:
        df = pd.DataFrame(ranking)
        st.dataframe(df, use_container_width=True)
