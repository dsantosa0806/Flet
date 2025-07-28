from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
import requests
from selenium import webdriver
import config
import os
import json

caminho_padrao = config.caminho_padrao
USER_DATA_DIR = config.USER_DATA_DIR


def store_profile(directory=USER_DATA_DIR):
    # Verifica se o diretório existe, caso contrário, cria
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except Exception as e:
        print(f"Erro ao criar pasta profile: {e}")


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

    store_profile()  # Criação da pasta caso não exista
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument("--profile-directory=Default")

    options.add_experimental_option('prefs', {
        "download.default_directory": config.caminho_padrao,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    })
    return options


def acessa_sior(navegador):
    try:
        navegador.get('http://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F')
    except Exception as e:
        print(f'Erro ao acessar SIOR: {e}')
        raise RuntimeError("Falha ao acessar SIOR")


def login(navegador):
    path_btn_entrar_gov = '//*[@id="placeholder"]/div[1]/div/div/div/div/div/div/form/div[2]/button'
    qr_code_path = '//*[@id="login-cpf"]/div[5]/a'
    logado = '//*[@id="center-pane"]/div/div/div[1]/div[2]'
    try:
        WebDriverWait(navegador, 120).until(EC.presence_of_element_located((By.XPATH, path_btn_entrar_gov))).click()
        WebDriverWait(navegador, 120).until(EC.presence_of_element_located((By.XPATH, qr_code_path))).click()
        WebDriverWait(navegador, 120).until(EC.presence_of_element_located((By.XPATH, logado))).is_displayed()
    except Exception as e:
        print(f"Erro no login manual: {e}")
        return 1


def elemento_existe(navegador, by, value):
    try:
        elemento = navegador.find_element(by, value)
        return elemento.is_displayed()
    except NoSuchElementException:
        return False


def acessa_tela_incial_auto(navegador):
    try:
        navegador.get('https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/?SituacoesInfracaoSelecionadas=0')
    except Exception as e:
        print(f"Erro ao acessar tela inicial: {e}")
        return 1


def iniciar_sessao_sior(log=None):
    def log_print(msg):
        print(msg)
        if log:
            log.value += f"\n{msg}"

    try:
        # 1. Primeiro tenta abrir em modo headless
        navegador = webdriver.Chrome(options=option_navegador(headless=True))
        log_print("🧭 navegador iniciado em modo headless")
        navegador.get("https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F")

        # Cria a sessão requests
        s = requests.Session()
        user_agent = navegador.execute_script("return navigator.userAgent;")
        s.headers.update({'User-Agent': user_agent})
        s.headers.update({"origin": "https://servicos.dnit.gov.br"})
        s.headers.update({"host": "servicos.dnit.gov.br"})

        # Tenta carregar cookies e verificar se já está logado
        load_cookies(navegador, s)
        navegador.refresh()
        acessa_sior(navegador)

        if not elemento_existe(navegador, By.XPATH, '//*[@id="center-pane"]/div/div/div[1]/div[2]'):
            log_print("🔐 Login manual necessário. Abrindo navegador visível...")
            navegador.quit()

            # 2. Abre navegador visível (sem headless)
            navegador = webdriver.Chrome(options=option_navegador(headless=False))
            navegador.get("https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F")
            acessa_sior(navegador)
            login(navegador)

            log_print("⏳ Aguarde 5 segundos para realizar o login manual...")
            import time
            time.sleep(5)

            # Após login manual, salva cookies e reinicia em headless
            store_cookies(navegador)
            navegador.quit()
            log_print("🔁 Reiniciando navegador em modo headless com cookies salvos...")

            navegador = webdriver.Chrome(options=option_navegador(headless=True))
            navegador.get("https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F")
            load_cookies(navegador, s)
            navegador.refresh()

        acessa_tela_incial_auto(navegador)
        log_print("📄 Tela inicial carregada.")
        return navegador, s

    except Exception as e:
        print(f"Erro ao acessar navegador: {e}")
        if log:
            log.value += f"\n❌ Erro ao iniciar sessão: {e}"
        return None, None