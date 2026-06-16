from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    SessionNotCreatedException,
)
from selenium import webdriver

import requests
import config
import os
import json
import time
import subprocess
import shutil
import threading
import atexit


# =========================================================
# CONFIGURAÇÕES GERAIS
# =========================================================

caminho_padrao = config.caminho_padrao

SIOR_BASE_URL = "https://servicos.dnit.gov.br"
SIOR_LOGIN_URL = "https://servicos.dnit.gov.br/sior/Account/Login/?ReturnUrl=%2Fsior%2F"

SIOR_TELA_INICIAL_AUTO_URL = (
    "https://servicos.dnit.gov.br/sior/Infracao/"
    "ConsultaAutoInfracao/?SituacoesInfracaoSelecionadas=0"
)

LOGADO_XPATH = '//*[@id="center-pane"]/div/div/div[1]/div[2]'

# Pasta exclusiva do perfil persistente do Chrome para o SIOR.
# Não use o perfil pessoal do Chrome aqui.
SIOR_PROFILE_DIR = getattr(
    config,
    "SIOR_PROFILE_DIR",
    os.getenv("SIOR_PROFILE_DIR", r"C:\Selenium-Profiles\SIOR")
)

SIOR_PROFILE_NAME = getattr(
    config,
    "SIOR_PROFILE_NAME",
    os.getenv("SIOR_PROFILE_NAME", "Default")
)

# Pasta do fallback em cookies JSON.
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
# REGISTRO GLOBAL DE NAVEGADORES SIOR
# =========================================================

_NAVEGADORES_SIOR = {}
_NAVEGADORES_SIOR_LOCK = threading.Lock()


def registrar_navegador_sior(navegador):
    """
    Registra uma instância Selenium criada pelo SIOR.
    Isso permite encerrar o navegador caso o usuário feche a aplicação Flet.
    """
    if navegador:
        try:
            with _NAVEGADORES_SIOR_LOCK:
                _NAVEGADORES_SIOR[id(navegador)] = navegador
        except Exception:
            pass

    return navegador


def desregistrar_navegador_sior(navegador):
    """
    Remove o navegador do registro global.
    """
    if navegador:
        try:
            with _NAVEGADORES_SIOR_LOCK:
                _NAVEGADORES_SIOR.pop(id(navegador), None)
        except Exception:
            pass


def encerrar_navegador_sior(navegador, log=None):
    """
    Encerra com segurança uma instância Selenium do SIOR.
    """
    if not navegador:
        return

    try:
        navegador.quit()
        _log(log, "✅ Navegador SIOR encerrado.")
    except Exception as ex:
        _log(log, f"⚠️ Falha ao encerrar navegador SIOR: {ex}")
    finally:
        desregistrar_navegador_sior(navegador)


def finalizar_navegadores_sior(log=None):
    """
    Encerra todos os navegadores SIOR registrados.

    Esta função deve ser chamada:
    - ao fechar a aplicação Flet;
    - no atexit;
    - antes de abrir novo navegador, se necessário.
    """

    try:
        with _NAVEGADORES_SIOR_LOCK:
            navegadores = list(_NAVEGADORES_SIOR.values())
            _NAVEGADORES_SIOR.clear()

        for navegador in navegadores:
            try:
                navegador.quit()
                _log(log, "✅ Navegador SIOR finalizado no fechamento da aplicação.")
            except Exception as ex:
                _log(log, f"⚠️ Falha ao finalizar navegador SIOR: {ex}")

    except Exception as ex:
        _log(log, f"⚠️ Erro ao finalizar navegadores registrados do SIOR: {ex}")

    # Camada extra: limpa processos órfãos e locks do perfil, caso você já tenha essas funções.
    try:
        limpar_processos_sior_profile(log=log)
    except Exception:
        pass

    try:
        limpar_locks_perfil_sior(log=log)
    except Exception:
        pass


def finalizar_navegadores_sior_imediato(log=None):
    """
    Fechamento imediato para uso exclusivo ao fechar o app.

    Não usa navegador.quit().
    Não remove locks.
    Não faz varredura PowerShell.
    Apenas dispara taskkill assíncrono nos ChromeDrivers registrados.

    O /T mata também os Chromes filhos do ChromeDriver.
    """

    pids = []

    try:
        with _NAVEGADORES_SIOR_LOCK:
            navegadores = list(_NAVEGADORES_SIOR.values())
            _NAVEGADORES_SIOR.clear()
    except Exception:
        navegadores = []

    for navegador in navegadores:
        try:
            pid = None

            try:
                pid = navegador.service.process.pid
            except Exception:
                pass

            if pid:
                pids.append(pid)

        except Exception:
            pass

    if not pids:
        return

    for pid in pids:
        try:
            if os.name == "nt":
                subprocess.Popen(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen(
                    ["kill", "-9", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
        except Exception as ex:
            _log(log, f"⚠️ Falha ao disparar fechamento imediato do PID {pid}: {ex}")


# Garante limpeza em encerramentos normais do Python
atexit.register(finalizar_navegadores_sior_imediato)


# =========================================================
# HELPERS DE LOG
# =========================================================

def _log(log, mensagem: str):
    """
    Compatível com:
    - função callback: log("mensagem")
    - componente Flet TextField/Text: log.value += ...
    - None
    """
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


# =========================================================
# HELPERS DE PASTAS / COOKIES
# =========================================================

def _garantir_pastas():
    os.makedirs(SIOR_PROFILE_DIR, exist_ok=True)
    os.makedirs(SIOR_COOKIES_DIR, exist_ok=True)

def _normalizar_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(path or ""))


def limpar_processos_sior_profile(log=None):
    """
    Encerra somente processos do Chrome/ChromeDriver associados ao perfil persistente do SIOR.

    Essa limpeza evita erro:
    - user data directory is already in use
    - DevToolsActivePort file doesn't exist
    - Chrome failed to start: crashed
    """

    perfil_normalizado = _normalizar_path(SIOR_PROFILE_DIR)
    processos_finalizados = 0

    try:
        # Usa PowerShell para localizar processos Chrome/ChromeDriver
        # cujo CommandLine contenha o caminho do perfil SIOR.
        comando = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            f"""
            $perfil = '{SIOR_PROFILE_DIR.replace("'", "''")}'
            Get-CimInstance Win32_Process |
            Where-Object {{
                ($_.Name -match 'chrome|chromedriver') -and
                ($_.CommandLine -like "*$perfil*")
            }} |
            ForEach-Object {{
                try {{
                    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                    Write-Output $_.ProcessId
                }} catch {{}}
            }}
            """
        ]

        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )

        linhas = [l for l in resultado.stdout.splitlines() if l.strip()]
        processos_finalizados = len(linhas)

        if processos_finalizados:
            _log(log, f"🧹 Processos Chrome/ChromeDriver do perfil SIOR encerrados: {processos_finalizados}")

    except Exception as ex:
        _log(log, f"⚠️ Não foi possível limpar processos do perfil SIOR: {ex}")

    return processos_finalizados


def limpar_locks_perfil_sior(log=None):
    """
    Remove arquivos de lock deixados no perfil persistente após fechamento inesperado.

    Não remove cookies nem dados de sessão.
    """

    arquivos_lock = [
        "SingletonLock",
        "SingletonCookie",
        "SingletonSocket",
        "DevToolsActivePort",
    ]

    removidos = 0

    try:
        if not os.path.exists(SIOR_PROFILE_DIR):
            return 0

        for nome in arquivos_lock:
            caminho = os.path.join(SIOR_PROFILE_DIR, nome)

            if os.path.exists(caminho):
                try:
                    if os.path.isdir(caminho):
                        shutil.rmtree(caminho, ignore_errors=True)
                    else:
                        os.remove(caminho)

                    removidos += 1
                except Exception:
                    pass

        if removidos:
            _log(log, f"🧽 Locks do perfil SIOR removidos: {removidos}")

    except Exception as ex:
        _log(log, f"⚠️ Falha ao limpar locks do perfil SIOR: {ex}")

    return removidos


def finalizar_navegadores_sior(log=None):
    """
    Função pública para ser chamada pelo app.py ao fechar a aplicação.
    """
    limpar_processos_sior_profile(log=log)
    limpar_locks_perfil_sior(log=log)


def _cookies_path(directory: str = SIOR_COOKIES_DIR, filename: str = SIOR_COOKIES_FILE) -> str:
    return os.path.join(directory, filename)


def _normalizar_cookie_para_selenium(cookie: dict) -> dict:
    """
    Evita erro no navegador.add_cookie() por campos incompatíveis.
    """
    chaves_validas = {
        "name",
        "value",
        "domain",
        "path",
        "expiry",
        "secure",
        "httpOnly",
        "sameSite",
    }

    cookie_limpo = {
        k: v
        for k, v in cookie.items()
        if k in chaves_validas and v is not None
    }

    # Alguns cookies podem vir com sameSite inválido para o Selenium.
    if cookie_limpo.get("sameSite") not in ("Strict", "Lax", "None"):
        cookie_limpo.pop("sameSite", None)

    # Selenium espera expiry como inteiro.
    if "expiry" in cookie_limpo:
        try:
            cookie_limpo["expiry"] = int(cookie_limpo["expiry"])
        except Exception:
            cookie_limpo.pop("expiry", None)

    return cookie_limpo


def _set_cookie_requests(s: requests.Session, cookie: dict):
    """
    Injeta cookie do Selenium/JSON na sessão requests.
    """
    if not s:
        return

    nome = cookie.get("name")
    valor = cookie.get("value")

    if not nome or valor is None:
        return

    dominio = cookie.get("domain")
    path = cookie.get("path", "/")

    try:
        if dominio:
            s.cookies.set(nome, valor, domain=dominio, path=path)
        else:
            s.cookies.set(nome, valor)
    except Exception:
        try:
            s.cookies.set(nome, valor)
        except Exception:
            pass


def store_cookies(
        navegador,
        directory: str = SIOR_COOKIES_DIR,
        filename: str = SIOR_COOKIES_FILE
):
    """
    Salva cookies atuais do navegador em cookies.json.
    Também serve como fallback caso o perfil persistente falhe ou expire.
    """
    try:
        os.makedirs(directory, exist_ok=True)

        cookies_file = _cookies_path(directory, filename)
        cookies = navegador.get_cookies()

        with open(cookies_file, "w", encoding="utf-8") as file:
            json.dump(cookies, file, ensure_ascii=False, indent=4)

        print(f"🍪 Cookies salvos em: {cookies_file}")
        return cookies_file

    except Exception as e:
        print(f"Erro ao salvar cookies: {e}")
        return None


def load_cookies(
        navegador=None,
        s: requests.Session = None,
        directory: str = SIOR_COOKIES_DIR,
        filename: str = SIOR_COOKIES_FILE,
        injetar_no_navegador: bool = False
):
    """
    Carrega cookies do cookies.json.

    Regra segura:
    - Por padrão, usa cookies.json APENAS no requests.Session.
    - Não injeta cookies no Selenium, porque o navegador já usa perfil persistente.
    - A injeção no Selenium só ocorre se injetar_no_navegador=True.
    """

    cookies_file = _cookies_path(directory, filename)

    if not os.path.exists(cookies_file):
        print("ℹ️ Arquivo de cookies não encontrado.")
        return []

    try:
        with open(cookies_file, "r", encoding="utf-8") as file:
            cookies = json.load(file)

        total_requests = 0
        total_selenium = 0

        # =====================================================
        # 1. SEMPRE alimenta o requests.Session
        # =====================================================
        if s:
            for cookie in cookies:
                try:
                    _set_cookie_requests(s, cookie)
                    total_requests += 1
                except Exception:
                    pass

        # =====================================================
        # 2. Só injeta no Selenium se for explicitamente pedido
        # =====================================================
        if injetar_no_navegador and navegador:
            try:
                url_atual = navegador.current_url or ""

                if "servicos.dnit.gov.br" not in url_atual:
                    navegador.set_page_load_timeout(10)
                    try:
                        navegador.get(SIOR_BASE_URL)
                    except TimeoutException:
                        try:
                            navegador.execute_script("window.stop();")
                        except Exception:
                            pass

                for cookie in cookies:
                    try:
                        cookie_limpo = _normalizar_cookie_para_selenium(cookie)

                        if cookie_limpo.get("name") and cookie_limpo.get("value") is not None:
                            navegador.add_cookie(cookie_limpo)
                            total_selenium += 1

                    except Exception:
                        pass

            except Exception as ex:
                print(f"⚠️ Falha ao injetar cookies no Selenium: {ex}")

        print(
            f"✅ Cookies carregados do JSON. "
            f"Requests: {total_requests}/{len(cookies)} | "
            f"Selenium: {total_selenium}/{len(cookies)}"
        )

        return cookies

    except Exception as e:
        print(f"Erro ao carregar cookies: {e}")
        return []


def sincronizar_cookies_navegador_para_session(navegador, s: requests.Session) -> int:
    """
    Copia cookies existentes no navegador, inclusive os vindos do perfil persistente,
    para a requests.Session.
    """
    if not navegador or not s:
        return 0

    try:
        cookies = navegador.get_cookies()
    except Exception:
        return 0

    total = 0

    for cookie in cookies:
        try:
            _set_cookie_requests(s, cookie)
            total += 1
        except Exception:
            pass

    return total


def configurar_headers_session(navegador, s: requests.Session):
    """
    Define headers básicos da sessão requests usando o User-Agent real do navegador.
    """
    try:
        user_agent = navegador.execute_script("return navigator.userAgent;")
    except Exception:
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    s.headers.update({
        "User-Agent": user_agent,
        "origin": "https://servicos.dnit.gov.br",
        "host": "servicos.dnit.gov.br",
        "referer": SIOR_LOGIN_URL,
    })


# =========================================================
# OPÇÕES DO NAVEGADOR COM PERFIL PERSISTENTE
# =========================================================

def option_navegador(headless=True, usar_perfil=True):
    """
    Cria ChromeOptions otimizado para abertura rápida.

    Estratégia:
    - Headless: usa page_load_strategy = "none" para não esperar carregamento completo.
    - Visível: mantém page_load_strategy = "eager", mais seguro para login manual e QR Code.
    - Perfil persistente continua ativo.
    - cookies.json continua sendo usado como fallback para requests.Session.
    """

    _garantir_pastas()

    options = webdriver.ChromeOptions()

    if usar_perfil:
        options.add_argument(f"--user-data-dir={SIOR_PROFILE_DIR}")
        options.add_argument(f"--profile-directory={SIOR_PROFILE_NAME}")

    # =====================================================
    # FLAGS BÁSICAS
    # =====================================================
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--use_subprocess")

    # =====================================================
    # FLAGS PARA REDUZIR TRABALHO INICIAL DO CHROME
    # =====================================================
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-domain-reliability")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--log-level=3")

    options.add_argument(
        "--disable-features="
        "Translate,"
        "OptimizationHints,"
        "MediaRouter,"
        "DialMediaRouteProvider,"
        "AutofillServerCommunication"
    )

    # =====================================================
    # PAGE LOAD STRATEGY
    # =====================================================
    if headless:
        # Mais rápido: o get() retorna quase imediatamente.
        # A validação passa a ser feita pelo safe_get().
        options.page_load_strategy = "none"
        options.add_argument("--headless=new")

        # No headless, não precisamos renderizar imagens.
        options.add_argument("--blink-settings=imagesEnabled=false")
    else:
        # Mais seguro para login manual, QR Code e GOV.BR.
        options.page_load_strategy = "eager"

    # =====================================================
    # PREFERÊNCIAS
    # =====================================================
    options.add_experimental_option("prefs", {
        "download.default_directory": config.caminho_padrao,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,

        # Evita prompts desnecessários
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    })

    # Reduz logs e mensagens de automação
    options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    return options


def aplicar_otimizacoes_cdp(navegador, headless=True):
    """
    Aplica bloqueios via Chrome DevTools Protocol.

    No headless, bloqueia recursos que pesam no primeiro carregamento.
    Não bloqueia JS nem CSS para evitar quebrar o SIOR.
    """

    if not headless:
        return

    try:
        navegador.execute_cdp_cmd("Network.enable", {})

        navegador.execute_cdp_cmd("Network.setBlockedURLs", {
            "urls": [
                "*.png",
                "*.jpg",
                "*.jpeg",
                "*.gif",
                "*.webp",
                "*.ico",
                "*.svg",
                "*.woff",
                "*.woff2",
                "*.ttf",
                "*google-analytics*",
                "*googletagmanager*",
                "*doubleclick*",
            ]
        })

    except Exception:
        pass


def criar_navegador(headless=True, log=None):
    """
    Cria o webdriver com perfil persistente e otimizações de carregamento.
    """
    try:
        # Limpeza preventiva para evitar perfil travado após fechamento inesperado.
        limpar_processos_sior_profile(log=log)
        limpar_locks_perfil_sior(log=log)

        time.sleep(0.5)

        options = option_navegador(headless=headless, usar_perfil=True)
        navegador = webdriver.Chrome(options=options)
        registrar_navegador_sior(navegador)

        aplicar_otimizacoes_cdp(navegador, headless=headless)

        if headless:
            navegador.set_page_load_timeout(12)
        else:
            navegador.set_page_load_timeout(30)

        return navegador

    except SessionNotCreatedException as e:
        msg = str(e)

        if (
                "user data directory is already in use" in msg.lower()
                or "profile" in msg.lower()
                or "cannot create default profile directory" in msg.lower()
        ):
            mensagem = (
                "❌ Não foi possível abrir o Chrome com o perfil persistente do SIOR.\n"
                "Provável causa: já existe outro Chrome/RPA usando o perfil:\n"
                f"{SIOR_PROFILE_DIR}\n\n"
                "Feche todas as janelas do Chrome abertas por esta automação e tente novamente."
            )
            _log(log, mensagem)
            raise RuntimeError(mensagem)

        raise

    except WebDriverException as e:
        mensagem = f"❌ Erro ao criar navegador Chrome: {e}"
        _log(log, mensagem)
        raise RuntimeError(mensagem)


# =========================================================
# ACESSO / LOGIN
# =========================================================

def acessa_sior(navegador):
    """
    Mantida para compatibilidade com outras partes do projeto.
    Preferencialmente, no fluxo principal, use safe_get(SIOR_LOGIN_URL)
    para evitar carregamentos duplicados.
    """
    try:
        navegador.set_page_load_timeout(12)

        try:
            navegador.get(SIOR_LOGIN_URL)
        except TimeoutException:
            print("⚠️ Timeout no carregamento → forçando stop")
            navegador.execute_script("window.stop();")

        WebDriverWait(navegador, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        try:
            WebDriverWait(navegador, 8).until(
                lambda d: d.execute_script("return document.readyState") in ["interactive", "complete"]
            )
        except Exception:
            pass

    except Exception as e:
        print(f"Erro ao acessar SIOR: {e}")
        raise RuntimeError("Falha ao acessar SIOR")


def login(navegador):
    path_btn_entrar_gov = '//*[@id="placeholder"]/div[1]/div/div/div/div/div/div/form/div[2]/button'
    qr_code_path = '//*[@id="login-cpf"]/div[5]/a'

    try:
        WebDriverWait(navegador, 120).until(
            EC.presence_of_element_located((By.XPATH, path_btn_entrar_gov))
        ).click()

        WebDriverWait(navegador, 120).until(
            EC.presence_of_element_located((By.XPATH, qr_code_path))
        ).click()

        WebDriverWait(navegador, 180).until(
            EC.presence_of_element_located((By.XPATH, LOGADO_XPATH))
        ).is_displayed()

        return 0

    except Exception as e:
        print(f"Erro no login manual: {e}")
        return 1


def elemento_existe(navegador, by, value):
    try:
        elemento = navegador.find_element(by, value)
        return elemento.is_displayed()
    except NoSuchElementException:
        return False
    except Exception:
        return False


# =========================================================
# SAFE GET OTIMIZADO
# =========================================================

def _aguardar_body_disponivel(navegador, timeout=6):
    """
    Aguarda o document.body existir.
    Útil quando page_load_strategy = none.
    """
    inicio = time.time()

    while time.time() - inicio < timeout:
        try:
            body_existe = navegador.execute_script("return document.body != null")
            if body_existe:
                return True
        except Exception:
            pass

        time.sleep(0.25)

    return False


def safe_get(
        navegador,
        url,
        elemento_validacao=None,
        tentativas=3,
        timeout_get=20,
        timeout_elemento=15,
        tempo_espera=2,
        tempo_estabilizacao=0.7
):
    """
    Acesso seguro e rápido.

    Compatível com:
    - page_load_strategy = none no headless;
    - page_load_strategy = eager no modo visível.

    A validação real passa a ser feita pelo DOM e/ou elemento_validacao.
    """

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

            # Pequena estabilização.
            # Com page_load_strategy=none, não usar sleep alto.
            time.sleep(tempo_estabilizacao)

            # ===================================================
            # TESTE LEVE DE DOM COM ESPERA CURTA
            # ===================================================
            body_ok = _aguardar_body_disponivel(
                navegador,
                timeout=min(6, max(2, timeout_elemento))
            )

            if not body_ok:
                raise Exception("DOM não carregado")

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

                    time.sleep(0.5)

                if not encontrou:
                    if carregamento_interrompido:
                        print("⚠️ Página parcialmente carregada, mas DOM disponível.")
                        return True

                    raise Exception(f"Elemento de validação não encontrado: {value}")

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
    sucesso = safe_get(
        navegador=navegador,
        url=SIOR_TELA_INICIAL_AUTO_URL,
        elemento_validacao=(By.TAG_NAME, "body"),
        tentativas=3,
        timeout_get=15,
        timeout_elemento=8,
        tempo_estabilizacao=0.7
    )

    if not sucesso:
        print("❌ Não foi possível carregar tela inicial.")
        return 1

    return 0


# =========================================================
# SESSÃO REQUESTS
# =========================================================

def preparar_session_requests(navegador):
    """
    Prepara a sessão requests sem travar o navegador.

    Estratégia:
    1. Captura cookies existentes no perfil persistente do Chrome.
    2. Carrega cookies.json apenas para o requests.Session.
    3. Não faz navegador.refresh().
    4. Não injeta cookies.json no Selenium.
    """

    s = requests.Session()

    configurar_headers_session(navegador, s)

    # Cookies vindos do perfil persistente do Chrome.
    total_perfil = sincronizar_cookies_navegador_para_session(navegador, s)

    print(f"🍪 Cookies sincronizados do perfil Chrome para requests: {total_perfil}")

    # Cookies do JSON apenas para requests.Session.
    cookies_json = load_cookies(
        navegador=None,
        s=s,
        injetar_no_navegador=False
    )

    print(f"🍪 Cookies JSON carregados para requests: {len(cookies_json)}")

    return s


# =========================================================
# INICIAR SESSÃO SIOR
# PERFIL PERSISTENTE + COOKIES JSON
# =========================================================

def iniciar_sessao_sior(log=None):
    navegador = None
    s = None

    def log_print(msg):
        _log(log, msg)

    try:
        _garantir_pastas()

        # =================================================
        # 1. TENTA ABRIR HEADLESS COM PERFIL PERSISTENTE
        # =================================================
        navegador = criar_navegador(headless=True, log=log)

        log_print(
            "🧭 Navegador iniciado em modo headless "
            f"com perfil persistente: {SIOR_PROFILE_DIR}"
        )

        sucesso_login_page = safe_get(
            navegador=navegador,
            url=SIOR_LOGIN_URL,
            elemento_validacao=(By.TAG_NAME, "body"),
            tentativas=3,
            timeout_get=15,
            timeout_elemento=8,
            tempo_estabilizacao=0.7
        )

        if not sucesso_login_page:
            raise Exception("Falha ao abrir página inicial do SIOR")

        # Prepara requests sem injetar cookies no Selenium.
        s = preparar_session_requests(navegador)

        # =================================================
        # 2. VERIFICA SE JÁ ESTÁ LOGADO
        # =================================================
        if elemento_existe(navegador, By.XPATH, LOGADO_XPATH):
            log_print("✅ Sessão recuperada pelo perfil persistente.")
            store_cookies(navegador)

        else:
            # =================================================
            # 3. LOGIN MANUAL VISÍVEL COM O MESMO PERFIL
            # =================================================
            log_print("🔐 Login manual necessário. Abrindo navegador visível...")
            log_print("REALIZE O LOGIN CONFORME VÍDEO.")
            log_print("A conexão via WIFI poderá impactar no desempenho da automação.")
            log_print("Se possível, conecte via cabo de rede.")
            log_print("https://drive.google.com/file/d/1RoblMwNnSIzX9-g-NKIQP3WDsytV8d6c/view")

            try:
                encerrar_navegador_sior(navegador, log=log)
                navegador = None
            except Exception:
                pass

            navegador = None

            # Pequena pausa para liberar o perfil do Chrome.
            time.sleep(2)

            navegador = criar_navegador(headless=False, log=log)

            log_print(
                "🧭 Navegador visível iniciado com perfil persistente "
                f"do SIOR: {SIOR_PROFILE_DIR}"
            )

            sucesso_login_page = safe_get(
                navegador=navegador,
                url=SIOR_LOGIN_URL,
                elemento_validacao=(By.TAG_NAME, "body"),
                tentativas=3,
                timeout_get=25,
                timeout_elemento=15,
                tempo_estabilizacao=1
            )

            if not sucesso_login_page:
                raise Exception("Falha ao abrir SIOR em modo visível")

            # IMPORTANTE:
            # Não chamar acessa_sior(navegador) aqui.
            # A página de login já foi aberta pelo safe_get.
            resultado_login = login(navegador)

            if resultado_login == 1:
                log_print("⚠️ O login manual não foi confirmado automaticamente.")
                log_print("⚠️ Verifique se o QR Code foi autenticado corretamente.")

            log_print("⏳ Validando sessão após login manual...")

            time.sleep(2)

            # Salva cookies do navegador visível.
            store_cookies(navegador)

            try:
                encerrar_navegador_sior(navegador, log=log)
                navegador = None
            except Exception:
                pass

            navegador = None

            # Pausa importante para evitar perfil travado.
            time.sleep(2)

            log_print("🔁 Reiniciando navegador headless com o mesmo perfil persistente...")

            # =================================================
            # 4. REINICIA HEADLESS, MAS NÃO INJETA COOKIES NO SELENIUM
            # =================================================
            navegador = criar_navegador(headless=True, log=log)

            sucesso_login_page = safe_get(
                navegador=navegador,
                url=SIOR_LOGIN_URL,
                elemento_validacao=(By.TAG_NAME, "body"),
                tentativas=3,
                timeout_get=15,
                timeout_elemento=8,
                tempo_estabilizacao=0.7
            )

            if not sucesso_login_page:
                raise Exception("Falha ao reiniciar SIOR em modo headless")

            # Prepara nova sessão requests.
            # Aqui o cookies.json entra apenas no requests.Session.
            s = preparar_session_requests(navegador)

            if elemento_existe(navegador, By.XPATH, LOGADO_XPATH):
                log_print("✅ Sessão recuperada no headless após login manual.")
            else:
                log_print("⚠️ Área logada não confirmada visualmente no headless.")
                log_print("⚠️ Tentando acessar diretamente a tela inicial do SIOR...")

        # =================================================
        # 5. ACESSA TELA INICIAL
        # =================================================
        resultado = acessa_tela_incial_auto(navegador)

        if resultado == 1:
            raise Exception("Falha ao acessar tela inicial do auto")

        # Atualiza requests com os cookies atuais do navegador.
        sincronizar_cookies_navegador_para_session(navegador, s)

        # Atualiza cookies.json sem forçar refresh.
        store_cookies(navegador)

        log_print("📄 Tela inicial carregada.")

        return navegador, s

    except Exception as e:
        log_print(f"❌ Erro ao iniciar sessão SIOR: {e}")

        try:
            if navegador:
                encerrar_navegador_sior(navegador, log=log)
                navegador = None
        except Exception:
            pass

        return None, None