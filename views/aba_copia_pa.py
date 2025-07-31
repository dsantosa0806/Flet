import os
import re
import json
import threading
import time
import config
import flet as ft
from selenium import webdriver
from navegador.sapiens_selenium_execution import login as sapiens_login, acessa_sapiens, options_nav
from utils.popups import mostrar_alerta

COOKIE_PATH_SAPIENS = config.COOKIE_PATH_SAPIENS


def carregar_credenciais():
    if os.path.exists(COOKIE_PATH_SAPIENS):
        try:
            with open(COOKIE_PATH_SAPIENS, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("user"), data.get("password")
        except Exception:
            return None, None
    return None, None


def salvar_credenciais(user, password):
    try:
        with open(COOKIE_PATH_SAPIENS, "w", encoding="utf-8") as f:
            json.dump({"user": user, "password": password}, f)
    except Exception as ex:
        print(f"Erro ao salvar credenciais: {ex}")


def limpar_nup(nup_formatado):
    return re.sub(r"[^\d]", "", nup_formatado)


def verificar_download_concluido(nome_arquivo: str, timeout=50, intervalo=1) -> bool:
    caminho = os.path.join(config.caminho_padrao, nome_arquivo)
    tentativas = int(timeout / intervalo)
    for _ in range(tentativas):
        if os.path.exists(caminho):
            return True
        time.sleep(intervalo)
    return False


def aba_copia_pa(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page):
    cached_user, cached_pass = carregar_credenciais()

    alerta_dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[],
        open=False
    )
    txt_user = ft.TextField(label="Usuário Sapiens", width=300, value=cached_user or "")
    txt_pass = ft.TextField(label="Senha Sapiens", width=300, password=True, can_reveal_password=True, value=cached_pass or "")
    credenciais_expander = ft.ExpansionTile(
        title=ft.Text("🔐 Credenciais Sapiens"),
        initially_expanded=not cached_user,
        controls=[ft.Row([txt_user, txt_pass])]
    )

    input_nups = ft.TextField(
        label="Informe os NUPs (um por linha, ex: 50600.123456/2021-00)",
        multiline=True, min_lines=5, max_lines=10, height=150,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )

    btn_iniciar = ft.ElevatedButton("Iniciar Download", icon=ft.Icons.DOWNLOAD)
    progress = ft.ProgressBar(width=400, visible=False)
    status = ft.Text("", size=DEFAULT_FONT_SIZE, color="blue", visible=False)
    log_execucao = ft.TextField(label="📝 Log", multiline=True, read_only=True, expand=True, height=200,
                                label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
                                text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE))

    def validar_nups(lista_nups):
        erros = []
        if not lista_nups:
            erros.append("⚠ Nenhum NUP informado.")
        if len(lista_nups) > 50:
            erros.append("⚠ Limite máximo de 50 NUPs por tentativa.")
        for nup in lista_nups:
            nup_limpo = limpar_nup(nup)
            if len(nup_limpo) != 17 or not nup_limpo.isdigit():
                erros.append(f"❌ NUP inválido: {nup} (esperado 17 dígitos)")
        return erros

    def run_download(e):
        nups_raw = [n.strip() for n in input_nups.value.splitlines() if n.strip()]
        erros = validar_nups(nups_raw)
        if erros:
            log_execucao.value = "\n".join(erros)
            page.update()
            return

        user_input = txt_user.value.strip()
        pass_input = txt_pass.value.strip()
        if not user_input or not pass_input:
            page.dialog = alerta_dialogo
            mostrar_alerta(ft, page, "Credenciais obrigatórias", "Informe usuário e senha do Sapiens", tipo="warning")
            return

        if user_input != cached_user or pass_input != cached_pass:
            salvar_credenciais(user_input, pass_input)

        btn_iniciar.disabled = True
        btn_iniciar.text = "Processando..."
        progress.visible = True
        status.visible = True
        status.value = "Iniciando..."
        log_execucao.value = ""
        page.update()

        def task():
            try:

                navegador = webdriver.Chrome(options=options_nav())
                navegador.minimize_window()
                navegador, cookies = sapiens_login(navegador, user_input, pass_input)

                if not cookies or navegador is None:
                    status.value = "❌ Falha no login. Usuário ou senha incorreto."
                    page.dialog = alerta_dialogo
                    mostrar_alerta(ft, page, "Falha no login",
                                   "Usuário ou senha incorreto.",
                                   tipo="error")
                    if navegador:
                        navegador.quit()
                    btn_iniciar.disabled = False
                    btn_iniciar.text = "Novo Download"
                    progress.visible = False
                    page.update()
                    return

                status.value = "🔐 Login realizado com sucesso! Iniciando requisições..."
                log_execucao.value += "A velocidade da sua internet pode influenciar no tempo de download dos arquivos\n"
                total = len(nups_raw)
                for idx, nup_formatado in enumerate(nups_raw, 1):
                    nup_limpo = limpar_nup(nup_formatado)
                    status.value = f"Baixando {idx}/{total}: {nup_formatado}"
                    navegador.get(f"https://sapiens.agu.gov.br/pdfcompleto?nup={nup_limpo}")
                    progress.value = idx / total
                    page.update()

                    nome_arquivo = f"{nup_limpo}.pdf"
                    if verificar_download_concluido(nome_arquivo):
                        log_execucao.value += f"✅ Download finalizado: {nup_formatado}\n"
                    else:
                        log_execucao.value += f"❌ Timeout: download não encontrado para {nup_formatado}\n"

                status.value = "✅ Concluído!"
                page.dialog = alerta_dialogo
                mostrar_alerta(ft,
                               page,
                               "Download concluído",
                               f"{total} documentos disponíveis em C:\\Downloads.",
                               tipo="success")

            except Exception as ex:
                log_execucao.value += f"❌ Erro: {ex}"
                status.value = "Erro"
            finally:
                if navegador:
                    navegador.quit()
                btn_iniciar.disabled = False
                btn_iniciar.text = "Novo Download"
                progress.visible = False
                page.update()

        threading.Thread(target=task).start()

    btn_iniciar.on_click = run_download

    return ft.Column([
        ft.Row([ft.Text("SAPIENS > Download de Processo Administrativo", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        credenciais_expander,
        input_nups,
        ft.Row([btn_iniciar], alignment="center"),
        status,
        progress,
        log_execucao,
        alerta_dialogo
    ], expand=True)
