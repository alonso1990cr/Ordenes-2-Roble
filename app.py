import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image
import io
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 # Costa Rica

# Refresco silencioso cada 1 segundo para el reloj
st_autorefresh(interval=1000, key="daterefresh")

if not os.path.exists("fotos"):
    os.makedirs("fotos")

# --- FUNCIONES DE APOYO ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def mostrar_reloj_discreto():
    """Muestra la hora en rojo, pequeña y alineada a la derecha."""
    hora_actual = obtener_fecha_cr().strftime("%d/%m/%Y %H:%M:%S")
    st.markdown(
        f"""
        <div style="text-align: right; margin-top: -55px; margin-bottom: 20px;">
            <p style="color: #ff4b4b; font-size: 13px; font-family: monospace; font-weight: bold;">
                SISTEMA CR: {hora_actual}
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )

def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        try:
            return pd.read_csv(archivo, dtype=str).fillna("")
        except:
            return pd.DataFrame(columns=columnas)
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

def estilo_estados(val):
    if val == 'Abierta': return 'color: green; font-weight: bold'
    if val == 'En Pausa': return 'color: orange; font-weight: bold'
    if val == 'Cerrada': return 'color: red; font-weight: bold'
    return ''

def generar_excel_protegido(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Historial_OT')
        workbook  = writer.book
        worksheet = writer.sheets['Historial_OT']
        worksheet.protect('Roble2026', {'autofilter': True})
    return output.getvalue()

# --- CARGA DE DATOS ---
cols_ot = ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios", "CorreoCopia", "TiempoAcumulado", "Foto"]
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", cols_ot)

# --- NAVEGACIÓN ---
st.sidebar.title("🛠️ Panel de Control")
menu = st.sidebar.selectbox("Seleccione sección:", ["👥 Empleados", "📝 Nueva OT", "🔍 Cierre y Consulta", "📊 Dashboard"])

# --- SECCIÓN: EMPLEADOS ---
if menu == "👥 Empleados":
    st.header("👥 Gestión de Personal")
    mostrar_reloj_discreto()
    
    t1, t2, t3 = st.tabs(["➕ Registrar", "✏️ Modificar", "🗑️ Eliminar"])
    
    with t1:
        with st.form("add_emp", clear_on_submit=True):
            n = st.text_input("Nombre Completo")
            c = st.text_input("Correo Electrónico")
            if st.form_submit_button("Registrar"):
                if n and c:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre":n,"Correo":c}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Empleado registrado"); st.rerun()

    with t2:
        if not df_emp.empty:
            sel_m = st.selectbox("Seleccione empleado a editar:", df_emp['Nombre'])
            idx_m = df_emp.index[df_emp['Nombre'] == sel_m].tolist()[0]
            with st.form("edit_emp"):
                new_n = st.text_input("Nombre", value=df_emp.at[idx_m, 'Nombre'])
                new_c = st.text_input("Correo", value=df_emp.at[idx_m, 'Correo'])
                if st.form_submit_button("Actualizar Datos"):
                    df_emp.at[idx_m, 'Nombre'], df_emp.at[idx_m, 'Correo'] = new_n, new_c
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Datos actualizados"); st.rerun()

    with t3:
        if not df_emp.empty:
            borrar = st.selectbox("Seleccione empleado a eliminar:", df_emp['Nombre'])
            conf = st.checkbox(f"Confirmo que deseo eliminar a {borrar}")
            if st.button("Eliminar Permanentemente") and conf:
                df_emp = df_emp[df_emp['Nombre'] != borrar]
                guardar_datos(df_emp, "empleados.csv")
                st.warning("Empleado eliminado"); st.rerun()
    
    st.subheader("Lista de Personal Activo")
    st.table(df_emp)

# --- SECCIÓN: NUEVA OT ---
elif menu == "📝 Nueva OT":
    st.header("📝 Apertura de Orden de Trabajo")
    mostrar_reloj_discreto()
    if df_emp.empty:
        st.warning("Debe registrar personal en la sección de Empleados primero.")
    else:
        with st.form("f_ot", clear_on_submit=True):
            op = st.selectbox("Operario Asignado", df_emp['Nombre'])
            tp = st.radio("Tipo de Trabajo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            ds = st.text_area("Descripción del Hallazgo")
            foto = st.file_uploader("Adjuntar Foto (Opcional)", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo para copia adicional")
            
            if st.form_submit_button("Generar Orden de Trabajo"):
                id_ot = f"{len(df_ot) + 1:04d}"
                nom_foto = f"OT_{id_ot}.jpg" if foto else "Sin foto"
                if foto:
                    with open(os.path.join("fotos", nom_foto), "wb") as f: f.write(foto.getbuffer())
                
                nueva = {"OT":id_ot, "Empleado":op, "Descripcion":ds, "Inicio":obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                         "Tipo":tp, "Estado":"Abierta", "Fin":"", "Comentarios":"", "CorreoCopia":cp, "TiempoAcumulado":"0", "Foto":nom_foto}
                
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                st.success(f"OT #{id_ot} creada con éxito."); st.rerun()

# --- SECCIÓN: CIERRE Y CONSULTA ---
elif menu == "🔍 Cierre y Consulta":
    st.header("🔍 Gestión de Cierre y Consulta")
    mostrar_reloj_discreto()
    tab1, tab2 = st.tabs(["Órdenes Activas", "Historial Completo"])
    
    with tab1:
        pendientes = df_ot[df_ot['Estado'].isin(["Abierta", "En Pausa"])].copy()
        if not pendientes.empty:
            st.dataframe(pendientes[["OT", "Estado", "Empleado", "Tipo", "Descripcion"]].style.map(estilo_estados, subset=['Estado']), use_container_width=True, hide_index=True)
            
            sel = st.selectbox("Seleccionar OT:", ["---"] + (pendientes['OT'] + " | " + pendientes['Empleado']).tolist())
            if sel != "---":
                idx = df_ot.index[df_ot['OT'] == sel.split(" | ")[0]].tolist()[0]
                
                # Imagen
                f_nom = df_ot.at[idx, 'Foto']
                if f_nom != "Sin foto" and os.path.exists(os.path.join("fotos", f_nom)):
                    st.image(os.path.join("fotos", f_nom), width=300, caption="Evidencia Inicial")
                
                with st.form("gestion_ot"):
                    nuevo_est = st.selectbox("Estado", ["Abierta", "En Pausa", "Cerrada"], index=["Abierta", "En Pausa", "Cerrada"].index(df_ot.at[idx, 'Estado']))
                    nuevo_com = st.text_area("Comentarios / Avances", value=df_ot.at[idx, 'Comentarios'])
                    if st.form_submit_button("Actualizar OT"):
                        df_ot.at[idx, 'Estado'], df_ot.at[idx, 'Comentarios'] = nuevo_est, nuevo_com
                        if nuevo_est == "Cerrada":
                            df_ot.at[idx, 'Fin'] = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                        guardar_datos(df_ot, "ordenes.csv"); st.rerun()

    with tab2:
        st.dataframe(df_ot.style.map(estilo_estados, subset=['Estado']), use_container_width=True)
        if not df_ot.empty:
            st.download_button("📥 Exportar Historial (Excel)", generar_excel_protegido(df_ot), "Historial_OT_Roble.xlsx")

# --- SECCIÓN: DASHBOARD ---
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    mostrar_reloj_discreto()
    
    if not df_ot.empty:
        st.sidebar.divider()
        st.sidebar.subheader("🎯 Filtros")
        
        df_ot['Inicio_dt'] = pd.to_datetime(df_ot['Inicio'], errors='coerce')
        f_min = df_ot['Inicio_dt'].min().date() if not df_ot['Inicio_dt'].dropna().empty else obtener_fecha_cr().date()
        
        rango = st.sidebar.date_input("Periodo", [f_min, obtener_fecha_cr().date()])
        op_sel = st.sidebar.selectbox("Operario", ["Todos"] + sorted(df_ot['Empleado'].unique().tolist()))
        tp_sel = st.sidebar.selectbox("Tipo de Trabajo", ["Todos"] + sorted(df_ot['Tipo'].unique().tolist()))

        # Filtrado
        df_f = df_ot.copy()
        if len(rango) == 2:
            df_f = df_f[(df_f['Inicio_dt'].dt.date >= rango[0]) & (df_f['Inicio_dt'].dt.date <= rango[1])]
        if op_sel != "Todos": df_f = df_f[df_f['Empleado'] == op_sel]
        if tp_sel != "Todos": df_f = df_f[df_f['Tipo'] == tp_sel]

        # Métricas y Gráficos
        df_f['Horas'] = pd.to_numeric(df_f['TiempoAcumulado'], errors='coerce').fillna(0) / 3600
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OT", len(df_f))
        c2.metric("Horas Invertidas", f"{df_f['Horas'].sum():.2f}")
        c3.metric("Completadas", len(df_f[df_f['Estado'] == "Cerrada"]))
        
        st.plotly_chart(px.bar(df_f, x='OT', y='Horas', color='Tipo', barmode='group'), use_container_width=True)
        st.plotly_chart(px.pie(df_f, names='Estado', hole=0.4), use_container_width=True)
    else:
        st.info("Sin datos para procesar el Dashboard.")
