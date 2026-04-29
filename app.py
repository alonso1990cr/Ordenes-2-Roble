import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- FUNCIONES TÉCNICAS ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            df = pd.read_csv(archivo, dtype=str).fillna("")
            return df
        except:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- MENÚ LATERAL ---
st.sidebar.title("🛠️ Navegación Principal")
menu = st.sidebar.selectbox(
    "Seleccione una sección:", 
    ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"]
)

# --- LÓGICA DE SECCIONES ---

if menu == "👥 Empleados":
    st.header("👥 Gestión de Operarios")
    with st.form("add_emp", clear_on_submit=True):
        n = st.text_input("Nombre Completo")
        c = st.text_input("Correo Electrónico")
        if st.form_submit_button("Registrar"):
            if n and c:
                df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                guardar_datos(df_emp, "empleados.csv")
                st.success("Operario registrado.")
                st.rerun()
    st.table(df_emp)

elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    if df_emp.empty:
        st.warning("Registre operarios primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            archivo_foto = st.file_uploader("Capturar Foto (Opcional)", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo de copia")
            if st.form_submit_button("Generar Orden"):
                if ds and cp:
                    id_ot = f"{len(df_ot) + 1:04d}"
                    nombre_foto = "Sin foto"
                    if archivo_foto:
                        nombre_foto = f"OT_{id_ot}.jpg"
                        with open(os.path.join("fotos", nombre_foto), "wb") as f:
                            f.write(archivo_foto.getbuffer())
                    
                    nueva = {"OT": id_ot, "Empleado": op, "Descripcion": ds, 
                             "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                             "Tipo": tp, "Estado": "Abierta", "Fin": "", "Comentarios": "", 
                             "CorreoCopia": cp, "TiempoAcumulado": "0", "Foto": nombre_foto}
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success(f"OT #{id_ot} guardada con éxito."); st.rerun()

elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    def estilo_estados(val):
        if val == 'Abierta': return 'color: green; font-weight: bold'
        if val == 'En Pausa': return 'color: orange; font-weight: bold'
        if val == 'Cerrada': return 'color: red; font-weight: bold'
        return ''

    with tab1:
        pendientes = df_ot[df_ot['Estado'].str.contains("Abierta|En Pausa", case=False, na=False)].copy()
        if pendientes.empty:
            st.info("No hay órdenes pendientes.")
        else:
            ahora = obtener_fecha_cr()
            def formatear_duracion(row):
                try:
                    total_segundos = float(row['TiempoAcumulado'])
                    if row['Estado'] == "Abierta":
                        inicio = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                        total_segundos += (ahora - inicio).total_seconds()
                    h, m = int(total_segundos // 3600), int((total_segundos % 3600) // 60)
                    return f"{h}h {m}m"
                except: return "0h 0m"

            pendientes['Duración'] = pendientes.apply(formatear_duracion, axis=1)
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Tipo", "Inicio", "Duración", "Comentarios", "Descripcion"]].style.map(estilo_estados, subset=['Estado']), use_container_width=True, hide_index=True)
            
            st.divider()
            opciones = ["--- Seleccione una orden ---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist()
            sel = st.selectbox("Escoger OT para editar:", opciones)

            if sel != "--- Seleccione una orden ---":
                id_sel = sel.split(" | ")[0]
                idx = df_ot.index[df_ot['OT'] == id_sel].tolist()[0]
                
                # REINTEGRO DE FOTO
                foto_nom = str(df_ot.at[idx, 'Foto'])
                if foto_nom != "Sin foto" and foto_nom != "":
                    ruta = os.path.join("fotos", foto_nom)
                    if os.path.exists(ruta):
                        st.image(ruta, caption=f"Evidencia OT #{id_sel}", width=400)

                with st.form("form_cierre", clear_on_submit=True):
                    nuevo_est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    coment = st.text_area("Avances", value=df_ot.at[idx, 'Comentarios'])
                    if st.form_submit_button("Actualizar y Guardar"):
                        ahora_act = obtener_fecha_cr()
                        if df_ot.at[idx, 'Estado'] == "Abierta":
                            inicio_dt = datetime.strptime(df_ot.at[idx, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                            df_ot.at[idx, 'TiempoAcumulado'] = str(float(df_ot.at[idx, 'TiempoAcumulado']) + (ahora_act - inicio_dt).total_seconds())
                        
                        df_ot.at[idx, 'Estado'], df_ot.at[idx, 'Comentarios'] = nuevo_est, coment
                        if nuevo_est == "Abierta": df_ot.at[idx, 'Inicio'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                        elif nuevo_est == "Cerrada": df_ot.at[idx, 'Fin'] = ahora_act.strftime("%Y-%m-%d %H:%M:%S")
                        
                        guardar_datos(df_ot, "ordenes.csv")
                        st.success("✅ Registro actualizado correctamente"); st.rerun()

    with tab2:
        st.dataframe(df_ot.style.map(estilo_estados, subset=['Estado']), use_container_width=True)

elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if df_ot.empty:
        st.info("No hay datos.")
    else:
        # REINTEGRO DE FILTROS
        st.sidebar.divider()
        st.sidebar.subheader("🎯 Filtros")
        df_ot['Inicio_dt'] = pd.to_datetime(df_ot['Inicio'], errors='coerce')
        
        f_min = df_ot['Inicio_dt'].min().date() if not df_ot['Inicio_dt'].dropna().empty else obtener_fecha_cr().date()
        rango = st.sidebar.date_input("Rango de Fechas", [f_min, obtener_fecha_cr().date()])
        op_sel = st.sidebar.selectbox("Operario", ["Todos"] + sorted(df_ot['Empleado'].unique().tolist()))
        tp_sel = st.sidebar.selectbox("Tipo", ["Todos"] + sorted(df_ot['Tipo'].unique().tolist()))

        df_f = df_ot.copy()
        if len(rango) == 2:
            df_f = df_f[(df_f['Inicio_dt'].dt.date >= rango[0]) & (df_f['Inicio_dt'].dt.date <= rango[1])]
        if op_sel != "Todos": df_f = df_f[df_f['Empleado'] == op_sel]
        if tp_sel != "Todos": df_f = df_f[df_f['Tipo'] == tp_sel]

        df_f['Horas'] = pd.to_numeric(df_f['TiempoAcumulado'], errors='coerce').fillna(0) / 3600
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Órdenes", len(df_f))
        c2.metric("Horas Totales", f"{df_f['Horas'].sum():.2f}")
        c3.metric("Cerradas", len(df_f[df_f['Estado'] == "Cerrada"]))
        
        st.plotly_chart(px.bar(df_f, x='OT', y='Horas', color='Tipo', title="Horas por OT"), use_container_width=True)
        st.plotly_chart(px.pie(df_f, names='Estado', title="Distribución por Estado"), use_container_width=True)
