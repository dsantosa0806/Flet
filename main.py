from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import undetected_chromedriver as webdriver
from Navegador.selenium_execution import acessa_sior, login, \
    elemento_existe, acessa_tela_incial_auto, iniciar_sessao_sior, option_navegador, load_cookies, store_cookies
import config
import json
import os
from requests_data.requisicoes import get_relatorio_financeiro, get_relatorio_resumido
from datetime import datetime

caminho_padrao = config.caminho_padrao


def correlacionar_processo_sei_auto(df):
    # Cria um dicionário para armazenar a relação de processos e autos
    correlacao = {}

    # Itera sobre cada processo único em 'PROCESSO SEI'
    for processo in df['PROCESSO SEI'].unique():
        # Filtra o DataFrame para encontrar todos os 'AUTO' associados ao 'PROCESSO SEI' atual
        autos_correlacionados = df[df['PROCESSO SEI'] == processo]['AUTO'].tolist()

        # Armazena a lista de 'AUTO' no dicionário
        correlacao[processo] = autos_correlacionados

    return correlacao


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
    log_print("📄 Tela inicial carregada.")

    # 🗂️ Cria pasta destino
    timestamp_legivel = datetime.now().strftime("%Y-%m-%d")
    pasta_destino = os.path.join(config.caminho_padrao, f"Relatórios {timestamp_legivel}")
    os.makedirs(pasta_destino, exist_ok=True)
    log_print(f"📁 Pasta criada: {pasta_destino}")

    try:
        # 🔄 Processa os códigos
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

