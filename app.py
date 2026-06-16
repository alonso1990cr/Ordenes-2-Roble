elif menu == "Nueva OT":
    st.title("Nueva Orden de Trabajo")
    mostrar_reloj()

    if df_emp.empty:
        st.warning("Debe registrar empleados primero")
    else:

        with st.form("ot_form"):

            op = st.selectbox("Operario", df_emp["Nombre"])

            tp = st.radio(
                "Tipo",
                ["Preventivo", "Correctivo", "SNC alta", "SNC media", "SNC baja"],
                horizontal=True
            )

            # =========================
            # FRECUENCIA (SOLO PREVENTIVO)
            # =========================
            frecuencia_pm = None

            if tp == "Preventivo":
                frecuencia_pm = st.selectbox(
                    "Frecuencia Preventiva",
                    ["S - Semanal", "Q - Quincenal", "M - Mensual", "T - Trimestral", "S6 - Semestral", "A - Anual"]
                )

            # =========================
            # MATERIALES (CONTROL REAL)
            # =========================
            material_opcion = st.radio(
                "Materiales",
                ["No aplica material", "Ligar a Orden de Materiales"],
                horizontal=True
            )

            # 👇 IMPORTANTE: placeholder para forzar visibilidad correcta
            orden_materiales = "No aplica"

            if material_opcion == "Ligar a Orden de Materiales":
                orden_materiales = st.text_input(
                    "Digite Orden de Materiales",
                    placeholder="Ej: OM-000123"
                )

            # =========================
            # OTROS CAMPOS
            # =========================
            desc = st.text_area("Descripción")
            foto = st.file_uploader("Foto", type=["jpg", "png", "jpeg"])
            cp = st.text_input("Correo copia")

            generar = st.form_submit_button("Generar OT")

        # =====================================================
        # PROCESAMIENTO FUERA DEL FORM (CLAVE STREAMLIT)
        # =====================================================
        if generar:

            # VALIDACIÓN SIMPLE (EVITA ERRORES)
            if tp == "Preventivo" and not frecuencia_pm:
                st.error("Debe seleccionar frecuencia preventiva")
                st.stop()

            if material_opcion == "Ligar a Orden de Materiales" and orden_materiales.strip() == "":
                st.error("Debe digitar la orden de materiales")
                st.stop()

            id_ot = f"{len(df_ot)+1:04d}"
            correo_op = df_emp[df_emp["Nombre"] == op]["Correo"].values[0]

            nombre_foto = "Sin foto"
            if foto:
                nombre_foto = f"OT_{id_ot}.jpg"
                with open(os.path.join("fotos", nombre_foto), "wb") as f:
                    f.write(foto.getbuffer())

            nueva = {
                "OT": id_ot,
                "Empleado": op,
                "Descripcion": desc,
                "Inicio": obtener_fecha_cr().strftime("%Y-%m-%d %H:%M:%S"),
                "Tipo": tp,
                "FrecuenciaPM": frecuencia_pm if frecuencia_pm else "",
                "OrdenMateriales": orden_materiales,
                "Estado": "Abierta",
                "Fin": "",
                "Comentarios": "",
                "CorreoCopia": cp,
                "Foto": nombre_foto
            }

            df_ot = pd.concat([df_ot, pd.DataFrame([nueva])], ignore_index=True)
            guardar(df_ot, "ordenes.csv")

            correos = ["sa.alterna@gmail.com", correo_op, cp]

            cuerpo = f"""
OT #{id_ot}
Operario: {op}
Tipo: {tp}
Frecuencia: {frecuencia_pm}
Materiales: {orden_materiales}
Descripción: {desc}
"""

            enviar_correo(correos, f"OT #{id_ot}", cuerpo)

            st.success("OT creada correctamente")
            st.rerun()
