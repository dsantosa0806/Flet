from requests_data.requisicoes_version import verificar_versao
from config import  current_version

VERSAO_LOCAL = current_version


def aba_inicial(ft, HEADING_FONT_SIZE, DEFAULT_FONT_SIZE, page):
    # Verifica versão ao carregar
    versao_info = verificar_versao()

    alerta_versao = ft.Container()
    if versao_info:
        alerta_versao = ft.Container(
            content=ft.Column([
                ft.Text("🚨 Nova versão disponível!", size=DEFAULT_FONT_SIZE + 2, weight="bold", color=ft.Colors.RED),
                ft.Text(f"Versão atual: {VERSAO_LOCAL}", size=DEFAULT_FONT_SIZE),
                ft.Text(f"Nova versão: {versao_info['nova_versao']}", size=DEFAULT_FONT_SIZE),
                ft.Text(f"Novidades:\n{versao_info['changelog']}", size=DEFAULT_FONT_SIZE),
                ft.TextButton("📥 Baixar atualização", on_click=lambda _: page.launch_url(versao_info['link']))
            ]),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.RED),
            padding=10,
            border_radius=10,
            border=ft.border.all(1, ft.Colors.RED)
        )

    return ft.Column([
        ft.Row([ft.Text("Início", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        alerta_versao,
        ft.Text("👋 Bem-vindo ao RPA Search Data", size=HEADING_FONT_SIZE + 2, weight="bold"),
        ft.Divider(),
        ft.Text("Essa aplicação automatiza e facilita a consulta e o "
                "download de relatórios do SIOR e do Sapiens Dívida.",
                size=DEFAULT_FONT_SIZE),
        ft.Text(
            "🧭 Navegação rápida:",
            size=DEFAULT_FONT_SIZE + 1,
            weight="bold"
        ),

        ft.Text(
            "• Home: retorna à tela inicial da aplicação.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• SIOR > Consulta > Auto de Infração: permite consultar dados detalhados dos AITs.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• SIOR > Consulta > Proprietário: permite consultar autos vinculados ao CPF/CNPJ do proprietário.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• SIOR > Consulta > Placa: permite consultar autos vinculados à placa do veículo, incluindo padrão antigo e Mercosul.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• SIOR > Consulta > Auto de Infração Cobrança: permite consultar autos em situação de cobrança.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• SIOR > Consulta > Devedor em Cobrança: permite consultar cobranças vinculadas ao CPF/CNPJ do devedor.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• SIOR > Consulta > Acompanhamento Painel Supervisor: permite extrair informações do painel de acompanhamento da equipe.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• SIOR > Distribuição de processos: permite realizar a distribuição automatizada de processos realizada pelo"
            "supervisor da equipe.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• SIOR > Download Relatórios: permite baixar relatórios financeiro e resumido em PDF.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• SIOR > Login Manual SIOR: permite atualizar manualmente os cookies de sessão quando o login automático falhar.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• Sapiens > Consulta Créditos: permite consultar créditos por CPF/CNPJ no Sapiens Dívida.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• CADIN > Consulta CADIN: permite consultar informações de registro no CADIN.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Text(
            "• Ajuda > Sobre: apresenta informações, instruções e detalhes da aplicação.",
            size=DEFAULT_FONT_SIZE
        ),

        ft.Divider(),

        ft.Text("⚠️ Dicas importantes:", size=DEFAULT_FONT_SIZE + 1, weight="bold"),

        ft.GestureDetector(
            content=ft.Text(
                "• Mantenha o Google Chrome instalado e atualizado. "
                "Após atualização, reinicie o computador"
                "Clique aqui para verificar como atualizar o Google Chrome",
                size=DEFAULT_FONT_SIZE,
                color=ft.Colors.BLUE,
            ),
            on_tap=lambda e: page.launch_url("https://support.google.com/chrome/answer/95414")),
        ft.Text("• Evite usar o SIOR ou Sapiens manualmente enquanto o RPA estiver rodando.", size=DEFAULT_FONT_SIZE),
        ft.Text("• Após o inicío de cada Consulta/Download,"
                " a navegação ficará desabilitada até finalizar todo o processamento."
                "Sempre extraia o relatório em xlsx após finalizar a consulta.", size=DEFAULT_FONT_SIZE),
        ft.GestureDetector(
            content=ft.Text(
                "• Clique aqui para assistir ao vídeo explicativo",
                size=DEFAULT_FONT_SIZE,
                color=ft.Colors.BLUE,
            ),
            on_tap=lambda e: page.launch_url("https://drive.google.com/file/d/1RoblMwNnSIzX9-g-NKIQP3WDsytV8d6c/view")
        ),
        ft.GestureDetector(
            content=ft.Text(
                "• Em caso de erro, feche e abra o RPA novamente ",
                size=DEFAULT_FONT_SIZE,
                color=ft.Colors.RED,
            ),
            on_tap=lambda e: page.launch_url("")),
        ft.Container(height=20),
        ft.Text("✅ Para começar, selecione uma opção no menu acima.", size=DEFAULT_FONT_SIZE, italic=True),
    ], expand=True, scroll="auto", spacing=10)
