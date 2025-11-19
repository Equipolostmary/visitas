# streamlit_app.py
import streamlit as st
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import json
from io import BytesIO
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="Gestor Visitas - Lost Mary", layout="wide")

# ---------- CONFIG ----------
SHEET_ID = "1RzAMfJvg7OQmVITHw0rAeHPAnn34qocMzVa6qvARMAQ"
FORM_LINKS = {
    "VALENCIA": "https://forms.gle/oQnuA8CiEEhjKKZo6",
    "ASTURIAS": "https://forms.gle/j6Ngo7SZkWS6B5kL7",
    "MALAGA": "https://forms.gle/HcQxd55xQFJ8aiGX9"
}

# ---------- AUTH ----------
def get_gspread_client():
    """
    Autenticación correcta para Streamlit Cloud
    usando st.secrets["google_credentials"]
    """
    scope = ["https://www.googleapis.com/auth/spreadsheets",
             "https://www.googleapis.com/auth/drive"]

    if "google_credentials" not in st.secrets:
        st.error("❌ Falta st.secrets['google_credentials']")
        st.stop()

    creds_info = st.secrets["google_credentials"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scopes=scope)
    return gspread.authorize(creds)

gc = get_gspread_client()
sh = gc.open_by_key(SHEET_ID)

# ---------- HELPERS ----------
def read_zone_sheet(zone_name):
    try:
        worksheet = sh.worksheet(zone_name)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        df["__zona"] = zone_name
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_all_zones():
    zones = ["VALENCIA", "ASTURIAS", "MALAGA"]
    dfs = [read_zone_sheet(z) for z in zones]
    dfs = [d for d in dfs if not d.empty]
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)

def find_address_column(df):
    candidates = [c for c in df.columns if any(k in c.lower() for k in ("direc","addr","direccion","address","domicilio"))]
    return candidates[0] if candidates else None

def find_date_column(df):
    candidates = [c for c in df.columns if any(k in c.lower() for k in ("fecha","date","dia","hora"))]
    return candidates[0] if candidates else None

def append_visit_to_zone(zone, record):
    worksheet = sh.worksheet(zone)
    headers = worksheet.row_values(1)
    row = [record.get(h, "") for h in headers]
    worksheet.append_row(row, value_input_option="USER_ENTERED")

# ---------- UI ----------
st.title("Herramienta de visitas — Gestores de puntos de venta")
st.markdown("Busca puntos de venta por **dirección** y revisa su última visita.")

full = load_all_zones()
if full.empty:
    st.warning("No hay datos disponibles. Revisa permisos del Sheet.")
    st.stop()

addr_col = find_address_column(full)
date_col = find_date_column(full)

# Sidebar
with st.sidebar:
    st.header("Búsqueda")
    query = st.text_input("Buscar por dirección")
    zona_filter = st.selectbox("Zona", ["(todas)", "VALENCIA", "ASTURIAS", "MALAGA"])
    st.markdown("---")
    st.write("Formularios oficiales")
    for z in FORM_LINKS:
        st.markdown(f"[{z}]({FORM_LINKS[z]})")

# Filtering
df = full.copy()
if zona_filter != "(todas)":
    df = df[df["__zona"] == zona_filter]

if query:
    if addr_col:
        mask = df[addr_col].astype(str).str.contains(query, case=False, na=False)
    else:
        mask = pd.Series(False, index=df.index)
        for c in df.columns:
            mask |= df[c].astype(str).str.contains(query, case=False, na=False)
    results = df[mask]
else:
    results = pd.DataFrame()

st.subheader("Coincidencias encontradas")
st.write("Total:", len(results))

if not results.empty:
    st.dataframe(results.reset_index(drop=True))

    sel = st.number_input("Selecciona índice", 0, len(results)-1, 0)
    row = results.reset_index(drop=True).iloc[sel]

    st.markdown("### Detalle seleccionado")
    st.write(row.to_dict())

    selected_address = row.get(addr_col, "")
    zone = row["__zona"]

    zone_df = full[full["__zona"] == zone]
    same = zone_df[zone_df[addr_col].astype(str).str.lower() ==
                   str(selected_address).lower()]

    st.markdown("### Última visita")
    if not same.empty:
        if date_col:
            same[date_col] = pd.to_datetime(same[date_col], errors="coerce")
            last = same.sort_values(by=date_col, ascending=False).iloc[0]
        else:
            last = same.iloc[-1]
        st.write(last.to_dict())
    else:
        st.info("No hay visitas previas registradas.")

    st.markdown("---")
    st.write("Acciones:")
    col1, col2 = st.columns(2)

    with col1:
        zona_sel = st.selectbox("Abrir formulario", list(FORM_LINKS.keys()))
        st.markdown(f"[Abrir formulario {zona_sel}]({FORM_LINKS[zona_sel]})")

    with col2:
        if st.button("Ir a crear visita desde la app"):
            st.success("Baja a la sección inferior para crear la visita.")

else:
    st.info("Introduce una dirección para buscar.")

# ---------- Create Visit ----------
st.markdown("---")
st.header("Crear visita desde la app")

with st.form("create_visit"):
    z = st.selectbox("Zona", ["VALENCIA", "ASTURIAS", "MALAGA"])
    ws = sh.worksheet(z)
    headers = ws.row_values(1)

    entry = {}
    for h in headers:
        if "direc" in h.lower():
            entry[h] = st.text_input("Dirección")
        elif "fecha" in h.lower():
            entry[h] = st.date_input("Fecha", value=datetime.today()).strftime("%Y-%m-%d")
        elif any(k in h.lower() for k in ("nota", "observ", "coment")):
            entry[h] = st.text_area("Notas")
        else:
            entry[h] = st.text_input(h)

    if st.form_submit_button("Guardar visita"):
        try:
            append_visit_to_zone(z, entry)
            st.success("Visita guardada correctamente.")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"Error: {e}")

st.caption("Desarrollado para Lost Mary — Antonio")
