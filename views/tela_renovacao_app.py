# ==========================================================
# VIEW - TELA DE RENOVAÇÃO DA APLICAÇÃO
# ==========================================================
import config

from core.licenca_app import (
    verificar_acesso_aplicacao,
    validar_senha_renovacao,
)


def _fechar_page(page):
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


def exigir_renovacao_antes_de_abrir(ft, page, montar_aplicacao_callback):
    """
    Deve ser chamada no começo do main(page), antes da montagem do menu.

    Se a licença estiver válida:
        monta a aplicação normalmente.

    Se precisar renovar:
        exibe tela de senha.

    Se houver bloqueio:
        exibe tela de bloqueio.
    """

    resultado = verificar_acesso_aplicacao()

    if resultado.liberado:
        montar_aplicacao_callback()
        return

    try:
        page.controls.clear()
    except Exception:
        pass

    page.title = getattr(config, "APP_TITLE", "RPA Search Data")
    page.window_width = getattr(config, "WINDOW_WIDTH", 1200)
    page.window_height = getattr(config, "WINDOW_HEIGHT", 900)
    page.padding = 30
    page.theme_mode = "light"
    page.scroll = "AUTO"

    txt_status = ft.Text(
        value=resultado.mensagem,
        size=12,
        color=ft.Colors.RED_700,
        selectable=True,
    )

    txt_machine = ft.Text(
        value=f"Machine ID: {resultado.machine_id[:16]}",
        size=11,
        color=ft.Colors.GREY_600,
        selectable=True,
    )

    input_senha = ft.TextField(
        label="Senha de renovação mensal",
        password=True,
        can_reveal_password=True,
        width=420,
        visible=resultado.requer_senha,
    )

    btn_validar = ft.ElevatedButton(
        text="Validar e abrir aplicação",
        icon=ft.Icons.LOCK_OPEN,
        bgcolor=ft.Colors.GREEN,
        color=ft.Colors.WHITE,
        visible=resultado.requer_senha,
    )

    btn_tentar_novamente = ft.ElevatedButton(
        text="Tentar novamente",
        icon=ft.Icons.REFRESH,
    )

    btn_sair = ft.ElevatedButton(
        text="Fechar",
        icon=ft.Icons.CLOSE,
        bgcolor=ft.Colors.RED_600,
        color=ft.Colors.WHITE,
    )

    progress = ft.ProgressBar(
        width=420,
        visible=False,
    )

    def liberar_aplicacao():
        try:
            page.controls.clear()
            page.update()
        except Exception:
            pass

        montar_aplicacao_callback()

    def validar(e=None):
        senha = str(input_senha.value or "").strip()

        if not senha:
            txt_status.value = "Informe a senha de renovação mensal."
            txt_status.color = ft.Colors.RED_700
            page.update()
            return

        btn_validar.disabled = True
        progress.visible = True
        txt_status.value = "Validando licença..."
        txt_status.color = ft.Colors.BLUE_700
        page.update()

        validacao = validar_senha_renovacao(
            senha=senha,
            politica=resultado.politica,
        )

        if validacao.liberado:
            txt_status.value = "Licença validada. Abrindo aplicação..."
            txt_status.color = ft.Colors.GREEN_700
            page.update()
            liberar_aplicacao()
            return

        txt_status.value = validacao.mensagem
        txt_status.color = ft.Colors.RED_700
        btn_validar.disabled = False
        progress.visible = False
        page.update()

    def tentar_novamente(e=None):
        exigir_renovacao_antes_de_abrir(
            ft=ft,
            page=page,
            montar_aplicacao_callback=montar_aplicacao_callback,
        )

    input_senha.on_submit = validar
    btn_validar.on_click = validar
    btn_tentar_novamente.on_click = tentar_novamente
    btn_sair.on_click = lambda e: _fechar_page(page)

    card = ft.Container(
        content=ft.Column(
            controls=[
                ft.Icon(
                    ft.Icons.ADMIN_PANEL_SETTINGS,
                    size=54,
                    color=ft.Colors.BLUE_700,
                ),
                ft.Text(
                    "Renovação da aplicação",
                    size=22,
                    weight="bold",
                ),
                ft.Text(
                    f"Perfil: {getattr(config, 'APP_PROFILE', '')}",
                    size=12,
                    weight="bold",
                    color=ft.Colors.GREY_700,
                ),
                ft.Text(
                    resultado.titulo or "Verificação de licença",
                    size=16,
                    weight="bold",
                    color=ft.Colors.RED_700 if not resultado.requer_senha else ft.Colors.BLUE_700,
                ),
                txt_status,
                txt_machine,
                ft.Divider(),
                input_senha,
                progress,
                ft.Row(
                    controls=[
                        btn_validar,
                        btn_tentar_novamente,
                        btn_sair,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    wrap=True,
                ),
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=620,
        padding=30,
        border_radius=15,
        border=ft.border.all(1, ft.Colors.GREY_400),
        bgcolor=ft.Colors.with_opacity(
            0.04,
            ft.Colors.ON_SURFACE,
        ),
    )

    page.add(
        ft.Column(
            controls=[
                ft.Container(height=60),
                ft.Row(
                    controls=[card],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )

    page.update()