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
# IDs/links you provided
SHEET_ID = "1RzAMfJvg7OQmVITHw0rAeHPAnn34qocMzVa6qvARMAQ"
FORM_LINKS = {
    "VALENCIA": "https://forms.gle/oQnuA8CiEEhjKKZo6",
    "ASTURIAS": "https://forms.gle/j6Ngo7SZkWS6B5kL7",
    "MALAGA": "https://forms.gle/HcQxd55xQFJ8aiGX9"
}
# default local path for dev
LOCAL_SERVICE_ACCOUNT = Path("service_account.json")

# ---------- AUTH ----------
def get_gspread_client():
    """
    Tries three methods:
    - Streamlit secrets: 'gcp_service_account' with JSON content
    - local file service_account.json
    - env fallback not implemented (could add)
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # 1) Streamlit secrets mode
    if "gcp_service_account" in st.secrets:
        sa_info = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(sa_info, scopes=scope)
        return gspread.authorize(creds)
    # 2) local file (for dev)
    if LOCAL_SERVICE_ACCOUNT.exists():
        creds = ServiceAccountCredentials.from_json_keyfile_name(str(LOCAL_SERVICE_ACCOUNT), scopes=scope)
        return gspread.authorize(creds)
    st.error("No se encontró credencial. Coloca service_account.json en la raíz o configura st.secrets['gcp_service_account'].")
    st.stop()

gc = get_gspread_client()
sh = gc.open_by_key(SHEET_ID)

# ---------- HELPERS ----------
def read_zone_sheet(zone_name):
    try:
        worksheet = sh.worksheet(zone_name)
    except Exception as e:
        st.warning(f"No se encontró la hoja '{zone_name}'. Error: {e}")
        return pd.DataFrame()
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    df["__zona"] = zone_name
    return df

@st.cache_data(ttl=60)
def load_all_zones():
    zones = ["VALENCIA", "ASTURIAS", "MALAGA"]
    dfs = []
    for z in zones:
        df = read_zone_sheet(z)
        if not df.empty:
            dfs.append(df)
    if dfs:
        full = pd.concat(dfs, ignore_index=True, sort=False)
    else:
        full = pd.DataFrame()
    return full

def find_address_column(df):
    # heuristics: find column name that looks like address
    candidates = [c for c in df.columns if any(k in c.lower() for k in ("direc", "addr", "direccion", "address", "domicilio"))]
    return candidates[0] if candidates else None

def find_date_column(df):
    candidates = [c for c in df.columns if any(k in c.lower() for k in ("fecha", "date", "dia", "hora"))]
    return candidates[0] if candidates else None

def append_visit_to_zone(zone, record: dict):
    worksheet = sh.worksheet(zone)
    # convert keys to sheet columns order by reading header row
    header_row = worksheet.row_values(1)
    # create row aligned to header (missing keys -> "")
    row = [ record.get(h, "") for h in header_row ]
    worksheet.append_row(row, value_input_option="USER_ENTERED")

# ---------- UI ----------
st.title("Herramienta de visitas — Gestores de puntos de venta")
st.markdown("Busca puntos de venta por **dirección** y revisa la última visita. Puedes abrir el formulario de tu zona o crear la visita desde la app.")

full = load_all_zones()
if full.empty:
    st.info("No hay datos cargados en las hojas. Asegúrate de compartir el sheet con el service account y que las hojas se llamen VALENCIA / ASTURIAS / MALAGA.")
    st.stop()

# detect address column
addr_col = find_address_column(full)
date_col = find_date_column(full)

with st.sidebar:
    st.header("Búsqueda")
    query = st.text_input("Buscar por dirección (parte del texto)")
    zona_filter = st.selectbox("Filtrar por zona", ["(todas)", "VALENCIA", "ASTURIAS", "MALAGA"])
    st.markdown("---")
    st.write("Formularios oficiales:")
    st.markdown(f"[Abrir formulario Valencia]({FORM_LINKS['VALENCIA']})")
    st.markdown(f"[Abrir formulario Asturias]({FORM_LINKS['ASTURIAS']})")
    st.markdown(f"[Abrir formulario Málaga]({FORM_LINKS['MALAGA']})")
    st.markdown("---")
    st.write("Consejo: si quieres que la app rellene la visita, usa la sección 'Crear visita desde la app' abajo.")

# filter dataset
df = full.copy()
if zona_filter != "(todas)":
    df = df[df["__zona"] == zona_filter]

if query:
    if addr_col:
        mask = df[addr_col].astype(str).str.contains(query, case=False, na=False)
        results = df[mask]
    else:
        # fallback: search every column
        mask = pd.Series(False, index=df.index)
        for c in df.columns:
            try:
                mask = mask | df[c].astype(str).str.contains(query, case=False, na=False)
            except Exception:
                pass
        results = df[mask]
else:
    results = pd.DataFrame()  # require query to show matches

st.subheader("Coincidencias encontradas")
st.write("Filas encontradas:", len(results))
if not results.empty:
    # show table with index to pick
    st.dataframe(results.reset_index(drop=True))
    sel = st.number_input("Selecciona índice de la coincidencia (0 = primera)", min_value=0, max_value=max(0, len(results)-1), value=0, step=1)
    selected_row = results.reset_index(drop=True).loc[sel]
    st.markdown("### Detalle seleccionado")
    st.write(selected_row.to_dict())

    # show latest visit for that address (search by exact address within that zone)
    selected_address = None
    if addr_col:
        selected_address = selected_row.get(addr_col, "")
    if selected_address:
        zone = selected_row["__zona"]
        zone_df = full[full["__zona"] == zone]
        # find all rows for that address
        same = zone_df[zone_df[addr_col].astype(str).str.strip().str.lower() == str(selected_address).strip().lower()]
        if same.empty:
            st.info("No hay visitas previas exactas para esta dirección en la misma zona.")
        else:
            # try to sort by date if possible
            if date_col:
                try:
                    same[date_col] = pd.to_datetime(same[date_col], errors='coerce')
                    last = same.sort_values(by=date_col, ascending=False).iloc[0]
                except Exception:
                    last = same.iloc[-1]
            else:
                last = same.iloc[-1]
            st.markdown("#### Última visita registrada")
            st.write(last.to_dict())
    else:
        st.info("No se detectó columna de dirección; revisa nombres de columnas en tu sheet (p.ej. 'Dirección', 'direccion', 'address').")

    st.markdown("---")
    st.write("Acciones para este punto de venta:")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Abrir formulario oficial**")
        open_form = st.selectbox("Formulario zona", ["Valencia", "Asturias", "Málaga"])
        if st.button("Abrir formulario en nueva pestaña"):
            url = FORM_LINKS[open_form.upper()]
            js = f"window.open('{url}')"  # Streamlit can open if using markdown link instead; we'll provide link
            st.markdown(f"[Abrir formulario {open_form}]({url})")
    with col2:
        st.markdown("**Crear visita desde la app**")
        if st.button("Rellenar visita en la app (guardar en Sheet)"):
            st.info("Desplázate abajo a 'Crear visita desde la app' para completar y enviar el registro directamente desde aquí.")

else:
    st.info("Escribe una parte de la dirección y pulsa Enter para buscar coincidencias.")

st.markdown("---")
st.header("Crear visita desde la app")
st.markdown("Si prefieres no usar Google Forms, puedes completar la visita aquí y la app guardará una nueva fila en la hoja de la zona seleccionada.")

with st.form("create_visit"):
    z = st.selectbox("Zona (dónde registrar la visita)", ["VALENCIA", "ASTURIAS", "MALAGA"])
    # Build a flexible form: use columns detected in the sheet header for that zone
    ws = sh.worksheet(z)
    headers = ws.row_values(1)
    # show default fields first (address, fecha, notas) if exist
    addr_field = next((h for h in headers if any(k in h.lower() for k in ("direc","direccion","address","domicilio"))), None)
    date_field = next((h for h in headers if any(k in h.lower() for k in ("fecha","date"))), None)
    note_field = next((h for h in headers if any(k in h.lower() for k in ("nota","observ","coment","apunt"))), None)

    entry = {}
    for h in headers:
        if h == addr_field:
            entry[h] = st.text_input("Dirección", value="")
        elif h == date_field:
            entry[h] = st.date_input("Fecha", value=datetime.today()).strftime("%Y-%m-%d")
        elif h == note_field:
            entry[h] = st.text_area("Notas / Observaciones", value="")
        else:
            entry[h] = st.text_input(h, value="")

    submitted = st.form_submit_button("Guardar visita en la hoja")
    if submitted:
        try:
            append_visit_to_zone(z, entry)
            st.success("Visita guardada correctamente en la hoja " + z)
            # invalidate cache
            st.experimental_memo.clear()
        except Exception as e:
            st.error("Error al guardar: " + str(e))

st.markdown("----")
st.caption("Desarrollado para gestores — Lost Mary. Si quieres que la app también envíe un correo tras guardar o genere PDF, puedo añadirlo.")
