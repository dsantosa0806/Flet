import flet as ft

from requests_data.requisicoes_version import verificar_versao
from views.aba_consulta_sapiens_divida import aba_consulta_sapiens
from views.aba_consulta_sior import aba_consulta
from views.aba_consulta_sior_painel_supervisor import aba_consulta_sior_painel_supervisor
from views.aba_download import aba_download
from views.aba_sobre import aba_sobre
from config import DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, WINDOW_WIDTH, WINDOW_HEIGHT, APP_TITLE
from views.aba_inicial import aba_inicial
from views.aba_consulta_sior_cobranca import aba_consulta_auto_cobranca
from views.aba_copia_pa import aba_copia_pa


def construir_cabecalho(toggle_switch):
    return ft.Row([
        ft.Text(APP_TITLE, size=HEADING_FONT_SIZE, weight="bold"),
        toggle_switch
    ])


def main(page: ft.Page):
    verificar_versao(ft, page)
    page.title = APP_TITLE
    page.window_width = WINDOW_WIDTH
    page.window_height = WINDOW_HEIGHT
    page.scroll = "AUTO"
    page.padding = 25
    page.theme_mode = "dark"
    page.window_resizable = True

    # Alternância de tema
    def toggle_theme(e):
        page.theme_mode = "dark" if page.theme_mode == "light" else "light"
        toggle_switch.label = "🌙 Modo Escuro" if page.theme_mode == "light" else "🌞 Modo Claro"
        page.update()

    toggle_switch = ft.Switch(
        label="🌙 Modo Escuro",
        value=False,
        on_change=toggle_theme,
        tooltip="Alternar claro/escuro"
    )

    # Cabeçalho com título e botão de tema
    cabecalho = ft.Row([
        ft.Text(APP_TITLE, size=HEADING_FONT_SIZE, weight="bold"),
        ft.Container(expand=True),
        toggle_switch
    ])

    conteudo_abas = ft.Container(expand=True)

    # Callback para mudar conteúdo
    def atualizar_conteudo(opcao: str):
        if opcao == "SIOR_Consulta":
            conteudo_abas.content = aba_consulta(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page)
        elif opcao == "SIOR_Download":
            conteudo_abas.content = aba_download(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page)
        elif opcao == "Sapiens_Consulta":
            conteudo_abas.content = aba_consulta_sapiens(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page)
        elif opcao == "Sapiens_Copia_Pa":
            conteudo_abas.content = aba_copia_pa(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page)
        elif opcao == "Sobre":
            conteudo_abas.content = aba_sobre(ft, HEADING_FONT_SIZE, DEFAULT_FONT_SIZE)
        elif opcao == "Inicio":
            conteudo_abas.content = aba_inicial(ft, HEADING_FONT_SIZE, DEFAULT_FONT_SIZE, page)
        elif opcao == "SIOR_Consulta_Cobranca":
            conteudo_abas.content = aba_consulta_auto_cobranca(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page)
        elif opcao == "SIOR_Consulta_Painel_Super":
            conteudo_abas.content = aba_consulta_sior_painel_supervisor(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page)
        page.update()

    # Menu principal e submenu
    menu = ft.Row([

        ft.PopupMenuButton(
            content=ft.Text("SIOR"),
            tooltip="",
            menu_padding=0,
            menu_position=ft.PopupMenuPosition.UNDER,  # CORRETO
            items=[
                ft.PopupMenuItem(
                    text="Consulta Auto de Infração",
                    on_click=lambda e: atualizar_conteudo("SIOR_Consulta"),
                    checked=False
                ),
                ft.PopupMenuItem(),
                ft.PopupMenuItem(
                    text="Consulta Auto de Infração (Cobrança)",
                    on_click=lambda e: atualizar_conteudo("SIOR_Consulta_Cobranca"),
                    checked=False
                ),
                ft.PopupMenuItem(),
                ft.PopupMenuItem(
                    text="Download Relatórios",
                    on_click=lambda e: atualizar_conteudo("SIOR_Download"),
                    checked=False
                ),
                ft.PopupMenuItem(),
                ft.PopupMenuItem(
                    text="Painel Supervisor",
                    on_click=lambda e: atualizar_conteudo("SIOR_Consulta_Painel_Super"),
                    checked=False
                ),

            ]
        ),
        ft.PopupMenuButton(
            content=ft.Text("Sapiens"),
            tooltip="",
            menu_padding=0,
            menu_position=ft.PopupMenuPosition.UNDER,
            items=[
                ft.PopupMenuItem(
                    text="Consulta Créditos",
                    on_click=lambda e: atualizar_conteudo("Sapiens_Consulta"),
                    checked=False
                ),
                ft.PopupMenuItem(),
                ft.PopupMenuItem(
                    text="Download P.A's",
                    on_click=lambda e: atualizar_conteudo("Sapiens_Copia_Pa"),
                    checked=False
                ),

            ]
        ),
        ft.PopupMenuButton(
            content=ft.Text("Ajuda"),
            tooltip="",
            menu_padding=0,
            menu_position=ft.PopupMenuPosition.UNDER,
            items=[
                ft.PopupMenuItem(
                    text="Sobre",
                    on_click=lambda e: atualizar_conteudo("Sobre"),
                    checked=False
                )
            ]
        )
    ])

    # Conteúdo inicial padrão
    atualizar_conteudo("Inicio")

    layout = ft.Column([
        cabecalho,
        menu,
        ft.Divider(),
        conteudo_abas
    ], expand=True)

    page.add(layout)


if __name__ == "__main__":
    ft.app(target=main)
