# --- MENÚ PRINCIPAL ---
menu = st.sidebar.selectbox("MENÚ PRINCIPAL", ["Dashboard", "Gestión de Empleados", "Nueva Orden de Trabajo", "Cierre y Consulta de OT"])

# 1. EL PRIMER BLOQUE DEBE SER "IF"
if menu == "Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    # ... (todo el código del dashboard)

# 2. LOS SIGUIENTES DEBEN SER "ELIF" Y ESTAR ALINEADOS CON EL "IF"
elif menu == "Gestión de Empleados":
    st.header("👥 Gestión de Operarios")
    
    col_reg, col_mod, col_del = st.columns(3)
    
    # --- COLUMNA 1: REGISTRAR ---
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

    # --- COLUMNA 2: MODIFICAR ---
    with col_mod:
        st.subheader("Modificar Datos")
        if not df_emp.empty:
            emp_a_editar = st.selectbox("Seleccione para editar:", df_emp['Nombre'], key="edit_select")
            idx_edit = df_emp.index[df_emp['Nombre'] == emp_a_editar].tolist()[0]
            with st.form("editar_emp"):
                nuevo_nom = st.text_input("Editar Nombre", value=df_emp.at[idx_edit, 'Nombre'])
                nuevo_ema = st.text_input("Editar Correo", value=df_emp.at[idx_edit, 'Correo'])
                if st.form_submit_button("Actualizar Datos"):
                    df_emp.at[idx_edit, 'Nombre'] = nuevo_nom
                    df_emp.at[idx_edit, 'Correo'] = nuevo_ema
                    guardar_datos(df_emp, "empleados.csv")
                    st.success("Cambios guardados.")
                    st.rerun()

    # --- COLUMNA 3: ELIMINAR ---
    with col_del:
        st.subheader("Eliminar Operario")
        if not df_emp.empty:
            emp_a_eliminar = st.selectbox("Seleccione para borrar:", df_emp['Nombre'], key="del_select")
            if st.button("🗑️ Eliminar Definitivamente"):
                df_emp = df_emp[df_emp['Nombre'] != emp_a_eliminar]
                guardar_datos(df_emp, "empleados.csv")
                st.warning(f"Se ha eliminado a {emp_a_eliminar}")
                st.rerun()

# 3. OTROS ELIF PARA LAS DEMÁS PESTAÑAS
elif menu == "Nueva Orden de Trabajo":
    st.header("📝 Apertura de OT")
    # ... (código de nueva OT)

elif menu == "Cierre y Consulta de OT":
    st.header("🔍 Seguimiento de Órdenes")
    # ... (código de cierre)
