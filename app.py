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
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", ["Dashboard", "Gestión de Empleados", "Nueva Orden de Trabajo", "Cierre y Consulta de OT"])

# 1. DASHBOARD
if menu == "Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    if df_ot.empty: 
        st.info("No hay datos registrados aún.")
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

        f_emp = st.sidebar.selectbox("Filtrar Operario:", ["TODOS"] + list(df_emp['Nombre'].unique()))
        f_ini = st.sidebar.date_input("Desde", df_dash['Inicio'].min().date())
        f_fin = st.sidebar.date_input("Hasta", obtener_fecha_cr().date())

        mask = (df_dash['Inicio'].dt.date >= f_ini) & (df_dash['Inicio'].dt.date <= f_fin)
        if f_emp != "TODOS": mask = mask & (df_dash['Empleado'] == f_emp)
        df_f = df_dash.loc[mask]

        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_f))
        c2.metric("Cerradas", len(df_f[df_f['Estado'] == 'Cerrada']))
        c3.metric("Promedio Horas", f"{df_f[df_f['Horas']>0]['Horas'].mean():.2f}" if not df_f[df_f['Horas']>0].empty else "0")

        fig = px.bar(df_f, x='OT', y='Horas', color='Empleado', title="Horas Laboradas por Orden")
        st.plotly_chart(fig, use_container_width=True)

# 2. GESTIÓN DE EMPLEADOS (COMPLETA)
elif menu == "Gestión de Empleados":
    st.header("👥 Gestión de Operarios")
    
    col_reg, col_mod = st.columns(2)
    
    with col_reg:
        st.subheader("Registrar Nuevo")
        with st.form("nuevo_emp", clear_on_submit=True):
            nom = st.text_input("Nombre Completo")
            ema = st.text_input("Correo Electrónico")
            if st.form_submit_button("Añadir Operario"):
                if nom and ema:
                    df_emp = pd.concat([df_emp, pd.DataFrame([{"Nombre": nom, "Correo": ema}])], ignore_index=True)
                    guardar_datos(df_emp, "empleados.csv")
                    st.success(f"Registrado: {nom}")
                    st.rerun()
                else:
                    st.error("Llene todos los campos.")

    with col_mod:
        st.subheader("Modificar Existente")
        if not df_emp.empty:
            emp_a_editar = st.selectbox("Seleccione para editar:", df_emp['Nombre'])
            idx = df_emp.index[df_emp['Nombre'] == emp_a_editar].tolist()[0]
            
            with st.form("editar_emp"):
                nuevo_nom = st.text_input("Editar Nombre", value=df_emp.at[idx, 'Nombre'])
                nuevo_ema = st.text_input("Editar Correo", value=df_emp.at[idx, 'Correo'])
                if st.form_submit_button("Actualizar Datos"):
                    df_emp.at[idx, 'Nombre'] = nuevo_nom
                    df_emp.at[idx, 'Correo'] = nuevo_ema
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Cambios guardados con éxito.")
                    st.rerun()
        else:
            st.info("No hay empleados registrados para modificar.")

    st.divider()
    st.subheader("Lista Actual de Operarios")
    st.table(df_emp)

# 3. NUEVA ORDEN DE TRABAJO
elif menu == "Nueva Orden de Trabajo":
    st.header("📝 Apertura de OT")
    if df_emp.empty: 
        st.warning("Debe registrar al menos un empleado antes de abrir una OT.")
    else:
        with st.form("nueva_ot"):
            operario = st.selectbox("Seleccionar Operario", df_emp['Nombre'])
            tipo = st.radio("Tipo de Mantenimiento", ["Preventivo", "Correctivo"])
            desc = st.text_area("Descripción de la falla/tarea")
            if st.form_submit_button("Generar OT"):
                ahora = obtener_fecha_cr()
                num_ot = ahora.strftime("%Y%m%d-%H%M")
                nueva_linea = {"OT": num_ot, "Empleado": operario, "Descripcion": desc, 
                               "Inicio": ahora.strftime("%Y-%m-%d %H:%M:%S"), "Tipo": tipo, 
                               "Estado": "Abierta", "Fin": "", "Comentarios": ""}
                df_ot = pd.concat([df_ot, pd.DataFrame([nueva_linea])], ignore_index=True)
                guardar_datos(df_ot, "ordenes.csv")
                
                correo_op = df_emp[df_emp['Nombre'] == operario]['Correo'].values[0]
                enviar_correo(correo_op, f"Nueva OT Asignada: #{num_ot}", f"Se ha abierto una OT para: {desc}")
                st.success(f"OT #{num_ot} creada y notificada.")

# 4. CIERRE Y CONSULTA (CON PESTAÑAS SEPARADAS)
elif menu == "Cierre y Consulta de OT":
    st.header("🔍 Seguimiento de Órdenes")
    t_abiertas, t_cerradas = st.tabs(["Órdenes en Proceso", "Historial de Cerradas"])
    
    with t_abiertas:
        abiertas = df_ot[df_ot['Estado'] == "Abierta"]
        if abiertas.empty: 
            st.info("No hay órdenes de trabajo abiertas.")
        else:
            st.dataframe(abiertas, use_container_width=True)
            st.subheader("Gestionar Cierre")
            ot_id = st.selectbox("Seleccione ID de OT para cerrar:", abiertas['OT'])
            idx_ot = df_ot.index[df_ot['OT'] == ot_id].tolist()[0]
            
            with st.form("form_cierre"):
                comentarios = st.text_area("Hallazgos / Comentarios finales", value=df_ot.at[idx_ot, 'Comentarios'])
                accion = st.selectbox("Cambiar estado a:", ["Abierta", "Cerrada"])
                if st.form_submit_button("Confirmar Cambios"):
                    df_ot.at[idx_ot, 'Comentarios'] = comentarios
                    df_ot.at[idx_ot, 'Estado'] = accion
                    if accion == "Cerrada":
                        fecha_fin = obtener_fecha_cr()
                        df_ot.at[idx_ot, 'Fin'] = fecha_fin.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Cálculo de duración laboral
                        f_ini = datetime.strptime(df_ot.at[idx_ot, 'Inicio'], "%Y-%m-%d %H:%M:%S")
                        duracion = calcular_duracion_laboral(f_ini, fecha_fin)
                        
                        correo_op = df_emp[df_emp['Nombre'] == df_ot.at[idx_ot, 'Empleado']]['Correo'].values[0]
                        enviar_correo(correo_op, f"OT #{ot_id} Cerrada", f"La orden ha sido cerrada con éxito. Duración efectiva: {duracion}")
                    
                    guardar_datos(df_ot, "ordenes.csv")
                    st.success("Orden actualizada correctamente.")
                    st.rerun()

    with t_cerradas:
        cerradas = df_ot[df_ot['Estado'] == "Cerrada"].copy()
        if cerradas.empty:
            st.info("No hay historial de órdenes cerradas.")
        else:
            # Calcular duración visual para la tabla
            def calc_dur_str(row):
                ini = datetime.strptime(row['Inicio'], "%Y-%m-%d %H:%M:%S")
                fin = datetime.strptime(row['Fin'], "%Y-%m-%d %H:%M:%S")
                return str(calcular_duracion_laboral(ini, fin))
            
            cerradas['Duración Laboral'] = cerradas.apply(calc_dur_str, axis=1)
            st.dataframe(cerradas, use_container_width=True)
