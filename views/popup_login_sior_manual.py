import os
import json
from datetime import datetime, timezone
import config
from utils.locate_files_instalador import caminho_recurso

# =========================================================
# CONFIGURAÇÕES DO COOKIES.JSON DO SIOR
# =========================================================

SIOR_COOKIES_DIR = getattr(
    config,
    "SIOR_COOKIES_DIR",
    os.getenv("SIOR_COOKIES_DIR", r"C:\Cookies-Selenium")
)

SIOR_COOKIES_FILE = getattr(
    config,
    "SIOR_COOKIES_FILE",
    os.getenv("SIOR_COOKIES_FILE", "cookies.json")
)


def _cookies_path():
    return os.path.join(SIOR_COOKIES_DIR, SIOR_COOKIES_FILE)


def _garantir_pasta_cookies():
    os.makedirs(SIOR_COOKIES_DIR, exist_ok=True)


# =========================================================
# HELPERS DE DIALOG
# =========================================================

def _abrir_dialogo(page, dialog):
    """
    Abre AlertDialog de forma compatível com versões novas e antigas do Flet.
    """

    try:
        # Flet mais recente
        page.open(dialog)
        return
    except Exception:
        pass

    try:
        # Flet tradicional
        page.dialog = dialog
        dialog.open = True
        page.update()
        return
    except Exception:
        pass

    try:
        # Fallback via overlay
        if dialog not in page.overlay:
            page.overlay.append(dialog)

        dialog.open = True
        page.update()
    except Exception as ex:
        print(f"Erro ao abrir diálogo: {ex}")


def _fechar_dialogo(page, dialog=None):
    """
    Fecha AlertDialog de forma compatível com versões novas e antigas do Flet.
    """

    try:
        if dialog:
            page.close(dialog)
            return
    except Exception:
        pass

    try:
        if dialog:
            dialog.open = False
        elif page.dialog:
            page.dialog.open = False

        page.update()
    except Exception:
        pass


# =========================================================
# VALIDAÇÕES E SALVAMENTO
# =========================================================
def converter_expiry_para_timestamp(expiry_value):
    """
    Converte o valor de expiry informado pelo usuário para timestamp Unix.

    Aceita:
    - Timestamp Unix em segundos: 1781637387
    - Data ISO do navegador: 2026-06-16T23:49:48.806Z
    - Data ISO sem milissegundos: 2026-06-16T23:49:48Z

    Retorna:
    - int timestamp Unix
    """

    expiry_value = str(expiry_value or "").strip()

    if not expiry_value:
        raise ValueError("Expiry não informado.")

    # Caso já venha como timestamp
    if expiry_value.isdigit():
        return int(expiry_value)

    try:
        # O navegador geralmente retorna com Z, indicando UTC
        # Ex: 2026-06-16T23:49:48.806Z
        if expiry_value.endswith("Z"):
            expiry_value = expiry_value.replace("Z", "+00:00")

        expiry_datetime = datetime.fromisoformat(expiry_value)

        # Se vier sem timezone, assume UTC
        if expiry_datetime.tzinfo is None:
            expiry_datetime = expiry_datetime.replace(tzinfo=timezone.utc)

        return int(expiry_datetime.timestamp())

    except Exception:
        raise ValueError(
            "Formato de expiry inválido. Use o formato "
            "2026-06-16T23:49:48.806Z ou um timestamp Unix."
        )


def _validar_campos(session_id_value, sior_auth_expiry, sior_auth_value):
    session_id_value = str(session_id_value or "").strip()
    sior_auth_expiry = str(sior_auth_expiry or "").strip()
    sior_auth_value = str(sior_auth_value or "").strip()

    if not session_id_value:
        return False, "Informe o value do cookie ASP.NET_SessionId."

    if not sior_auth_expiry:
        return False, "Informe o expiry do cookie .SIOR_AUTH_prod_v2."

    try:
        expiry_int = converter_expiry_para_timestamp(sior_auth_expiry)
    except Exception as ex:
        return False, str(ex)

    agora_epoch = int(datetime.now(timezone.utc).timestamp())

    if expiry_int <= agora_epoch:
        return False, "O expiry informado já está expirado. Gere novos cookies antes de salvar."

    if not sior_auth_value:
        return False, "Informe o value do cookie .SIOR_AUTH_prod_v2."

    return True, ""


def salvar_cookies_sior_manual(session_id_value, sior_auth_expiry, sior_auth_value):
    """
    Salva manualmente o cookies.json do SIOR com os cookies necessários:
    - ASP.NET_SessionId
    - .SIOR_AUTH_prod_v2

    O expiry pode ser informado como:
    - timestamp Unix
    - data ISO do navegador: 2026-06-16T23:49:48.806Z
    """

    session_id_value = str(session_id_value or "").strip()
    sior_auth_expiry = converter_expiry_para_timestamp(sior_auth_expiry)
    sior_auth_value = str(sior_auth_value or "").strip()

    _garantir_pasta_cookies()

    cookies = [
        {
            "domain": "servicos.dnit.gov.br",
            "httpOnly": True,
            "name": "ASP.NET_SessionId",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": session_id_value
        },
        {
            "domain": "servicos.dnit.gov.br",
            "expiry": sior_auth_expiry,
            "httpOnly": True,
            "name": ".SIOR_AUTH_prod_v2",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": sior_auth_value
        }
    ]

    caminho = _cookies_path()

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(cookies, arquivo, ensure_ascii=False, indent=4)

    return caminho


# =========================================================
# COMPONENTES VISUAIS
# =========================================================

def _abrir_imagem_ampliada(ft, page, caminho_img, titulo="Imagem ampliada"):
    """
    Abre a imagem em um overlay grande, acima do popup principal,
    sem depender das limitações de tamanho do AlertDialog.
    """

    overlay_zoom = None

    def _num(valor, padrao):
        try:
            if valor is None:
                return padrao
            return int(valor)
        except Exception:
            return padrao

    largura_tela = _num(
        getattr(page, "width", None) or getattr(page, "window_width", None),
        1366
    )
    altura_tela = _num(
        getattr(page, "height", None) or getattr(page, "window_height", None),
        768
    )

    largura_modal = max(900, largura_tela - 50)
    altura_modal = max(620, altura_tela - 60)

    largura_imagem = largura_modal - 40
    altura_imagem = altura_modal - 125

    def fechar(e=None):
        try:
            if overlay_zoom in page.overlay:
                page.overlay.remove(overlay_zoom)
            page.update()
        except Exception as ex:
            print(f"Erro ao fechar imagem ampliada: {ex}")

    imagem = ft.Image(
        src=caminho_img,
        width=largura_imagem,
        height=altura_imagem,
        fit=ft.ImageFit.CONTAIN,
        border_radius=8
    )

    # Se a versão do Flet tiver InteractiveViewer, permite zoom com mouse/toque.
    try:
        imagem_visual = ft.InteractiveViewer(
            content=imagem,
            min_scale=1,
            max_scale=4
        )
    except Exception:
        imagem_visual = imagem

    overlay_zoom = ft.Container(
        width=largura_tela,
        height=altura_tela,
        bgcolor=ft.Colors.with_opacity(0.88, ft.Colors.BLACK),
        alignment=ft.alignment.center,
        padding=20,
        content=ft.Container(
            width=largura_modal,
            height=altura_modal,
            padding=12,
            border_radius=12,
            bgcolor=ft.Colors.GREY_900,
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                f"🖼️ {titulo}",
                                size=16,
                                weight="bold",
                                color=ft.Colors.WHITE
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE,
                                icon_color=ft.Colors.WHITE,
                                tooltip="Fechar imagem",
                                on_click=fechar
                            )
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),

                    ft.Text(
                        "Imagem ampliada. Use o zoom, se disponível, ou feche para retornar às instruções.",
                        size=11,
                        italic=True,
                        color=ft.Colors.GREY_300
                    ),

                    ft.Container(
                        content=imagem_visual,
                        alignment=ft.alignment.center,
                        expand=True,
                        border_radius=10,
                        border=ft.border.all(1, ft.Colors.GREY_700),
                        padding=5
                    )
                ],
                spacing=8,
                expand=True
            )
        )
    )

    try:
        page.overlay.append(overlay_zoom)
        page.update()
    except Exception as ex:
        print(f"Erro ao abrir imagem ampliada: {ex}")


def _criar_conteudo_imagem_ampliada(ft, caminho_img, titulo, on_voltar):
    """
    Cria o conteúdo ampliado da imagem dentro do próprio popup Login Manual SIOR.
    Não abre novo AlertDialog.

    Melhorias:
    - Evita criar novo modal por cima do popup principal.
    - Usa botões de zoom.
    - Usa InteractiveViewer quando disponível na versão do Flet.
    - Permite rolagem quando a imagem ficar maior que a área visível.
    """

    zoom = {"valor": 1.0}

    largura_base = 1080
    altura_base = 620

    txt_zoom = ft.Text(
        "100%",
        size=12,
        weight="bold"
    )

    imagem = ft.Image(
        src=caminho_img,
        width=largura_base,
        height=altura_base,
        fit=ft.ImageFit.CONTAIN,
        border_radius=8
    )

    def aplicar_zoom():
        try:
            imagem.width = int(largura_base * zoom["valor"])
            imagem.height = int(altura_base * zoom["valor"])
            txt_zoom.value = f"{int(zoom['valor'] * 100)}%"

            imagem.update()
            txt_zoom.update()

        except Exception as ex:
            print(f"Erro ao aplicar zoom na imagem: {ex}")

    def aumentar_zoom(e=None):
        zoom["valor"] = min(zoom["valor"] + 0.25, 4.0)
        aplicar_zoom()

    def reduzir_zoom(e=None):
        zoom["valor"] = max(zoom["valor"] - 0.25, 0.5)
        aplicar_zoom()

    def resetar_zoom(e=None):
        zoom["valor"] = 1.0
        aplicar_zoom()

    # Tenta usar InteractiveViewer, se existir na versão instalada do Flet.
    try:
        imagem_visual = ft.InteractiveViewer(
            content=imagem,
            min_scale=0.5,
            max_scale=4.0,
            pan_enabled=True,
            scale_enabled=True
        )
    except Exception:
        imagem_visual = imagem

    return ft.Container(
        width=1120,
        height=720,
        padding=10,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK,
                            tooltip="Voltar às instruções",
                            on_click=on_voltar
                        ),
                        ft.Text(
                            f"Visualização ampliada - {titulo}",
                            size=15,
                            weight="bold"
                        ),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.ZOOM_OUT,
                            tooltip="Reduzir zoom",
                            on_click=reduzir_zoom
                        ),
                        txt_zoom,
                        ft.IconButton(
                            icon=ft.Icons.ZOOM_IN,
                            tooltip="Aumentar zoom",
                            on_click=aumentar_zoom
                        ),
                        ft.TextButton(
                            "100%",
                            icon=ft.Icons.CENTER_FOCUS_STRONG,
                            on_click=resetar_zoom
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),

                ft.Text(
                    "Use os botões de zoom para ampliar a imagem. Clique em voltar para retornar ao formulário.",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600
                ),

                ft.Container(
                    expand=True,
                    padding=6,
                    border_radius=10,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    alignment=ft.alignment.center,
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    imagem_visual
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                scroll=ft.ScrollMode.AUTO
                            )
                        ],
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    )
                )
            ],
            spacing=8,
            expand=True
        )
    )


def _criar_area_imagens(ft, page, imagens=None, on_ampliar=None):
    """
    Cria miniaturas compactas dos prints de instrução.

    A ampliação não é modificada.
    Ao clicar em qualquer miniatura, mantém o fluxo atual via on_ampliar().
    """

    imagens = imagens or []
    controles = []

    tamanho_card = 118
    tamanho_imagem = 82

    if imagens:
        for idx, caminho_img in enumerate(imagens, start=1):
            titulo_img = f"Passo {idx}"

            def clicar_imagem(e, img=caminho_img, titulo=titulo_img):
                if callable(on_ampliar):
                    on_ampliar(img, titulo)

            controles.append(
                ft.Container(
                    width=tamanho_card,
                    height=tamanho_card,
                    padding=6,
                    border_radius=12,
                    ink=True,
                    tooltip=f"Clique para ampliar o {titulo_img}",
                    on_click=clicar_imagem,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    content=ft.Column(
                        [
                            ft.Container(
                                width=tamanho_imagem,
                                height=tamanho_imagem,
                                border_radius=10,
                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                content=ft.Image(
                                    src=caminho_img,
                                    width=tamanho_imagem,
                                    height=tamanho_imagem,
                                    fit=ft.ImageFit.COVER,
                                ),
                                alignment=ft.alignment.center,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.ZOOM_IN,
                                        size=13,
                                        color=ft.Colors.GREY_600
                                    ),
                                    ft.Text(
                                        titulo_img,
                                        size=10,
                                        weight="bold",
                                        color=ft.Colors.GREY_700
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=4
                            )
                        ],
                        spacing=5,
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    )
                )
            )

    else:
        for idx in range(1, 4):
            controles.append(
                ft.Container(
                    width=tamanho_card,
                    height=tamanho_card,
                    padding=8,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    alignment=ft.alignment.center,
                    content=ft.Column(
                        [
                            ft.Icon(
                                ft.Icons.IMAGE_OUTLINED,
                                size=28,
                                color=ft.Colors.GREY_500
                            ),
                            ft.Text(
                                f"Print {idx}",
                                size=10,
                                weight="bold",
                                text_align=ft.TextAlign.CENTER
                            ),
                            ft.Text(
                                "Não adicionado",
                                size=9,
                                italic=True,
                                color=ft.Colors.GREY_500,
                                text_align=ft.TextAlign.CENTER
                            )
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER
                    )
                )
            )

    return ft.Row(
        controles,
        spacing=10,
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER
    )


# =========================================================
# JANELA PRINCIPAL DE LOGIN MANUAL
# =========================================================

def abrir_janela_login_manual_sior(
        ft,
        page,
        imagens=None,
        on_cookie_salvo=None
):
    """
    Abre janela/modal para instruções e preenchimento manual dos cookies do SIOR.
    """
    dialog_manual = None
    conteudo_principal = None
    acoes_principais = None
    btn_cancelar = None

    def voltar_para_formulario(e=None):
        try:
            dialog_manual.title = ft.Text("🔐 Login manual SIOR")
            dialog_manual.content = conteudo_principal
            dialog_manual.actions = acoes_principais
            page.update()
        except Exception as ex:
            print(f"Erro ao voltar para formulário de login manual: {ex}")

    def ampliar_imagem(caminho_img, titulo):
        try:
            dialog_manual.title = ft.Text(f"🖼️ {titulo}")

            dialog_manual.content = _criar_conteudo_imagem_ampliada(
                ft,
                caminho_img,
                titulo,
                voltar_para_formulario
            )

            # Remove ações inferiores para ganhar mais espaço vertical.
            # O botão de voltar ficará dentro do próprio conteúdo ampliado.
            dialog_manual.actions = []

            page.update()

        except Exception as ex:
            print(f"Erro ao ampliar imagem: {ex}")

    input_session_id = ft.TextField(
        label="value do ASP.NET_SessionId",
        hint_text="Ex: 2nmn2g3fxiiylqzwlex0mli1",
        multiline=False,
        password=True,
        can_reveal_password=True,
        dense=True
    )

    input_sior_auth_expiry = ft.TextField(
        label="expiry do .SIOR_AUTH_prod_v2",
        hint_text="Ex: 2026-06-16T23:49:48.806Z ou 1781637387",
        multiline=False,
        dense=True
    )

    input_sior_auth_value = ft.TextField(
        label="value do .SIOR_AUTH_prod_v2",
        hint_text="Cole aqui o value completo do cookie .SIOR_AUTH_prod_v2",
        multiline=True,
        min_lines=3,
        max_lines=5,
        password=True,
        can_reveal_password=True
    )

    txt_status = ft.Text("", size=11, visible=False)

    dialog_manual = None

    def salvar(e):
        valido, mensagem = _validar_campos(
            input_session_id.value,
            input_sior_auth_expiry.value,
            input_sior_auth_value.value
        )

        if not valido:
            txt_status.value = f"⚠️ {mensagem}"
            txt_status.color = ft.Colors.ORANGE
            txt_status.visible = True
            page.update()
            return

        try:
            caminho = salvar_cookies_sior_manual(
                input_session_id.value,
                input_sior_auth_expiry.value,
                input_sior_auth_value.value
            )

            txt_status.value = "✅ Cookies salvos com sucesso."
            txt_status.color = ft.Colors.GREEN
            txt_status.visible = True

            try:
                btn_cancelar.text = "Fechar"
            except Exception:
                pass

            page.update()

            if callable(on_cookie_salvo):
                try:
                    on_cookie_salvo(caminho)
                except Exception:
                    pass

        except Exception as ex:
            txt_status.value = f"❌ Erro ao salvar cookies: {ex}"
            txt_status.color = ft.Colors.RED
            txt_status.visible = True
            page.update()

    def cancelar(e):
        _fechar_dialogo(page, dialog_manual)

    conteudo = ft.Container(
        width=1080,
        height=720,
        content=ft.Column(
            [
                ft.Divider(),
                ft.ExpansionTile(
                    title=ft.Text(
                        "Dados dos cookies",
                        size=13,
                        weight="bold"
                    ),
                    leading=ft.Icon(ft.Icons.COOKIE_OUTLINED),
                    initially_expanded=True,
                    controls=[
                        ft.Container(
                            content=ft.Column(
                                [
                                    input_session_id,
                                    input_sior_auth_expiry,
                                    input_sior_auth_value,
                                    txt_status,
                                ],
                                spacing=8
                            ),
                            padding=ft.padding.only(
                                left=12,
                                right=12,
                                bottom=10
                            )
                        )
                    ]
                ),

                ft.Divider(),

                ft.Text(
                    "Login manual no SIOR",
                    size=18,
                    weight="bold"
                ),
                ft.Text(
                    "Siga as etapas abaixo para gerar os cookies necessários e liberar a sessão do SIOR.",
                    size=12
                ),
                ft.Divider(),

                ft.Text("Etapas sugeridas", size=13, weight="bold"),
                ft.Text(
                    "1. Abra o SIOR no SEU navegador e realize o login normalmente pelo Gov.br. Utilize "
                    "preferencialmente o Chrome (Passo 1)",
                    size=11
                ),
                ft.Text(
                    spans=[
                        ft.TextSpan("2. Após concluir o login no SIOR, pressione "),
                        ft.TextSpan(
                            "F12",
                            style=ft.TextStyle(weight="bold")
                        ),
                        ft.TextSpan(" para abrir as "),
                        ft.TextSpan(
                            "Ferramentas do Desenvolvedor",
                            style=ft.TextStyle(weight="bold")
                        ),
                        ft.TextSpan(". Em seguida, acesse: "),
                        ft.TextSpan(
                            "Aplicativo/Application > Cookies > https://servicos.dnit.gov.br",
                            style=ft.TextStyle(weight="bold")
                        ),
                        ft.TextSpan(
                            ". Nessa área estarão disponíveis os cookies necessários para preencher os campos abaixo"
                            " (Passo 2)."
                        ),
                    ],
                    size=11
                ),
                ft.Text(
                    "3. Localize os cookies ASP.NET_SessionId e .SIOR_AUTH_prod_v2 (Passo 3).",
                    size=11
                ),
                ft.Text(
                    "4. Copie os campos solicitados abaixo exatamente como aparecem no navegador (Passo 3).",
                    size=11
                ),
                ft.Text(
                    "5. Clique em Salvar cookies e tente realizar a consulta/Download SIOR novamente (Passo 3).",
                    size=11
                ),

                ft.Divider(),

                ft.Text("Prints de apoio", size=13, weight="bold"),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(
                                "Clique em uma miniatura para visualizar o passo em tela ampliada.",
                                size=10,
                                italic=True,
                                color=ft.Colors.GREY_600
                            ),
                            _criar_area_imagens(
                                ft,
                                page,
                                imagens=imagens,
                                on_ampliar=ampliar_imagem
                            )
                        ],
                        spacing=8
                    ),
                    height=155,
                    padding=10,
                    border_radius=10,
                    border=ft.border.all(1, ft.Colors.GREY_300)
                ),


            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO
        ),
        padding=10
    )

    conteudo_principal = conteudo

    btn_cancelar = ft.TextButton(
        "Cancelar",
        on_click=cancelar
    )

    btn_salvar = ft.ElevatedButton(
        "Salvar cookies",
        icon=ft.Icons.SAVE,
        on_click=salvar
    )

    acoes_principais = [
        btn_cancelar,
        btn_salvar
    ]

    dialog_manual = ft.AlertDialog(
        modal=True,
        title=ft.Text("🔐 Login manual SIOR"),
        content=conteudo_principal,
        actions=acoes_principais,
        actions_alignment=ft.MainAxisAlignment.END
    )

    _abrir_dialogo(page, dialog_manual)


# =========================================================
# POPUP DE PERGUNTA INICIAL
# =========================================================

def perguntar_login_manual_sior(
        ft,
        page,
        mensagem_erro=None,
        imagens=None,
        on_cookie_salvo=None,
        on_nao=None
):
    """
    Popup inicial chamado quando ocorrer erro de login no SIOR.

    Pergunta ao usuário se deseja realizar login manual.
    - Não: fecha o popup.
    - Sim: fecha o popup inicial e abre janela de instruções/cookies.
    """

    dialog_confirmacao = None

    def confirmar_sim(e):
        _fechar_dialogo(page, dialog_confirmacao)

        abrir_janela_login_manual_sior(
            ft=ft,
            page=page,
            imagens=imagens,
            on_cookie_salvo=on_cookie_salvo
        )

    def confirmar_nao(e):
        _fechar_dialogo(page, dialog_confirmacao)

        if callable(on_nao):
            try:
                on_nao()
            except Exception:
                pass

    textos = [
        ft.Text(
            "Não foi possível confirmar o login automaticamente no SIOR.",
            size=12
        )
    ]

    if mensagem_erro:
        textos.append(
            ft.Container(
                content=ft.Text(
                    str(mensagem_erro),
                    size=10,
                    color=ft.Colors.RED,
                    selectable=True
                ),
                padding=8,
                border_radius=8,
                border=ft.border.all(1, ft.Colors.RED_200)
            )
        )

    textos.append(
        ft.Text(
            "Deseja realizar o login de forma manual informando os cookies da sessão?",
            size=12,
            weight="bold"
        )
    )

    dialog_confirmacao = ft.AlertDialog(
        modal=True,
        title=ft.Text("⚠️ Login SIOR não confirmado"),
        content=ft.Container(
            width=460,
            content=ft.Column(
                textos,
                spacing=10,
                tight=True
            )
        ),
        actions=[
            ft.TextButton(
                "Não",
                on_click=confirmar_nao
            ),
            ft.ElevatedButton(
                "Sim, realizar login manual",
                icon=ft.Icons.LOGIN,
                on_click=confirmar_sim
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END
    )

    _abrir_dialogo(page, dialog_confirmacao)


# =========================================================
# ABA VISUAL PARA O APP.PY
# =========================================================

def aba_login_manual_sior(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page):
    """
    Aba visual para acesso manual ao login do SIOR.
    """

    txt_status = ft.Text(
        "",
        size=DEFAULT_FONT_SIZE,
        visible=False
    )

    imagens_instrucao = [
        caminho_recurso(r"images\sior_login_1.png"),
        caminho_recurso(r"images\sior_login_2.png"),
        caminho_recurso(r"images\sior_login_3.png"),
    ]

    def on_cookie_salvo(caminho):
        txt_status.value = "✅ Cookies SIOR salvos com sucesso."
        txt_status.color = ft.Colors.GREEN
        txt_status.visible = True
        page.update()

    def abrir_popup_confirmacao(e):
        perguntar_login_manual_sior(
            ft=ft,
            page=page,
            mensagem_erro="Login automático do SIOR não confirmado.",
            imagens=imagens_instrucao,
            on_cookie_salvo=on_cookie_salvo
        )

    def abrir_janela_direta(e):
        abrir_janela_login_manual_sior(
            ft=ft,
            page=page,
            imagens=imagens_instrucao,
            on_cookie_salvo=on_cookie_salvo
        )

    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        "SIOR > Login Manual",
                        size=10,
                        weight="bold"
                    )
                ],
                alignment="center"
            ),

            ft.Divider(),

            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "🔐 Login manual do SIOR",
                            size=HEADING_FONT_SIZE,
                            weight="bold"
                        ),
                        ft.Text(
                            "Utilize esta tela quando o login automático do SIOR falhar "
                            "ou quando for necessário atualizar manualmente os cookies da sessão.",
                            size=DEFAULT_FONT_SIZE
                        ),
                        ft.Text(
                            "Os campos solicitados serão usados para recriar o arquivo cookies.json "
                            "com os cookies ASP.NET_SessionId e .SIOR_AUTH_prod_v2.",
                            size=DEFAULT_FONT_SIZE,
                            italic=True,
                            color=ft.Colors.GREY_600
                        ),
                    ],
                    spacing=8
                ),
                padding=15,
                border_radius=10,
                border=ft.border.all(1, ft.Colors.GREY_400)
            ),

            ft.Row(
                [
                    # ft.ElevatedButton(
                    #     "Abrir popup de confirmação",
                    #     icon=ft.Icons.HELP_OUTLINE,
                    #     on_click=abrir_popup_confirmacao
                    # ),
                    ft.ElevatedButton(
                        "Preencher cookies diretamente",
                        icon=ft.Icons.LOGIN,
                        on_click=abrir_janela_direta
                    ),
                ],
                spacing=10
            ),

            txt_status,

            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(
                            "⚠️ Atenção",
                            size=DEFAULT_FONT_SIZE,
                            weight="bold",
                            color=ft.Colors.ORANGE
                        ),
                        ft.Text(
                            "Não compartilhe os valores dos cookies em mensagens, prints ou logs. "
                            "Eles representam uma sessão autenticada do SIOR.",
                            size=DEFAULT_FONT_SIZE
                        ),
                    ],
                    spacing=5
                ),
                padding=12,
                border_radius=10,
                border=ft.border.all(1, ft.Colors.ORANGE_300)
            )
        ],
        expand=True,
        spacing=12,
        scroll=ft.ScrollMode.AUTO
    )