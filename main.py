from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
import undetected_chromedriver as webdriver
import pandas as pd
from Navegador.selenium_execution import acessa_sior, login, \
    elemento_existe, acessa_tela_incial_auto
from create_dir.diretorios import open_dir_arquivos, diretorios_exec, clean_diretorio_autos_pass, \
    clean_diretorio_arquivos_pass
import config
import json
import os
from requests_data.requisicoes import get_relatorio_financeiro
import requests
import time


caminho_padrao = config.caminho_padrao


def store_cookies(navegador, directory="C:\\Cookies-Selenium"):
    # Verifica se o diretório existe, caso contrário, cria
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Define o caminho para salvar os cookies
    cookies_file = os.path.join(directory, "cookies.json")

    try:
        # Salva os cookies no arquivo JSON
        cookies = navegador.get_cookies()
        with open(cookies_file, "w") as file:
            json.dump(cookies, file, indent=4)

        print(f"Cookies salvos em: {cookies_file}")
    except Exception as e:
        print(f"Erro ao salvar cookies: {e}")


def load_cookies(navegador, s, directory="C:\\Cookies-Selenium"):
    # Define o caminho para carregar os cookies
    cookies_file = os.path.join(directory, "cookies.json")

    if os.path.exists(cookies_file):
        try:
            with open(cookies_file, "r") as file:
                cookies = json.load(file)
                for cookie in cookies:
                    navegador.add_cookie(cookie)

                    # Inicia aqui
                    s.cookies.set(cookie["name"], cookie["value"])

            print("Cookies carregados com sucesso!")
        except Exception as e:
            print(f"Erro ao carregar cookies: {e}")
    else:
        print("Arquivo de cookies não encontrado.")


def option_navegador(headless=True):
    options = webdriver.ChromeOptions()
    options.add_argument("enable-automation")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--dns-prefetch-disable")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--use_subprocess")

    if headless:
        options.add_argument("--headless=new")

    options.add_experimental_option('prefs', {
        "download.default_directory": config.caminho_padrao,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    })
    return options


def service_navegador():
    serv = Service()
    return serv


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
    from selenium.webdriver.common.by import By
    import requests
    from datetime import datetime
    import os
    import config
    from requests_data.requisicoes import get_relatorio_financeiro, get_relatorio_resumido
    from Navegador.selenium_execution import acessa_sior, login, elemento_existe, acessa_tela_incial_auto
    import undetected_chromedriver as webdriver

    def log_print(msg):
        print(msg)
        if log:
            log.value += f"\n{msg}"

    navegador = webdriver.Chrome(options=option_navegador(headless=True))
    log_print("🧭 Navegador iniciado em modo headless")

    navegador.get("https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F")

    # 🔧 Cria e configura a sessão requests
    s = requests.Session()
    user_agent = navegador.execute_script("return navigator.userAgent;")
    s.headers.update({'User-Agent': user_agent})
    s.headers.update({"origin": "https://servicos.dnit.gov.br"})
    s.headers.update({"host": "servicos.dnit.gov.br"})

    load_cookies(navegador, s)
    navegador.refresh()
    acessa_sior(navegador)

    if not elemento_existe(navegador, By.XPATH, '//*[@id="center-pane"]/div/div/div[1]/div[2]'):
        log_print("🔐 Login manual necessário. Abrindo navegador visível...")
        navegador.quit()

        navegador = webdriver.Chrome(options=option_navegador(headless=True))
        navegador.get("https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F")
        acessa_sior(navegador)
        login(navegador)

        log_print("⏳ Aguarde 60 segundos para realizar o login manual...")
        import time
        time.sleep(60)

        store_cookies(navegador)
        navegador.quit()
        log_print("🔁 Reiniciando navegador em modo headless...")

        navegador = webdriver.Chrome(options=option_navegador(headless=True))
        navegador.get("https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F")
        load_cookies(navegador, s)
        navegador.refresh()

    acessa_tela_incial_auto(navegador)
    log_print("📄 Tela inicial carregada.")

    # 🗂️ Cria pasta destino
    timestamp_legivel = datetime.now().strftime("%Y-%m-%d %Hh%Mm")
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

