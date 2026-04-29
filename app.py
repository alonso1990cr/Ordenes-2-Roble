# 4. DASHBOARD (CON EXCEL PROTEGIDO)
elif menu == "📊 Dashboard":
    st.header("📊 Dashboard de Rendimiento")
    
    if df_ot.empty: 
        st.info("No hay datos registrados aún.")
    else:
        # --- LÓGICA DE EXCEL PROTEGIDO ---
        buffer = io.BytesIO()
        try:
            # Usamos xlsxwriter como motor para permitir la protección de la hoja
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_ot.to_excel(writer, index=False, sheet_name='Historial_OT')
                
                # Acceder al libro y la hoja para protegerlos
                workbook  = writer.book
                worksheet = writer.sheets['Historial_OT']
                
                # Establecer la hoja como "Solo Lectura" (protegida)
                # Esto evita cambios accidentales en las celdas
                worksheet.protect('Roble2026') 
                
            st.sidebar.download_button(
                label="📥 Descargar Reporte Excel (Protegido)",
                data=buffer.getvalue(),
                file_name=f"Reporte_Mantenimiento_{obtener_fecha_cr().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ModuleNotFoundError:
            st.sidebar.error("Error: Falta instalar 'xlsxwriter'. Agregue xlsxwriter al archivo requirements.txt en GitHub.")

        # --- RESTO DE FILTROS Y GRÁFICOS ---
        df_dash = df_ot.copy()
        df_dash['Inicio'] = pd.to_datetime(df_dash['Inicio'])
        df_dash['Fin'] = pd.to_datetime(df_dash['Fin'], errors='coerce')
        
        def get_hrs(row):
            if pd.notna(row['Fin']):
                d = calcular_duracion_laboral(row['Inicio'], row['Fin'])
                return round(d.total_seconds() / 3600, 2)
            return 0
        df_dash['Horas'] = df_dash.apply(get_hrs, axis=1)

        st.sidebar.subheader("Filtros de Análisis")
        f_emp = st.sidebar.selectbox("Por Operario:", ["TODOS"] + list(df_emp['Nombre'].unique()))
        f_tipo = st.sidebar.selectbox("Por Tipo de OT:", ["TODOS", "Preventivo", "Correctivo", "Casos 24h", "Casos ISO"])
        
        fecha_min = df_dash['Inicio'].min().date() if not df_dash.empty else obtener_fecha_cr().date()
        f_ini = st.sidebar.date_input("Desde", fecha_min)
        f_fin = st.sidebar.date_input("Hasta", obtener_fecha_cr().date())

        mask = (df_dash['Inicio'].dt.date >= f_ini) & (df_dash['Inicio'].dt.date <= f_fin)
        if f_emp != "TODOS": mask = mask & (df_dash['Empleado'] == f_emp)
        if f_tipo != "TODOS": mask = mask & (df_dash['Tipo'] == f_tipo)
        
        df_f = df_dash.loc[mask]

        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs Filtradas", len(df_f))
        c2.metric("Cerradas", len(df_f[df_f['Estado'] == 'Cerrada']))
        c3.metric("Promedio Horas", f"{df_f[df_f['Horas']>0]['Horas'].mean():.2f}" if not df_f[df_f['Horas']>0].empty else "0")

        if not df_f.empty:
            fig = px.bar(df_f, x='OT', y='Horas', color='Tipo', 
                         hover_data=['Empleado', 'Descripcion'],
                         title=f"Horas Laboradas (Filtro: {f_tipo})")
            st.plotly_chart(fig, use_container_width=True)
