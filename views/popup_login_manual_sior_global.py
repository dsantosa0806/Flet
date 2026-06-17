import os
import json
import threading
from datetime import datetime, timezone

import config


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


# =========================================================
# CONFIGURAÇÃO GLOBAL DO POPUP
# =========================================================

IMAGENS_PADRAO_LOGIN_MANUAL_SIOR = [
    r"images\sior_login_1.png",
    r"images\sior_login_2.png",
    r"images\sior_login_3.png"
]

_CONTEXTO_POPUP_LOGIN_MANUAL_SIOR = {
    "ft": None,
    "page": None,
    "imagens": IMAGENS_PADRAO_LOGIN_MANUAL_SIOR,
    "on_cookie_salvo": None,
    "on_nao": None,
    "on_fechar": None,
    "log": None,
}

_LOCK_POPUP_LOGIN_MANUAL_SIOR = threading.RLock()
_POPUP_LOGIN_MANUAL_SIOR_ABERTO = False


def configurar_popup_login_manual_sior(
        ft,
        page,
        imagens=None,
        on_cookie_salvo=None,
        on_nao=None,
        on_fechar=None,
        log=None
):
    """
    Configura o contexto global do popup de Login Manual SIOR.

    Chame esta função uma única vez no app.py, dentro do main(page).

    Depois disso, o popup poderá ser chamado de qualquer lugar do projeto:

        perguntar_login_manual_sior(mensagem_erro="Erro ao iniciar sessão SIOR")

    Inclusive de arquivos de Selenium, sem precisar passar ft/page novamente.
    """

    with _LOCK_POPUP_LOGIN_MANUAL_SIOR:
        _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR["ft"] = ft
        _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR["page"] = page
        _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR["imagens"] = imagens or IMAGENS_PADRAO_LOGIN_MANUAL_SIOR
        _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR["on_cookie_salvo"] = on_cookie_salvo
        _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR["on_nao"] = on_nao
        _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR["on_fechar"] = on_fechar
        _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR["log"] = log

    return True


def popup_login_manual_sior_configurado():
    """
    Retorna True se ft e page já foram configurados.
    """

    with _LOCK_POPUP_LOGIN_MANUAL_SIOR:
        return bool(
            _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR.get("ft")
            and _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR.get("page")
        )


def _resolver_contexto(
        ft=None,
        page=None,
        imagens=None,
        on_cookie_salvo=None,
        on_nao=None,
        on_fechar=None,
        log=None
):
    """
    Resolve ft/page/imagens/callbacks usando os parâmetros recebidos
    ou o contexto global configurado no app.py.
    """

    with _LOCK_POPUP_LOGIN_MANUAL_SIOR:
        ft_final = ft or _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR.get("ft")
        page_final = page or _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR.get("page")
        imagens_final = imagens or _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR.get("imagens") or IMAGENS_PADRAO_LOGIN_MANUAL_SIOR
        on_cookie_salvo_final = on_cookie_salvo or _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR.get("on_cookie_salvo")
        on_nao_final = on_nao or _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR.get("on_nao")
        on_fechar_final = on_fechar or _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR.get("on_fechar")
        log_final = log or _CONTEXTO_POPUP_LOGIN_MANUAL_SIOR.get("log")

    return (
        ft_final,
        page_final,
        imagens_final,
        on_cookie_salvo_final,
        on_nao_final,
        on_fechar_final,
        log_final,
    )


def _log(log, mensagem):
    print(mensagem)

    if not log:
        return

    try:
        if callable(log):
            log(mensagem)
        elif hasattr(log, "value"):
            log.value += f"\n{mensagem}"
    except Exception:
        pass


def _safe_page_update(page):
    try:
        page.update()
    except Exception as ex:
        print(f"Erro ao atualizar página Flet: {ex}")


def _marcar_popup_aberto(valor):
    global _POPUP_LOGIN_MANUAL_SIOR_ABERTO

    with _LOCK_POPUP_LOGIN_MANUAL_SIOR:
        _POPUP_LOGIN_MANUAL_SIOR_ABERTO = bool(valor)


def popup_login_manual_sior_aberto():
    with _LOCK_POPUP_LOGIN_MANUAL_SIOR:
        return _POPUP_LOGIN_MANUAL_SIOR_ABERTO


# =========================================================
# HELPERS DE COOKIES
# =========================================================

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
        page.open(dialog)
        return True
    except Exception:
        pass

    try:
        page.dialog = dialog
        dialog.open = True
        _safe_page_update(page)
        return True
    except Exception:
        pass

    try:
        if dialog not in page.overlay:
            page.overlay.append(dialog)

        dialog.open = True
        _safe_page_update(page)
        return True
    except Exception as ex:
        print(f"Erro ao abrir diálogo: {ex}")
        return False


def _fechar_dialogo(page, dialog=None):
    """
    Fecha AlertDialog de forma compatível com versões novas e antigas do Flet.
    """

    try:
        if dialog:
            page.close(dialog)
            return True
    except Exception:
        pass

    try:
        if dialog:
            dialog.open = False
        elif getattr(page, "dialog", None):
            page.dialog.open = False

        _safe_page_update(page)
        return True
    except Exception:
        pass

    try:
        if dialog and dialog in page.overlay:
            page.overlay.remove(dialog)
            _safe_page_update(page)
            return True
    except Exception:
        pass

    return False


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
    """

    expiry_value = str(expiry_value or "").strip()

    if not expiry_value:
        raise ValueError("Expiry não informado.")

    if expiry_value.isdigit():
        return int(expiry_value)

    try:
        if expiry_value.endswith("Z"):
            expiry_value = expiry_value.replace("Z", "+00:00")

        expiry_datetime = datetime.fromisoformat(expiry_value)

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
            "value": session_id_value,
        },
        {
            "domain": "servicos.dnit.gov.br",
            "expiry": sior_auth_expiry,
            "httpOnly": True,
            "name": ".SIOR_AUTH_prod_v2",
            "path": "/",
            "sameSite": "Lax",
            "secure": False,
            "value": sior_auth_value,
        },
    ]

    caminho = _cookies_path()

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(cookies, arquivo, ensure_ascii=False, indent=4)

    return caminho


# =========================================================
# COMPONENTES VISUAIS
# =========================================================

def _criar_conteudo_imagem_ampliada(ft, caminho_img, titulo, on_voltar):
    """
    Cria o conteúdo ampliado da imagem dentro do próprio popup Login Manual SIOR.
    Não abre um segundo AlertDialog.
    """

    return ft.Container(
        width=900,
        height=650,
        padding=10,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(f"🖼️ {titulo}", size=16, weight="bold"),
                        ft.Container(expand=True),
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK,
                            tooltip="Voltar às instruções",
                            on_click=on_voltar,
                        ),
                    ]
                ),
                ft.Text(
                    "Visualização ampliada da imagem. Clique em voltar para retornar ao formulário.",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600,
                ),
                ft.Container(
                    content=ft.Image(
                        src=caminho_img,
                        width=860,
                        height=560,
                        fit=ft.ImageFit.CONTAIN,
                        border_radius=8,
                    ),
                    alignment=ft.alignment.center,
                    expand=True,
                ),
            ],
            spacing=10,
        ),
    )


def _criar_area_imagens(ft, imagens=None, on_ampliar=None):
    """
    Cria área visual para prints de instrução.
    """

    imagens = imagens or []
    controles = []

    if imagens:
        for idx, caminho_img in enumerate(imagens, start=1):
            titulo_img = f"Print {idx}"

            def clicar_imagem(e, img=caminho_img, titulo=titulo_img):
                if callable(on_ampliar):
                    on_ampliar(img, titulo)

            controles.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(titulo_img, size=11, weight="bold"),
                                    ft.Text(
                                        "Clique na imagem para ampliar",
                                        size=10,
                                        italic=True,
                                        color=ft.Colors.GREY_500,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Container(
                                content=ft.Image(
                                    src=caminho_img,
                                    width=520,
                                    height=260,
                                    fit=ft.ImageFit.CONTAIN,
                                    border_radius=8,
                                ),
                                padding=5,
                                border_radius=8,
                                ink=True,
                                on_click=clicar_imagem,
                            ),
                        ],
                        spacing=5,
                    ),
                    padding=10,
                    border_radius=10,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                )
            )
    else:
        for idx in range(1, 4):
            controles.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"Espaço para print {idx}", size=11, weight="bold"),
                            ft.Text(
                                "Adicione futuramente uma imagem com o passo a passo do login.",
                                size=10,
                                italic=True,
                                color=ft.Colors.GREY_500,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=5,
                    ),
                    width=520,
                    height=140,
                    padding=10,
                    border_radius=10,
                    border=ft.border.all(1, ft.Colors.GREY_400),
                    alignment=ft.alignment.center,
                )
            )

    return ft.Column(controles, spacing=10, scroll=ft.ScrollMode.AUTO)


def _criar_texto_etapa_2(ft):
    return ft.Text(
        spans=[
            ft.TextSpan("2. Após concluir o login no SIOR, pressione "),
            ft.TextSpan("F12", style=ft.TextStyle(weight="bold")),
            ft.TextSpan(" para abrir as "),
            ft.TextSpan("Ferramentas do Desenvolvedor", style=ft.TextStyle(weight="bold")),
            ft.TextSpan(". Em seguida, acesse: "),
            ft.TextSpan(
                "Aplicativo/Application > Cookies > https://servicos.dnit.gov.br",
                style=ft.TextStyle(weight="bold"),
            ),
            ft.TextSpan(
                ". Nessa área estarão disponíveis os cookies necessários para preencher os campos abaixo."
            ),
        ],
        size=11,
    )


# =========================================================
# JANELA PRINCIPAL DE LOGIN MANUAL
# =========================================================

def abrir_janela_login_manual_sior(
        ft=None,
        page=None,
        imagens=None,
        on_cookie_salvo=None,
        on_fechar=None,
        log=None
):
    """
    Abre janela/modal para instruções e preenchimento manual dos cookies do SIOR.

    Pode ser chamada diretamente com ft/page ou usando o contexto global configurado.
    """

    (
        ft,
        page,
        imagens,
        on_cookie_salvo,
        _,
        on_fechar,
        log,
    ) = _resolver_contexto(
        ft=ft,
        page=page,
        imagens=imagens,
        on_cookie_salvo=on_cookie_salvo,
        on_fechar=on_fechar,
        log=log,
    )

    if not ft or not page:
        _log(
            log,
            "⚠️ Popup Login Manual SIOR não configurado. "
            "Chame configurar_popup_login_manual_sior(ft, page) no app.py.",
        )
        return False

    if popup_login_manual_sior_aberto():
        _log(log, "ℹ️ Popup Login Manual SIOR já está aberto.")
        return False

    _marcar_popup_aberto(True)

    dialog_manual = None
    conteudo_principal = None
    acoes_principais = None
    btn_cancelar = None

    def finalizar_popup():
        _marcar_popup_aberto(False)

        if callable(on_fechar):
            try:
                on_fechar()
            except Exception:
                pass

    def voltar_para_formulario(e=None):
        try:
            dialog_manual.content = conteudo_principal
            dialog_manual.actions = acoes_principais
            _safe_page_update(page)
        except Exception as ex:
            _log(log, f"Erro ao voltar para formulário de login manual: {ex}")

    def ampliar_imagem(caminho_img, titulo):
        try:
            dialog_manual.content = _criar_conteudo_imagem_ampliada(
                ft,
                caminho_img,
                titulo,
                voltar_para_formulario,
            )

            dialog_manual.actions = [
                ft.TextButton(
                    "Voltar às instruções",
                    icon=ft.Icons.ARROW_BACK,
                    on_click=voltar_para_formulario,
                )
            ]

            _safe_page_update(page)

        except Exception as ex:
            _log(log, f"Erro ao ampliar imagem: {ex}")

    input_session_id = ft.TextField(
        label="value do ASP.NET_SessionId",
        hint_text="Ex: 2nmn2g3fxiiylqzwlex0mli1",
        multiline=False,
        password=True,
        can_reveal_password=True,
        dense=True,
    )

    input_sior_auth_expiry = ft.TextField(
        label="expiry do .SIOR_AUTH_prod_v2",
        hint_text="Ex: 2026-06-16T23:49:48.806Z ou 1781637387",
        multiline=False,
        dense=True,
    )

    input_sior_auth_value = ft.TextField(
        label="value do .SIOR_AUTH_prod_v2",
        hint_text="Cole aqui o value completo do cookie .SIOR_AUTH_prod_v2",
        multiline=True,
        min_lines=3,
        max_lines=5,
        password=True,
        can_reveal_password=True,
    )

    txt_status = ft.Text("", size=11, visible=False)

    def salvar(e):
        valido, mensagem = _validar_campos(
            input_session_id.value,
            input_sior_auth_expiry.value,
            input_sior_auth_value.value,
        )

        if not valido:
            txt_status.value = f"⚠️ {mensagem}"
            txt_status.color = ft.Colors.ORANGE
            txt_status.visible = True
            _safe_page_update(page)
            return

        try:
            caminho = salvar_cookies_sior_manual(
                input_session_id.value,
                input_sior_auth_expiry.value,
                input_sior_auth_value.value,
            )

            txt_status.value = "✅ Cookies salvos com sucesso. Clique em Fechar e tente executar a consulta novamente."
            txt_status.color = ft.Colors.GREEN
            txt_status.visible = True

            try:
                btn_cancelar.text = "Fechar"
            except Exception:
                pass

            _safe_page_update(page)

            if callable(on_cookie_salvo):
                try:
                    on_cookie_salvo(caminho)
                except Exception:
                    pass

        except Exception as ex:
            txt_status.value = f"❌ Erro ao salvar cookies: {ex}"
            txt_status.color = ft.Colors.RED
            txt_status.visible = True
            _safe_page_update(page)

    def cancelar(e=None):
        _fechar_dialogo(page, dialog_manual)
        finalizar_popup()

    conteudo = ft.Container(
        width=1080,
        height=720,
        content=ft.Column(
            [

                ft.Text("Dados dos cookies", size=13, weight="bold"),
                input_session_id,
                input_sior_auth_expiry,
                input_sior_auth_value,
                txt_status,
                ft.Divider(),

                ft.Text("Login manual no SIOR", size=18, weight="bold"),
                ft.Text(
                    "Siga as etapas abaixo para gerar os cookies necessários e liberar a sessão do SIOR.",
                    size=12,
                ),
                ft.Divider(),
                ft.Text("Etapas sugeridas", size=13, weight="bold"),
                ft.Text(
                    "1. Abra o SIOR no SEU navegador e realize o login normalmente pelo Gov.br. "
                    "Utilize preferencialmente o Chrome.",
                    size=11,
                ),
                _criar_texto_etapa_2(ft),
                ft.Text(
                    "3. Localize os cookies ASP.NET_SessionId e .SIOR_AUTH_prod_v2.",
                    size=11,
                ),
                ft.Text(
                    "4. Copie os campos solicitados abaixo exatamente como aparecem no navegador.",
                    size=11,
                ),
                ft.Text(
                    "5. Clique em Salvar cookies e tente realizar a consulta/Download SIOR novamente.",
                    size=11,
                ),
                ft.Divider(),
                ft.Text("Prints de apoio", size=13, weight="bold"),
                ft.Container(
                    content=_criar_area_imagens(
                        ft,
                        imagens=imagens,
                        on_ampliar=ampliar_imagem,
                    ),
                    height=210,
                    padding=5,
                    border_radius=8,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                ),
                ft.Divider(),
                ft.Text("Dados dos cookies", size=13, weight="bold"),
                input_session_id,
                input_sior_auth_expiry,
                input_sior_auth_value,
                txt_status,
            ],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=10,
    )

    conteudo_principal = conteudo

    btn_cancelar = ft.TextButton("Cancelar", on_click=cancelar)

    btn_salvar = ft.ElevatedButton(
        "Salvar cookies",
        icon=ft.Icons.SAVE,
        on_click=salvar,
    )

    acoes_principais = [btn_cancelar, btn_salvar]

    dialog_manual = ft.AlertDialog(
        modal=True,
        title=ft.Text("🔐 Login manual SIOR"),
        content=conteudo_principal,
        actions=acoes_principais,
        actions_alignment=ft.MainAxisAlignment.END,
    )

    abriu = _abrir_dialogo(page, dialog_manual)

    if not abriu:
        finalizar_popup()
        return False

    return True


# =========================================================
# POPUP DE PERGUNTA INICIAL GLOBAL
# =========================================================

def perguntar_login_manual_sior(
        ft=None,
        page=None,
        mensagem_erro=None,
        imagens=None,
        on_cookie_salvo=None,
        on_nao=None,
        on_fechar=None,
        abrir_direto=False,
        log=None
):
    """
    Popup inicial chamado quando ocorrer erro de login no SIOR.

    Pode ser chamado de qualquer lugar do projeto, desde que o contexto tenha sido
    configurado previamente no app.py com configurar_popup_login_manual_sior().

    Exemplos:

        perguntar_login_manual_sior(
            mensagem_erro="Erro ao iniciar sessão SIOR"
        )

        perguntar_login_manual_sior(
            mensagem_erro="Erro ao iniciar sessão SIOR",
            abrir_direto=True
        )
    """

    (
        ft,
        page,
        imagens,
        on_cookie_salvo,
        on_nao,
        on_fechar,
        log,
    ) = _resolver_contexto(
        ft=ft,
        page=page,
        imagens=imagens,
        on_cookie_salvo=on_cookie_salvo,
        on_nao=on_nao,
        on_fechar=on_fechar,
        log=log,
    )

    if not ft or not page:
        _log(
            log,
            "⚠️ Popup Login Manual SIOR não configurado. "
            "Chame configurar_popup_login_manual_sior(ft, page) no app.py.",
        )
        return False

    if abrir_direto:
        return abrir_janela_login_manual_sior(
            ft=ft,
            page=page,
            imagens=imagens,
            on_cookie_salvo=on_cookie_salvo,
            on_fechar=on_fechar,
            log=log,
        )

    if popup_login_manual_sior_aberto():
        _log(log, "ℹ️ Popup Login Manual SIOR já está aberto.")
        return False

    _marcar_popup_aberto(True)

    dialog_confirmacao = None

    def finalizar_popup():
        _marcar_popup_aberto(False)

        if callable(on_fechar):
            try:
                on_fechar()
            except Exception:
                pass

    def confirmar_sim(e):
        _fechar_dialogo(page, dialog_confirmacao)
        _marcar_popup_aberto(False)

        abrir_janela_login_manual_sior(
            ft=ft,
            page=page,
            imagens=imagens,
            on_cookie_salvo=on_cookie_salvo,
            on_fechar=on_fechar,
            log=log,
        )

    def confirmar_nao(e):
        _fechar_dialogo(page, dialog_confirmacao)
        finalizar_popup()

        if callable(on_nao):
            try:
                on_nao()
            except Exception:
                pass

    textos = [
        ft.Text(
            "Não foi possível confirmar o login automaticamente no SIOR.",
            size=12,
        )
    ]

    if mensagem_erro:
        textos.append(
            ft.Container(
                content=ft.Text(
                    str(mensagem_erro),
                    size=10,
                    color=ft.Colors.RED,
                    selectable=True,
                ),
                padding=8,
                border_radius=8,
                border=ft.border.all(1, ft.Colors.RED_200),
            )
        )

    textos.append(
        ft.Text(
            "Deseja realizar o login de forma manual informando os cookies da sessão?",
            size=12,
            weight="bold",
        )
    )

    dialog_confirmacao = ft.AlertDialog(
        modal=True,
        title=ft.Text("⚠️ Login SIOR não confirmado"),
        content=ft.Container(
            width=460,
            content=ft.Column(textos, spacing=10, tight=True),
        ),
        actions=[
            ft.TextButton("Não", on_click=confirmar_nao),
            ft.ElevatedButton(
                "Sim, realizar login manual",
                icon=ft.Icons.LOGIN,
                on_click=confirmar_sim,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    abriu = _abrir_dialogo(page, dialog_confirmacao)

    if not abriu:
        finalizar_popup()
        return False

    return True

# Alias opcional para melhorar a leitura em chamadas feitas por Selenium/backend.
abrir_popup_login_manual_sior = perguntar_login_manual_sior
