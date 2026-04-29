import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import plotly.express as px

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión OT - Roble", layout="wide")
UTC_OFFSET = 6 
CORREO_COPIA = "sa.alterna@gmail.com"

# --- ESTILO PERSONALIZADO (RELLENO VERDE) ---
st.markdown("""
    <style>
    .stTextInput > div > div > input, 
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div,
    .stMultiSelect > div > div {
        background-color: #e8f5e9 !important;
        color: #1b5e20 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_datos(archivo, columnas):
    if os.path.exists(archivo):
        df = pd.read_csv(archivo, dtype=str)
        for col in columnas:
            if col not in df.columns: df[col] = ""
        return df
    return pd.DataFrame(columns=columnas)

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

# --- FUNCIONES TÉCNICAS ---
def obtener_fecha_cr():
    return datetime.utcnow() - timedelta(hours=UTC_OFFSET)

def enviar_correo(destinatario, asunto, cuerpo):
    try:
        user = st.secrets["emails"]["sender_user"]
        password = st.secrets["emails"]["sender_password"]
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = f"{destinatario}, {CORREO_COPIA}"
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain'))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(user, password)
        server.sendmail(user, [destinatario, CORREO_COPIA], msg.as_string())
        server.quit()
        return True
    except: return False

def calcular_duracion_laboral(inicio, fin):
    total_segundos = 0
    curr = inicio
    while curr < fin:
        if curr.weekday() < 5: h_ini, h_fin, almuerzo = 8, 17, True
        elif curr.weekday() == 5: h_ini, h_fin, almuerzo = 7, 12, False
        else:
            curr = (curr + timedelta(days=1)).replace(hour=8, minute=0)
            continue
        ent = max(curr, curr.replace(hour=h_ini, minute=0, second=0))
        sal = min(fin, curr.replace(hour=h_fin, minute=0, second=0))
        if ent < sal:
            seg = (sal - ent).total_seconds()
            if almuerzo and ent.hour < 12 and sal.hour >= 13: seg -= 3600
            total_segundos += max(0, seg)
        curr = (curr + timedelta(days=1)).replace(hour=h_ini, minute=0)
    return timedelta(seconds=total_segundos)

# --- CARGA DE DATOS ---
df_emp = cargar_datos("empleados.csv", ["Nombre", "Correo"])
df_ot = cargar_datos("ordenes.csv", ["OT", "Empleado", "Descripcion", "Inicio", "Tipo", "Estado", "Fin", "Comentarios"])

# --- MENÚ PRINCIPAL ---
menu = st.sidebar.selectbox(
    "MENÚ PRINCIPAL", 
    ["👥 Gestión de Empleados", "📝 Nueva Orden de Trabajo", "🔍 Cierre y Consulta de OT", "📊 Dashboard"]
)

# 1. GESTIÓN DE EMPLEADOS
if menu == "👥 Gestión de Empleados":
    st.header("👥 Gestión de Operarios")
    col_reg, col_mod, col_del = st.columns(3)
    
    with col_reg:
        st.subheader("Registrar Nuevo")
        with st.form("nuevo_emp", clear_on_submit=True):
            nom = st.text_input("Nombre Completo")
            ema = st.text_input("Correo Electrónico")
            if st.form_submit_button("Añadir"):
                if nom and ema:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre": nom, "Correo": ema}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Registrado.")
                    st.rerun()

    with col_mod:
        st.subheader("Modificar Datos")
        if not df_emp.empty:
            emp_a_editar = st.selectbox("Elegir para editar:", df_emp['Nombre'])
            idx_edit = df_emp.index[df_emp['Nombre'] == emp_a_editar].tolist()[0]
            with st.form("editar_emp"):
                nuevo_nom = st.text_input("Nombre", value=df_emp.at[idx_edit, 'Nombre'])
                nuevo_ema = st.text_input("Correo", value=df_emp.at[idx_edit, 'Correo'])
                if st.form_submit_button("Actualizar"):
                    df_emp.at[idx_edit, 'Nombre'] = nuevo_nom
                    df_emp.at[idx_edit, 'Correo'] = nuevo_ema
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Actualizado.")
                    st.rerun()

    with col_del:
        st.subheader("Eliminar")
        if not df_emp.empty:
            emp_a_eliminar = st.selectbox("Elegir para borrar:", df_emp['Nombre'])
            if st.button("🗑️ Borrar Definitivamente"):
                df_emp = df_emp[df_emp['Nombre'] != emp_a_eliminar]
                guardar_datos(df_emp, "empleados.csv")
                st.warning("Eliminado.")
                st.rerun()

    st.divider()
    st.table(df_emp)

# 2. NUEVA ORDEN DE TRABAJO
elif menu == "📝 Nueva Orden de Trabajo":
    st.header("📝 Apertura de OT")
    if df_emp.empty: 
        st.warning("Debe registrar empleados primero.")
    else:
        with st.form("nueva_ot", clear_on_submit=True):
            operario = st.selectbox("Operario", df_emp['Nombre'])
            tipo = st.radio("Tipo", ["Preventivo", "Correctivo", "Casos 24h", "Casos ISO"], horizontal=True)
            desc = st.text_area("Descripción")
            if st.form_submit_button("Generar OT"):
                if desc:
                    ahora = obtener_fecha_cr()
                    num_ot = ahora.strftime("%Y%m%d-%H%M")
                    nueva = {"OT": num_ot, "Empleado": operario, "Descripcion": desc, 
                             "Inicio": ahora.strftime("%Y-%m-%d %H:%M:%S"), "Tipo": tipo, 
                             "Estado": "Abierta", "Fin": "", "Comentarios": ""}
                    df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success(f"OT #{num_ot} creada.")
                    st.rerun()

# 3. CIERRE Y CONSULTA
elif menu == "🔍 Cierre y Consulta de OT":
    st.header("🔍 Seguimiento de Órdenes")
    t_abiertas, t_cerradas = st.tabs(["Abiertas", "Cerradas"])
    
    with t_abiertas:
        abiertas = df_ot[df_ot['Estado'] == "Abierta"].copy()
        if abiertas.empty: 
            st.info("No hay órdenes abiertas.")
        else:
            st.dataframe(abiertas, use_container_width=True)
            abiertas['Seleccion'] = abiertas['OT'] + " | " + abiertas['Descripcion']
            opcion_sel = st.selectbox("Seleccione ID y Descripción para cerrar:", abiertas['Seleccion'])
            ot_id_sel = opcion_sel.split(" | ")[0]
            desc_sel = opcion_sel.split(" | ")[1]
            idx_ot = df_ot.index[(df_ot['OT'] == ot_id_sel) & (df_ot['Descripcion'] == desc_sel)].tolist()[0]
            
            with st.form("form_cierre"):
                coment = st.text_area("Comentarios", value=df_ot.at[idx_ot, 'Comentarios'])
                accion = st.selectbox("Estado", ["Abierta", "Cerrada"])
                if st.form_submit_button("Confirmar Cambios"):
                    df_ot.at[idx_ot, 'Comentarios'] = coment
                    df_ot.at[idx_ot, 'Estado'] = accion
                    if accion == "Cerrada":
                        df_ot.at[idx_ot, 'Fin'] = obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S")
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success("Orden actualizada.")
                    st.rerun()

    with t_cerradas:
        cerradas = df_ot[df_ot['Estado'] == "Cerrada"].copy()
        if cerradas.empty: 
            st.info("No hay historial.")
        else:
            def calc_dur(row):
                try:
                    ini = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                    fin = datetime.strptime(row['Fin'], "%Y-%m-%d %H:%M:%S")
                    return str(calcular_duracion_laboral(ini, fin))
                except: return "N/A"
            cerradas['Duración'] = cerradas.apply(calc_dur, axis=1)
            st.dataframe(cerradas, use_container_width=True)

# 4. DASHBOARD (CON FILTRO POR TIPO)
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if df_ot.empty: 
        st.info("No hay datos.")
    else:
        df_dash = df_ot.copy()
        df_dash['Inicio'] = pd.to_datetime(df_dash['Inicio'])
        df_dash['Fin'] = pd.to_datetime(df_dash['Fin'], errors='coerce')
        
        def get_hrs(row):
            if pd.notna(row['Fin']):
                d = calcular_duracion_laboral(row['Inicio'], row['Fin'])
                return round(d.total_seconds() / 3600, 2)
            return 0
        df_dash['Horas'] = df_dash.apply(get_hrs, axis=1)

        # Filtros en la barra lateral
        st.sidebar.subheader("Filtros de Análisis")
        f_emp = st.sidebar.selectbox("Por Operario:", ["TODOS"] + list(df_emp['Nombre'].unique()))
        
        # NUEVO FILTRO POR TIPO
        f_tipo = st.sidebar.selectbox("Por Tipo de OT:", ["TODOS", "Preventivo", "Correctivo", "Casos 24h", "Casos ISO"])
        
        fecha_min = df_dash['Inicio'].min().date() if not df_dash.empty else obtener_fecha_cr().date()
        f_ini = st.sidebar.date_input("Desde", fecha_min)
        f_fin = st.sidebar.date_input("Hasta", obtener_fecha_cr().date())

        # Aplicación de filtros
        mask = (df_dash['Inicio'].dt.date >= f_ini) & (df_dash['Inicio'].dt.date <= f_fin)
        if f_emp != "TODOS": mask = mask & (df_dash['Empleado'] == f_emp)
        if f_tipo != "TODOS": mask = mask & (df_dash['Tipo'] == f_tipo)
        
        df_f = df_dash.loc[mask]

        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs Filtradas", len(df_f))
        c2.metric("Cerradas", len(df_f[df_f['Estado'] == 'Cerrada']))
        c3.metric("Promedio Horas", f"{df_f[df_f['Horas']>0]['Horas'].mean():.2f}" if not df_f[df_f['Horas']>0].empty else "0")

        # Gráfico dinámico
        if not df_f.empty:
            fig = px.bar(df_f, x='OT', y='Horas', color='Tipo', 
                         hover_data=['Empleado', 'Descripcion'],
                         title=f"Horas Laboradas (Filtro: {f_tipo})")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No hay datos para los filtros seleccionados.")
