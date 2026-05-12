from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
import requests
from selenium import webdriver
import config
import os
import json
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
    options.page_load_strategy = "eager"

    if headless:
        options.add_argument("--headless=new")

    options.add_experimental_option('prefs', {
        "download.default_directory": config.caminho_padrao,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    })
    return options


def acessa_sior(navegador):
    try:
        url = 'http://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F'

        navegador.set_page_load_timeout(15)

        try:
            navegador.get(url)
        except TimeoutException:
            print("⚠️ Timeout no carregamento → forçando stop")
            navegador.execute_script("window.stop();")

        # 🔥 1. GARANTE que algo carregou (body sempre existe)
        WebDriverWait(navegador, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # 🔥 2. ESPERA a página parar de "mexer" (estabilizar)
        WebDriverWait(navegador, 15).until(
            lambda d: d.execute_script("return document.readyState") in ["interactive", "complete"]
        )

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
        WebDriverWait(navegador, 180).until(EC.presence_of_element_located((By.XPATH, logado))).is_displayed()
    except Exception as e:
        print(f"Erro no login manual: {e}")
        return 1


def elemento_existe(navegador, by, value):
    try:
        elemento = navegador.find_element(by, value)
        return elemento.is_displayed()
    except NoSuchElementException:
        return False




import time
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException
)
from selenium.webdriver.common.by import By


def safe_get(
        navegador,
        url,
        elemento_validacao=None,
        tentativas=3,
        timeout_get=20,
        timeout_elemento=15,
        tempo_espera=2
):

    ultimo_erro = None

    for tentativa in range(1, tentativas + 1):

        try:

            print(f"🌐 Acessando URL ({tentativa}/{tentativas}): {url}")

            navegador.set_page_load_timeout(timeout_get)

            carregamento_interrompido = False

            try:
                navegador.get(url)

            except TimeoutException:
                print("⚠️ Timeout no carregamento da página. Interrompendo carregamento...")

                carregamento_interrompido = True

                try:
                    navegador.execute_script("window.stop();")
                except Exception:
                    pass

            # ===================================================
            # ESPERA CURTA PARA ESTABILIZAR O CHROMEDRIVER
            # ===================================================
            time.sleep(2)

            # ===================================================
            # TESTE LEVE DE DOM
            # ===================================================
            try:
                body_existe = navegador.execute_script(
                    "return document.body != null"
                )

                if not body_existe:
                    raise Exception("DOM não carregado")

            except Exception as ex:
                raise Exception(f"DOM inválido: {ex}")

            # ===================================================
            # VALIDAÇÃO OPCIONAL DE ELEMENTO
            # ===================================================
            if elemento_validacao:

                by, value = elemento_validacao

                encontrou = False
                inicio = time.time()

                while time.time() - inicio < timeout_elemento:

                    try:

                        elementos = navegador.find_elements(by, value)

                        if elementos:
                            encontrou = True
                            break

                    except Exception:
                        pass

                    time.sleep(1)

                if not encontrou:

                    # 🔥 MUITO IMPORTANTE:
                    # se houve window.stop() e o DOM existe,
                    # aceita parcialmente a página
                    if carregamento_interrompido:
                        print("⚠️ Página parcialmente carregada, mas DOM disponível.")
                        return True

                    raise Exception(
                        f"Elemento de validação não encontrado: {value}"
                    )

            print("✅ Página carregada com sucesso.")
            return True

        except WebDriverException as ex:

            ultimo_erro = ex

            print(f"⚠️ WebDriverException tentativa {tentativa}: {ex}")

            try:
                navegador.execute_script("window.stop();")
            except Exception:
                pass

            time.sleep(tempo_espera)

        except Exception as ex:

            ultimo_erro = ex

            print(f"⚠️ Tentativa {tentativa} falhou: {ex}")

            try:
                navegador.execute_script("window.stop();")
            except Exception:
                pass

            time.sleep(tempo_espera)

    print(f"❌ Falha ao acessar URL após {tentativas} tentativas.")
    print(f"Último erro: {ultimo_erro}")

    return False


# =========================================================
# TELA INICIAL AUTO COM RETRY
# =========================================================
def acessa_tela_incial_auto(navegador):

    url = (
        "https://servicos.dnit.gov.br/sior/Infracao/"
        "ConsultaAutoInfracao/?SituacoesInfracaoSelecionadas=0"
    )

    sucesso = safe_get(
        navegador=navegador,
        url=url,

        # 🔥 NÃO usar elemento específico do SIOR
        elemento_validacao=(By.TAG_NAME, "body"),

        tentativas=3,
        timeout_get=20,
        timeout_elemento=10
    )

    if not sucesso:
        print("❌ Não foi possível carregar tela inicial.")
        return 1

    return 0


# =========================================================
# INICIAR SESSÃO SIOR (MELHORADO)
# =========================================================
def iniciar_sessao_sior(log=None):

    def log_print(msg):
        print(msg)
        if log:
            try:
                log(msg)
            except Exception:
                pass

    try:

        # =================================================
        # OPTIONS COM PAGE LOAD EAGER
        # =================================================
        options = option_navegador(headless=True)

        # 🔥 ESSENCIAL
        options.page_load_strategy = "eager"

        navegador = webdriver.Chrome(options=options)

        log_print("🧭 Navegador iniciado em modo headless")

        # =================================================
        # LOGIN PAGE COM SAFE_GET
        # =================================================
        sucesso_login_page = safe_get(
            navegador=navegador,
            url="https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F",
            elemento_validacao=(
                By.TAG_NAME,
                "body"
            ),
            tentativas=3,
            timeout_get=25,
            timeout_elemento=15
        )

        if not sucesso_login_page:
            raise Exception("Falha ao abrir página inicial do SIOR")

        # =================================================
        # SESSION REQUESTS
        # =================================================
        import requests

        s = requests.Session()

        user_agent = navegador.execute_script(
            "return navigator.userAgent;"
        )

        s.headers.update({'User-Agent': user_agent})
        s.headers.update({"origin": "https://servicos.dnit.gov.br"})
        s.headers.update({"host": "servicos.dnit.gov.br"})

        # =================================================
        # COOKIES
        # =================================================
        load_cookies(navegador, s)

        navegador.refresh()

        acessa_sior(navegador)

        # =================================================
        # VERIFICA LOGIN
        # =================================================
        if not elemento_existe(
                navegador,
                By.XPATH,
                '//*[@id="center-pane"]/div/div/div[1]/div[2]'
        ):
            log_print("🔐 Login manual necessário. Abrindo navegador visível... REALIZE O LOGIN CONFORME VÍDEO")

            log_print("A Conexão via WIFI poderá impactar no desempenho da automação.")

            log_print("Se possível, conecte via cabo de rede.")

            log_print("https://drive.google.com/file/d/1RoblMwNnSIzX9-g-NKIQP3WDsytV8d6c/view")

            navegador.quit()

            # =============================================
            # VISÍVEL
            # =============================================
            options_visivel = option_navegador(headless=False)
            options_visivel.page_load_strategy = "eager"

            navegador = webdriver.Chrome(options=options_visivel)

            sucesso_login_page = safe_get(
                navegador=navegador,
                url="https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F",
                elemento_validacao=(
                    By.TAG_NAME,
                    "body"
                ),
                tentativas=3,
                timeout_get=25,
                timeout_elemento=15
            )

            if not sucesso_login_page:
                raise Exception("Falha ao abrir SIOR em modo visível")

            acessa_sior(navegador)

            login(navegador)

            log_print("⏳ Aguarde o login manual...")

            time.sleep(2)

            # salva cookies
            store_cookies(navegador)

            navegador.quit()

            log_print("🔁 Reiniciando navegador headless...")

            # =============================================
            # HEADLESS NOVAMENTE
            # =============================================
            options_headless = option_navegador(headless=True)
            options_headless.page_load_strategy = "eager"

            navegador = webdriver.Chrome(options=options_headless)

            sucesso_login_page = safe_get(
                navegador=navegador,
                url="https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F",
                elemento_validacao=(
                    By.TAG_NAME,
                    "body"
                ),
                tentativas=3,
                timeout_get=25,
                timeout_elemento=15
            )

            if not sucesso_login_page:
                raise Exception("Falha ao reiniciar SIOR")

            load_cookies(navegador, s)

            navegador.refresh()

        # =================================================
        # TELA INICIAL
        # =================================================
        resultado = acessa_tela_incial_auto(navegador)

        if resultado == 1:
            raise Exception("Falha ao acessar tela inicial do auto")

        log_print("📄 Tela inicial carregada.")

        return navegador, s

    except Exception as e:

        print(f"Erro ao acessar navegador: {e}")

        if log:
            log.value += f"\n❌ Erro ao iniciar sessão: {e}"

        try:
            navegador.quit()
        except Exception:
            pass

        return None, None