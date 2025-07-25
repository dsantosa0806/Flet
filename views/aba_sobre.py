

def aba_sobre(ft, HEADING_FONT_SIZE, DEFAULT_FONT_SIZE):
    # === ABA 4: SOBRE ===
    aba_sobre = ft.Column([
        ft.Text("ℹ️ SOBRE", size=HEADING_FONT_SIZE, weight="bold"),
        ft.Text("Consulta e download de AIT via SIOR.", size=DEFAULT_FONT_SIZE)
    ], expand=True)