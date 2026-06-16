import flet as ft
from views.aba_consulta_sapiens_divida import aba_consulta_sapiens
from views.aba_consulta_sior import aba_consulta
from views.aba_consulta_sior_painel_supervisor import aba_consulta_sior_painel_supervisor
from views.aba_download import aba_download
from views.aba_sobre import aba_sobre
from config import DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, WINDOW_WIDTH, WINDOW_HEIGHT, APP_TITLE
from views.aba_inicial import aba_inicial
from views.aba_consulta_sior_cobranca import aba_consulta_auto_cobranca
from views.aba_copia_pa import aba_copia_pa
from views.aba_consulta_cadin import aba_consulta_cadin
from utils.expiry_login import obter_texto_expiracoes_login
from navegador.sior_selenium_execution import finalizar_navegadores_sior_imediato
import threading
from utils.popups import mostrar_alerta


def construir_cabecalho(toggle_switch):
    return ft.Row([
        ft.Text(APP_TITLE, size=HEADING_FONT_SIZE, weight="bold"),
        toggle_switch
    ])


def main(page: ft.Page):
    bloqueio_navegacao = ft.Ref[bool]()
    bloqueio_navegacao.current = False
    fechando_aplicacao = ft.Ref[bool]()
    fechando_aplicacao.current = False

    dialogo_versao = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[],
        open=False
    )

    page.dialog = dialogo_versao
    page.title = APP_TITLE
    page.window_width = WINDOW_WIDTH
    page.window_height = WINDOW_HEIGHT
    page.scroll = "AUTO"
    page.padding = 25
    page.theme_mode = "light"
    page.window_resizable = True
    page.window_prevent_close = False

    # =========================================================
    # FECHAMENTO SEGURO DA APLICAÇÃO
    # =========================================================

    def ao_fechar_app(e):
        evento = getattr(e, "data", "")

        if evento not in ("close", "closing"):
            return

        # Evita executar o fechamento mais de uma vez
        if fechando_aplicacao.current:
            return

        fechando_aplicacao.current = True
        bloqueio_navegacao.current = True

        try:
            mostrar_alerta(
                ft,
                page,
                "Aplicação em encerramento",
                "Estamos fechando a aplicação. Aguarde um instante...",
                tipo="info",
                duracao=0.6
            )
        except Exception as ex:
            print(f"Erro ao exibir popup de encerramento: {ex}")

        def fechar_definitivamente():
            try:
                finalizar_navegadores_sior_imediato()
            except Exception as ex:
                print(f"Erro ao disparar fechamento imediato SIOR: {ex}")

            try:
                page.window_prevent_close = False
            except Exception:
                pass

            try:
                page.window.prevent_close = False
            except Exception:
                pass

            try:
                page.window_destroy()
                return
            except Exception:
                pass

            try:
                page.window.destroy()
                return
            except Exception:
                pass

        timer = threading.Timer(0.7, fechar_definitivamente)
        timer.daemon = True
        timer.start()

    # Compatibilidade com versões antigas do Flet
    try:
        page.window_prevent_close = True
        page.on_window_event = ao_fechar_app
    except Exception:
        pass

    # Compatibilidade com versões mais recentes do Flet
    try:
        page.window.prevent_close = True
        page.window.on_event = ao_fechar_app
    except Exception:
        pass

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

    # Informação simples de expiração dos logins
    txt_expiracao_login = ft.Text(
        value=obter_texto_expiracoes_login(),
        size=10,
        italic=True,
        color=ft.Colors.GREY_400,
        selectable=True
    )

    # Cabeçalho com título, expiração de login e botão de tema
    cabecalho = ft.Row([
        ft.Text(APP_TITLE, size=HEADING_FONT_SIZE, weight="bold"),
        ft.Container(expand=True),
        txt_expiracao_login,
        toggle_switch
    ])

    conteudo_abas = ft.Container(expand=True)

    def bloquear():
        bloqueio_navegacao.current = True

    def desbloquear():
        bloqueio_navegacao.current = False
        txt_expiracao_login.value = obter_texto_expiracoes_login()

    # Callback para mudar conteúdo
    def atualizar_conteudo(opcao: str):
        if bloqueio_navegacao.current:
            page.snack_bar = ft.SnackBar(
                ft.Text("⚠ Aguarde a finalização do processo atual antes de trocar de aba."),
                bgcolor=ft.Colors.AMBER
            )
            page.snack_bar.open = True
            page.update()
            return

        match opcao:
            case "SIOR_Consulta":
                conteudo_abas.content = aba_consulta(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "SIOR_Download":
                conteudo_abas.content = aba_download(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "Sapiens_Consulta":
                conteudo_abas.content = aba_consulta_sapiens(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "Sapiens_Copia_Pa":
                conteudo_abas.content = aba_copia_pa(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "Sobre":
                conteudo_abas.content = aba_sobre(
                    ft,
                    HEADING_FONT_SIZE,
                    DEFAULT_FONT_SIZE
                )

            case "Inicio":
                conteudo_abas.content = aba_inicial(
                    ft,
                    HEADING_FONT_SIZE,
                    DEFAULT_FONT_SIZE,
                    page
                )

            case "SIOR_Consulta_Cobranca":
                conteudo_abas.content = aba_consulta_auto_cobranca(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "SIOR_Consulta_Painel_Super":
                conteudo_abas.content = aba_consulta_sior_painel_supervisor(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "CADIN_Consulta":
                conteudo_abas.content = aba_consulta_cadin(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page
                )

        txt_expiracao_login.value = obter_texto_expiracoes_login()
        page.update()

    # Menu principal e submenu
    menu = ft.Row([

        ft.PopupMenuButton(
            content=ft.Text("SIOR"),
            tooltip="",
            menu_padding=0,
            menu_position=ft.PopupMenuPosition.UNDER,
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
                # ft.PopupMenuItem(),
                # ft.PopupMenuItem(
                #     text="Download P.A's",
                #     on_click=lambda e: atualizar_conteudo("Sapiens_Copia_Pa"),
                #     checked=False
                # ),
            ]
        ),

        ft.PopupMenuButton(
            content=ft.Text("CADIN"),
            tooltip="",
            menu_padding=0,
            menu_position=ft.PopupMenuPosition.UNDER,
            items=[
                ft.PopupMenuItem(
                    text="Consulta CADIN",
                    on_click=lambda e: atualizar_conteudo("CADIN_Consulta"),
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
        conteudo_abas,
        dialogo_versao
    ], expand=True)

    page.add(layout)


if __name__ == "__main__":
    ft.app(target=main)