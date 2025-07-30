def aba_inicial(ft, HEADING_FONT_SIZE, DEFAULT_FONT_SIZE, page):
    return ft.Column([
        ft.Row([ft.Text("Início", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        ft.Text("👋 Bem-vindo ao RPA Search Data", size=HEADING_FONT_SIZE + 2, weight="bold"),
        ft.Divider(),

        ft.Text("Essa aplicação automatiza e facilita a consulta e o download de relatórios"
                " do SIOR e do Sapiens Dívida.",
                size=DEFAULT_FONT_SIZE),

        ft.Text("🧭 Navegação rápida:", size=DEFAULT_FONT_SIZE + 1, weight="bold"),
        ft.Text("• SIOR > Consulta Auto de Infração: permite consultar dados detalhados dos AITs.",
                size=DEFAULT_FONT_SIZE),
        ft.Text("• SIOR > Download Relatórios: permite baixar os relatórios financeiro e resumido em PDF.",
                size=DEFAULT_FONT_SIZE),
        ft.Text("• Sapiens > Consulta Créditos: permite consultar os créditos por CPF/CNPJ no Sapiens Dívida.",
                size=DEFAULT_FONT_SIZE),
        ft.Text("• Ajuda > Sobre: informações e instruções da aplicação.",
                size=DEFAULT_FONT_SIZE),

        ft.Divider(),

        ft.Text("⚠️ Dicas importantes:", size=DEFAULT_FONT_SIZE + 1, weight="bold"),
        ft.Text("• Mantenha o Google Chrome instalado e atualizado.", size=DEFAULT_FONT_SIZE),
        ft.Text("• Evite usar o SIOR ou Sapiens manualmente enquanto o RPA estiver rodando.", size=DEFAULT_FONT_SIZE),
        ft.GestureDetector(
            content=ft.Text(
                "• Clique aqui para assistir ao vídeo explicativo",
                size=DEFAULT_FONT_SIZE,
                color=ft.Colors.BLUE,
            ),
            on_tap=lambda e: page.launch_url("https://drive.google.com/file/d/1RoblMwNnSIzX9-g-NKIQP3WDsytV8d6c/view?usp=sharinghttps://drive.google.com/file/d/1RoblMwNnSIzX9-g-NKIQP3WDsytV8d6c/view?usp=sharing")
        ),

        ft.Container(height=20),

        ft.Text("✅ Para começar, selecione uma opção no menu acima.", size=DEFAULT_FONT_SIZE, italic=True),
    ], expand=True, scroll="auto", spacing=10)
