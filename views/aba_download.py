import os
import re
import threading
from datetime import datetime
from selenium.webdriver.common.by import By
import undetected_chromedriver as webdriver

from config import caminho_padrao
from navegador.sior_selenium_execution import (
    acessa_sior, login, elemento_existe,
    acessa_tela_incial_auto, iniciar_sessao_sior,
    option_navegador, load_cookies, store_cookies
)
from requests_data.requisicoes_sior import get_relatorio_financeiro, get_relatorio_resumido


# === LÓGICA DO PROCESSAMENTO DE DOWNLOADS ===
def executar_fluxo_completo(codigos_input,
                            log=None,
                            baixar_financeiro=False,
                            baixar_resumido=False,
                            atualizar_progresso=None,
                            total=0):
    def log_print(msg):
        print(msg)
        if log:
            log.value += f"\n{msg}"

    options = option_navegador()
    navegador, s = iniciar_sessao_sior(log=None)

    # Verifica se o login já está autenticado
    if not elemento_existe(navegador, By.XPATH, '//*[@id="center-pane"]/div/div/div[1]/div[2]'):
        log_print("🔐 Login manual necessário. Abrindo navegador visível...")
        navegador.quit()

        navegador = webdriver.Chrome(options=options(headless=True))
        cookies_load = load_cookies(navegador, s)
        cookies_store = store_cookies(navegador)

        navegador.get("https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F")
        acessa_sior(navegador)
        login(navegador)

        log_print("⏳ Aguarde 60 segundos para realizar o login manual...")
        import time
        time.sleep(60)

        cookies_store(navegador)
        navegador.quit()
        log_print("🔁 Reiniciando navegador em modo headless...")

        navegador = webdriver.Chrome(options=option_navegador(headless=True))
        navegador.get("https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F")
        cookies_load(navegador, s)
        navegador.refresh()

    acessa_tela_incial_auto(navegador)
    log_print("✅ Login realizado com sucesso.")
    log_print("📄 Tela inicial carregada.")

    # Criação da pasta destino
    pasta_destino = os.path.join(caminho_padrao, f"Relatórios {datetime.now().strftime('%Y-%m-%d')}")
    os.makedirs(pasta_destino, exist_ok=True)
    log_print(f"📁 Pasta criada: {pasta_destino}")

    try:
        codigos = [c.strip() for c in codigos_input.splitlines() if c.strip()]
        for i, ait in enumerate(codigos, 1):
            if baixar_financeiro:
                status = get_relatorio_financeiro(ait, s, pasta_destino)
                log_print(f"{'⚠' if status else '📄'} {'Falha' if status else 'Financeiro baixado'}: {ait}")

            if baixar_resumido:
                status = get_relatorio_resumido(ait, s, pasta_destino)
                log_print(f"{'⚠' if status else '🧾'} {'Falha' if status else 'Resumido baixado'}: {ait}")

            if atualizar_progresso:
                atualizar_progresso(i, total)
        log_print("✅ Todos os relatórios foram processados.")
    finally:
        navegador.quit()
        log_print("🧼 Navegador encerrado.")


# === UI COMPONENTE - ABA DE DOWNLOAD ===
def aba_download(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page, bloquear, desbloquear):
    # COMPONENTES
    input_download = ft.TextField(
        label="Número do AIT (um por linha)", multiline=True,
        min_lines=5, max_lines=10, height=150,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )
    check_financeiro = ft.Checkbox(label="Relatório Financeiro", value=True)
    check_resumido = ft.Checkbox(label="Relatório Resumido")
    btn_download = ft.ElevatedButton("Iniciar Processo", icon=ft.Icons.DOWNLOAD)
    progress_download = ft.ProgressBar(width=400, visible=False)
    status_download = ft.Text("", size=DEFAULT_FONT_SIZE, color="blue", visible=False)
    log_download = ft.TextField(label="📝 Log de Download",
                                multiline=True,
                                read_only=True,
                                expand=True,
                                height=200,
                                label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
                                text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
                                )

    # === FUNÇÃO PRINCIPAL DE AÇÃO ===
    def run_download(e):
        codigos = [c.strip() for c in input_download.value.splitlines() if c.strip()]
        erros = validar_codigos(codigos, check_financeiro.value, check_resumido.value)

        if erros:
            log_download.value = "\n".join(erros)
            page.update()
            return

        # Inicialização visual
        log_download.value = ""
        progress_download.value = 0
        status_download.visible = True
        status_download.value = "Preparando..."
        btn_download.disabled = True
        btn_download.text = "Processando..."
        page.snack_bar = ft.SnackBar(ft.Text("✅ Relatórios extraídos com sucesso!"), bgcolor=ft.Colors.GREEN)
        page.snack_bar.open = True
        page.update()

        def task():
            try:
                bloquear()
                total = len(codigos)
                status_download.value = f"Iniciando processamento de {total} AITs..."
                page.update()

                relatorios_processados = []

                def atualizar_progresso(idx, total):
                    status_download.value = f"Processando {idx}/{total}: {codigos[idx - 1]}"
                    progress_download.value = idx / total
                    page.update()

                executar_fluxo_completo(
                    "\n".join(codigos),  # passando todos de uma vez
                    log=log_download,
                    baixar_financeiro=check_financeiro.value,
                    baixar_resumido=check_resumido.value,
                    atualizar_progresso=atualizar_progresso,
                    total=total
                )
                status_download.value = "✅ Concluído"
            except Exception as ex:
                log_download.value += f"\n❌ Erro: {ex}\n"
            finally:
                btn_download.disabled = False
                btn_download.text = "Iniciar Processo"
                desbloquear()
                page.update()

        threading.Thread(target=task).start()

    def validar_codigos(codigos, financeiro, resumido):
        erros = []
        if not codigos:
            erros.append("⚠ É necessário inserir ao menos um código AIT.")
        if len(set(codigos)) < len(codigos):
            erros.append("⚠ Existem Número de AITs duplicados.")
        if len(codigos) > 2000:
            erros.append("⚠ Limite máximo de 2000 AITs por vez.")
        if any(" " in c for c in codigos):
            erros.append("⚠ Os Número de AIT não podem conter espaços.")
        if any(not re.match(r"^[A-Za-z][0-9]{9}$", c) for c in codigos):
            erros.append("⚠ Todos os Número de AITs devem ter o formato: Letra + 9 dígitos.")
        if not (financeiro or resumido):
            erros.append("⚠ Selecione ao menos um tipo de relatório.")
        return erros

    btn_download.on_click = run_download

    return ft.Column([
        ft.Row([ft.Text("SIOR > Download de Relatórios", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        input_download,
        ft.Row([check_financeiro, check_resumido], alignment="start"),
        ft.Row([btn_download], alignment="center"),
        status_download,
        progress_download,
        ft.Divider(),
        log_download
    ], expand=True)
