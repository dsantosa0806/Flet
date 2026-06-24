import flet as ft
from views.aba_consulta_sapiens_divida import aba_consulta_sapiens
from views.aba_consulta_sior import aba_consulta
from views.aba_consulta_sior_cobranca import aba_consulta_auto_cobranca
from views.aba_consulta_sior_painel_supervisor import aba_consulta_sior_painel_supervisor
from views.aba_consulta_sior_placa import aba_consulta_sior_placa
from views.aba_consulta_sior_proprietario import aba_consulta_sior_proprietario
from views.aba_download import aba_download
from views.aba_sobre import aba_sobre
from views.popup_login_sior_manual import aba_login_manual_sior
from config import DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, WINDOW_WIDTH, WINDOW_HEIGHT, APP_TITLE, IS_ADMIN, APP_PROFILE
from views.aba_inicial import aba_inicial
from views.aba_consulta_sior_cobranca_devedor import aba_consulta_auto_cobranca_devedor
from views.aba_copia_pa import aba_copia_pa
from views.aba_consulta_cadin import aba_consulta_cadin
from utils.expiry_login import obter_texto_expiracoes_login
from navegador.sior_selenium_execution import finalizar_navegadores_sior_imediato
import threading
from utils.popups import mostrar_alerta
from core.auth import obter_perfil_aplicacao
from core.permissoes import Recurso, tem_permissao
from views.admin.aba_admin_varredura_sior import aba_admin_varredura_sior
from views.admin.aba_admin_sapiens_tarefas import aba_admin_sapiens_tarefas
from views.admin.aba_admin_sapiens_extintos_pagamento import (
    aba_admin_sapiens_extintos_pagamento
)
from views.admin.aba_admin_sior_suspensao import aba_admin_sior_suspensao
from views.admin.aba_admin_sior_reativacao import aba_admin_sior_reativacao
from views.admin.aba_admin_sior_registro_pagamento import aba_admin_sior_registro_pagamento
from views.admin.aba_admin_sior_varredura_encaminhamento import (
    aba_admin_sior_varredura_encaminhamento
)
from views.admin.aba_admin_sior_encaminhar_devedores import (
    aba_admin_sior_encaminhar_devedores
)
from views.admin.aba_admin_sapiens_tarefas_em_aberto_setor import (
    aba_admin_sapiens_tarefas_em_aberto_setor
)
from views.admin.aba_admin_sapiens_creditos_suspensos_parcelamento import (
    aba_admin_sapiens_creditos_suspensos_parcelamento
)
from views.aba_sior_distribuicao_processos import aba_sior_distribuicao_processos
from views.admin.aba_admin_sior_recuperacao_pfe import (
    aba_admin_sior_recuperacao_pfe)


def construir_cabecalho(toggle_switch):
    return ft.Row([
        ft.Text(APP_TITLE, size=HEADING_FONT_SIZE, weight="bold"),
        toggle_switch
    ])


def main(page: ft.Page):
    perfil_atual = obter_perfil_aplicacao()

    def acesso_negado():
        return ft.Column(
            [
                ft.Icon(ft.Icons.LOCK_OUTLINE, size=48, color=ft.Colors.RED_400),
                ft.Text(
                    "Acesso não autorizado",
                    size=HEADING_FONT_SIZE,
                    weight="bold",
                    color=ft.Colors.RED_400
                ),
                ft.Text(
                    "Seu perfil não possui permissão para acessar esta funcionalidade.",
                    size=DEFAULT_FONT_SIZE
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True
        )

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

    # =========================================================
    # ALTERNÂNCIA DE TEMA
    # =========================================================

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

    txt_expiracao_login = ft.Text(
        value=obter_texto_expiracoes_login(),
        size=10,
        italic=True,
        color=ft.Colors.GREY_400,
        selectable=True
    )

    txt_perfil = ft.Container(
        content=ft.Text(
            f"Perfil: {APP_PROFILE}",
            size=10,
            weight="bold",
            color="white"
        ),
        bgcolor=ft.Colors.RED_600 if IS_ADMIN else ft.Colors.BLUE_600,
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=20
    )

    cabecalho = ft.Row([
        ft.Text(APP_TITLE, size=HEADING_FONT_SIZE, weight="bold"),
        txt_perfil,
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

    # =========================================================
    # CALLBACK PARA MUDAR CONTEÚDO
    # =========================================================

    def atualizar_conteudo(opcao: str):
        if bloqueio_navegacao.current:
            page.snack_bar = ft.SnackBar(
                ft.Text("⚠ Aguarde a finalização do processo atual antes de trocar de aba."),
                bgcolor=ft.Colors.AMBER
            )
            page.snack_bar.open = True
            page.update()
            return

        try:
            recurso = Recurso(opcao)
        except ValueError:
            recurso = None

        if recurso and not tem_permissao(perfil_atual, recurso):
            conteudo_abas.content = acesso_negado()
            page.snack_bar = ft.SnackBar(
                ft.Text("🔒 Acesso restrito ao perfil administrador."),
                bgcolor=ft.Colors.RED_400
            )
            page.snack_bar.open = True
            page.update()
            return

        match opcao:
            case "ADMIN_Varredura_SIOR":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_varredura_sior(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_Sapiens_Tarefas":
                conteudo_abas.content = aba_admin_sapiens_tarefas(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_Sapiens_Extintos_Pagamento":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_sapiens_extintos_pagamento(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_SIOR_Suspensao":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_sior_suspensao(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_SIOR_Reativacao":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_sior_reativacao(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_SIOR_Registro_Pagamento":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_sior_registro_pagamento(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_SIOR_Varredura_Encaminhamento":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_sior_varredura_encaminhamento(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_SIOR_Encaminhar_Devedores":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_sior_encaminhar_devedores(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_SIOR_Recuperacao_PFE":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_sior_recuperacao_pfe(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_Sapiens_Tarefas_Em_Aberto_Setor":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_sapiens_tarefas_em_aberto_setor(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "ADMIN_Sapiens_Creditos_Suspensos_Parcelamento":
                if not IS_ADMIN:
                    conteudo_abas.content = acesso_negado()
                    page.snack_bar = ft.SnackBar(
                        ft.Text("🔒 Acesso restrito ao administrador."),
                        bgcolor=ft.Colors.RED_400
                    )
                    page.snack_bar.open = True
                    page.update()
                    return

                conteudo_abas.content = aba_admin_sapiens_creditos_suspensos_parcelamento(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "SIOR_Distribuicao_Processos":
                conteudo_abas.content = aba_sior_distribuicao_processos(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "SIOR_Consulta":
                conteudo_abas.content = aba_consulta(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "SIOR_Proprietario":
                conteudo_abas.content = aba_consulta_sior_proprietario(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page,
                    bloquear,
                    desbloquear
                )

            case "SIOR_Placa":
                conteudo_abas.content = aba_consulta_sior_placa(
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

            case "Login Manual SIOR":
                conteudo_abas.content = aba_login_manual_sior(
                    ft,
                    DEFAULT_FONT_SIZE,
                    HEADING_FONT_SIZE,
                    page
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

            case "SIOR_Consulta_Cobranca_Devedor":
                conteudo_abas.content = aba_consulta_auto_cobranca_devedor(
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

            case _:
                page.snack_bar = ft.SnackBar(
                    ft.Text(f"⚠ Opção de menu não encontrada: {opcao}"),
                    bgcolor=ft.Colors.RED_400
                )
                page.snack_bar.open = True

        txt_expiracao_login.value = obter_texto_expiracoes_login()
        page.update()

    # =========================================================
    # MENU PRINCIPAL COM SUBMENUS E ÍCONES SIMPLES
    # =========================================================

    # =========================================================
    # MENU PRINCIPAL COM SUBMENUS E ÍCONES SIMPLES
    # =========================================================

    def texto_menu_principal(texto: str):
        return ft.Container(
            content=ft.Text(
                texto,
                weight="bold",
                no_wrap=True
            ),
            padding=ft.padding.symmetric(
                horizontal=4,
                vertical=2
            )
        )

    def texto_item_menu(texto: str, largura: int = 250):
        return ft.Container(
            content=ft.Text(
                texto,
                no_wrap=True,
                overflow=ft.TextOverflow.VISIBLE
            ),
            width=largura,
            padding=ft.padding.symmetric(
                horizontal=2,
                vertical=2
            )
        )

    def somente_permitidos(controles):
        """
        Remove itens None da lista de controles.

        Hoje todos os menus são de acesso geral.
        No futuro, quando houver módulos restritos,
        o item_menu poderá retornar None para esconder
        opções não permitidas.
        """
        return [
            controle
            for controle in controles
            if controle is not None
        ]

    def item_menu(
            texto: str,
            icone,
            destino: str,
            largura: int = 250,
            permitido: bool = True
    ):
        """
        Cria um item de menu.

        Parâmetro permitido:
        - True: exibe o item normalmente.
        - False: retorna None e o item será removido
          pelo somente_permitidos().
        """

        if not permitido:
            return None

        return ft.MenuItemButton(
            leading=ft.Icon(
                icone,
                size=18
            ),
            content=texto_item_menu(
                texto,
                largura
            ),
            on_click=lambda e: atualizar_conteudo(
                destino
            )
        )

    def submenu_menu(
            texto: str,
            icone,
            controles,
            largura: int = 250
    ):
        """
        Cria um submenu com ícone e seta lateral.
        """

        controles = somente_permitidos(controles)

        if not controles:
            return None

        return ft.SubmenuButton(
            content=ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            icone,
                            size=18
                        ),
                        ft.Text(
                            texto,
                            no_wrap=True
                        ),
                        ft.Container(
                            expand=True
                        ),
                        ft.Icon(
                            ft.Icons.CHEVRON_RIGHT,
                            size=18
                        ),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                width=largura,
                padding=ft.padding.symmetric(
                    horizontal=2,
                    vertical=2
                )
            ),
            controls=controles
        )

    # =========================================================
    # HOME
    # =========================================================
    menu_admin = None

    if IS_ADMIN:
        def texto_submenu_admin(titulo, icone):
            return ft.Row(
                controls=[
                    ft.Icon(
                        icone,
                        size=18
                    ),
                    ft.Text(
                        titulo,
                        size=DEFAULT_FONT_SIZE,
                        weight="bold"
                    )
                ],
                spacing=8
            )

        menu_admin = ft.SubmenuButton(
            content=texto_menu_principal("Admin"),
            controls=somente_permitidos([

                # ==================================================
                # SUBMENU ADMIN > SIOR
                # ==================================================
                ft.SubmenuButton(
                    content=texto_submenu_admin(
                        "SIOR",
                        ft.Icons.HUB_OUTLINED
                    ),
                    controls=somente_permitidos([

                        item_menu(
                            "Varredura - Cadastro Dívida",
                            ft.Icons.ADMIN_PANEL_SETTINGS,
                            "ADMIN_Varredura_SIOR",
                            largura=280,
                            permitido=True
                        ),

                        item_menu(
                            "Suspensão - Cobrança",
                            ft.Icons.PAUSE_CIRCLE_OUTLINE,
                            "ADMIN_SIOR_Suspensao",
                            largura=280,
                            permitido=True
                        ),

                        item_menu(
                            "Reativação - Cobrança",
                            ft.Icons.RESTART_ALT,
                            "ADMIN_SIOR_Reativacao",
                            largura=280,
                            permitido=True
                        ),

                        item_menu(
                            "Registro de Pagamento",
                            ft.Icons.PAYMENT,
                            "ADMIN_SIOR_Registro_Pagamento",
                            largura=280,
                            permitido=True
                        ),

                        item_menu(
                            "Varredura SIOR - Encaminhamento",
                            ft.Icons.DASHBOARD_OUTLINED,
                            "ADMIN_SIOR_Varredura_Encaminhamento",
                            largura=280,
                            permitido=True
                        ),

                        item_menu(
                            "Encaminhar Devedores SIOR",
                            ft.Icons.SEND,
                            "ADMIN_SIOR_Encaminhar_Devedores",
                            largura=280,
                            permitido=True
                        ),

                        item_menu(
                            "Análise Recuperação Créditos PFE",
                            ft.Icons.INSIGHTS_OUTLINED,
                            "ADMIN_SIOR_Recuperacao_PFE",
                            largura=330,
                            permitido=True
                        ),
                    ])
                ),

                # ==================================================
                # SUBMENU ADMIN > SAPIENS
                # ==================================================
                ft.SubmenuButton(
                    content=texto_submenu_admin(
                        "Sapiens",
                        ft.Icons.ACCOUNT_TREE_OUTLINED
                    ),
                    controls=somente_permitidos([

                        item_menu(
                            "Relatórios de Tarefas",
                            ft.Icons.ASSIGNMENT_OUTLINED,
                            "ADMIN_Sapiens_Tarefas",
                            largura=280,
                            permitido=True
                        ),

                        item_menu(
                            "Extintos por Pagamento",
                            ft.Icons.MONETIZATION_ON_OUTLINED,
                            "ADMIN_Sapiens_Extintos_Pagamento",
                            largura=300,
                            permitido=True
                        ),

                        item_menu(
                            "Sapiens - Tarefas em Aberto Setor",
                            ft.Icons.PENDING_ACTIONS_OUTLINED,
                            "ADMIN_Sapiens_Tarefas_Em_Aberto_Setor",
                            largura=330,
                            permitido=True
                        ),

                        item_menu(
                            "Créditos Suspensos por Parcelamento",
                            ft.Icons.PAUSE_CIRCLE_OUTLINE,
                            "ADMIN_Sapiens_Creditos_Suspensos_Parcelamento",
                            largura=360,
                            permitido=True
                        ),
                    ])
                ),
            ])
        )

    menu_home = ft.SubmenuButton(
        content=texto_menu_principal("Home"),
        controls=somente_permitidos([
            item_menu(
                "Início",
                ft.Icons.FACT_CHECK_OUTLINED,
                "Inicio",
                largura=240
            ),
        ])
    )

    # =========================================================
    # SIOR
    # =========================================================

    menu_sior = ft.SubmenuButton(
        content=texto_menu_principal("SIOR"),
        controls=somente_permitidos([

            submenu_menu(
                "Consulta",
                ft.Icons.SEARCH,
                somente_permitidos([
                    item_menu(
                        "Auto de Infração",
                        ft.Icons.DESCRIPTION_OUTLINED,
                        "SIOR_Consulta",
                        largura=260
                    ),

                    item_menu(
                        "Proprietário",
                        ft.Icons.PERSON_SEARCH_OUTLINED,
                        "SIOR_Proprietario",
                        largura=260
                    ),

                    item_menu(
                        "Placa",
                        ft.Icons.DIRECTIONS_CAR_OUTLINED,
                        "SIOR_Placa",
                        largura=260
                    ),

                    item_menu(
                        "Auto de Infração Cobrança",
                        ft.Icons.REQUEST_QUOTE,
                        "SIOR_Consulta_Cobranca",
                        largura=260
                    ),

                    item_menu(
                        "Devedor em Cobrança",
                        ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED,
                        "SIOR_Consulta_Cobranca_Devedor",
                        largura=260
                    ),

                    item_menu(
                        "Acompanhamento Painel Supervisor",
                        ft.Icons.DASHBOARD_OUTLINED,
                        "SIOR_Consulta_Painel_Super",
                        largura=260
                    ),

                ]),
                largura=240
            ),

            item_menu(
                "Distribuição de Processos",
                ft.Icons.ACCOUNT_TREE_OUTLINED,
                "SIOR_Distribuicao_Processos",
                largura=280,
                permitido=True
            ),

            item_menu(
                "Download Relatórios",
                ft.Icons.DOWNLOAD,
                "SIOR_Download",
                largura=240
            ),

            item_menu(
                "Login Manual SIOR",
                ft.Icons.LOGIN,
                "Login Manual SIOR",
                largura=240
            ),
        ])
    )

    # =========================================================
    # SAPIENS
    # =========================================================

    menu_sapiens = ft.SubmenuButton(
        content=texto_menu_principal("Sapiens"),
        controls=somente_permitidos([
            item_menu(
                "Consulta Créditos",
                ft.Icons.MONETIZATION_ON_OUTLINED,
                "Sapiens_Consulta",
                largura=240
            ),
            item_menu(
                "Relatórios de Tarefas",
                ft.Icons.ASSIGNMENT_OUTLINED,
                "ADMIN_Sapiens_Tarefas",
                largura=280,
                permitido=True
            ),

            # Caso queira reativar futuramente:
            # item_menu(
            #     "Download P.A's",
            #     ft.Icons.FOLDER_COPY_OUTLINED,
            #     "Sapiens_Copia_Pa",
            #     largura=240
            # ),
        ])
    )

    # =========================================================
    # CADIN
    # =========================================================

    menu_cadin = ft.SubmenuButton(
        content=texto_menu_principal("CADIN"),
        controls=somente_permitidos([
            item_menu(
                "Consulta CADIN",
                ft.Icons.FACT_CHECK_OUTLINED,
                "CADIN_Consulta",
                largura=240
            ),
        ])
    )

    # =========================================================
    # AJUDA
    # =========================================================

    menu_ajuda = ft.SubmenuButton(
        content=texto_menu_principal("Ajuda"),
        controls=somente_permitidos([
            item_menu(
                "Sobre",
                ft.Icons.INFO_OUTLINE,
                "Sobre",
                largura=240
            ),

            item_menu(
                "Login Manual SIOR",
                ft.Icons.LOGIN,
                "Login Manual SIOR",
                largura=240
            ),
        ])
    )

    # =========================================================
    # MENU FINAL
    # =========================================================

    menu = ft.MenuBar(
        controls=somente_permitidos([
            menu_admin,
            menu_home,
            menu_sior,
            menu_sapiens,
            menu_cadin,
            menu_ajuda,
        ])
    )

    # =========================================================
    # CONTEÚDO INICIAL PADRÃO
    # =========================================================

    atualizar_conteudo("Inicio")

    layout = ft.Column([
        cabecalho,
        menu,
        ft.Divider(),
        conteudo_abas,
        dialogo_versao
    ], expand=True)

    page.add(layout)

