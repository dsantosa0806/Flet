# ===================[ SUPER SAPIENS – LOGIN / TOKEN ]===================
import os
import json
import base64
import time
from datetime import datetime, timezone
from typing import List, Optional, Tuple

# Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ========================== CONFIG ==========================
COOKIES_DIR: str  = os.getenv("SS_COOKIES_DIR", r"C:\Cookies-Selenium-SuperSapiens")
COOKIES_FILE: str = os.getenv("SS_COOKIES_FILE", "cookies.json")
TOKEN_FILE: str   = os.getenv("SS_TOKEN_FILE", "token.json")

# Headless padrão (usado apenas quando já existe sessão/token; para login mostramos o automation)
HEADLESS_DEFAULT: bool = os.getenv("SS_HEADLESS", "0") in {"1", "true", "True"}

# Janela de segurança do token
SKEW_SECONDS: int    = int(os.getenv("SS_TOKEN_SKEW", "200"))
MIN_TTL_SECONDS: int = int(os.getenv("SS_MIN_TTL_SECONDS", "0"))

# URLs principais
SUPERSAPIENS_URL_HOME: str   = "https://supersapiens.agu.gov.br/"
SUPERSAPIENS_URL_DIVIDA: str = "https://supersapiens.agu.gov.br/apps/divida"


# ========================== JWT / TOKEN ==========================
def _parece_jwt(token: str) -> bool:
    """Verificação leve para formato de JWT."""
    return isinstance(token, str) and token.startswith("eyJ") and len(token.split(".")) == 3


def _b64url_decode(data: str) -> bytes:
    """Decodifica base64 URL-safe, ajustando padding."""
    rem = len(data) % 4
    if rem:
        data += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data.encode("utf-8"))


def _jwt_payload(token: str) -> Optional[dict]:
    """Retorna o payload do JWT (ou None em falha)."""
    try:
        payload_b64 = token.split(".")[1]
        decoded = _b64url_decode(payload_b64)
        return json.loads(decoded.decode("utf-8"))
    except Exception:
        return None


def _jwt_exp_and_iat(token: str) -> Tuple[Optional[int], Optional[int]]:
    """Extrai exp/iat do JWT (epoch segundos)."""
    payload = _jwt_payload(token)
    if not payload:
        return None, None
    return payload.get("exp"), payload.get("iat")


def token_valido(token: Optional[str], skew_seconds: int = SKEW_SECONDS, min_ttl: int = MIN_TTL_SECONDS) -> bool:
    """
    Considera válido se:
      • é um JWT, possui 'exp'
      • faltam mais do que max(skew_seconds, min_ttl) segundos para expirar
    """
    if not token or not _parece_jwt(token):
        return False
    exp, _ = _jwt_exp_and_iat(token)
    if not exp:
        return False
    agora = int(datetime.now(tz=timezone.utc).timestamp())
    ttl = exp - agora
    return ttl > max(skew_seconds, min_ttl)


# ======================= TOKEN EM ARQUIVO =======================
def _token_path() -> str:
    """Caminho do arquivo de token persistido."""
    os.makedirs(COOKIES_DIR, exist_ok=True)
    return os.path.join(COOKIES_DIR, TOKEN_FILE)


def salvar_token_em_arquivo(token: str) -> None:
    """Salva o token e metadados em token.json."""
    if not _parece_jwt(token):
        return
    exp, iat = _jwt_exp_and_iat(token)
    data = {
        "token": token,
        "exp": exp,
        "iat": iat,
        "payload": _jwt_payload(token) or {},
        "salvo_em": datetime.now(tz=timezone.utc).isoformat(),
    }
    with open(_token_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def carregar_token_de_arquivo() -> Optional[str]:
    """Carrega o token de token.json (retorna None se ausente/expirado)."""
    path = _token_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        token = data.get("token")
        return token if token and token_valido(token) else None
    except Exception:
        return None


# ======================== COOKIES (SELENIUM) =======================
def store_cookies(navegador, directory: str = COOKIES_DIR, filename: str = COOKIES_FILE) -> None:
    """Persiste cookies do automation para agilizar próximas execuções."""
    os.makedirs(directory, exist_ok=True)
    caminho = os.path.join(directory, filename)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(navegador.get_cookies(), f, ensure_ascii=False, indent=2)
    print(f"🍪 Cookies salvos em: {caminho}")


def load_cookies(navegador, directory: str = COOKIES_DIR, filename: str = COOKIES_FILE) -> List[dict]:
    """Carrega cookies (se existirem) e injeta no automation."""
    caminho = os.path.join(directory, filename)
    if not os.path.exists(caminho):
        print("ℹ️  Arquivo de cookies não encontrado (login pode ser necessário).")
        return []
    with open(caminho, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    try:
        navegador.get(SUPERSAPIENS_URL_HOME)
    except Exception:
        pass

    ok = 0
    for cookie in cookies:
        clean = {k: v for k, v in cookie.items() if k in {"name", "value", "domain", "path", "expiry", "secure"}}
        try:
            navegador.add_cookie(clean)
            ok += 1
        except Exception:
            continue
    print(f"✅ Cookies carregados ({ok}/{len(cookies)}).")
    return cookies


# ======================= EXTRAÇÃO DO JWT (WEB) =======================
def _extrair_jwt_de_texto(texto: str) -> Optional[str]:
    """Tenta localizar um JWT em um texto bruto (JSON/string)."""
    if not isinstance(texto, str):
        return None
    if _parece_jwt(texto):
        return texto
    # chaves comuns onde o token pode aparecer serializado
    for chave in ("access_token", "token", "jwt", "id_token", "Authorization", "auth._token.local", "auth.token"):
        marcador = f'"{chave}":"'
        if marcador in texto:
            pedaco = texto.split(marcador, 1)[-1]
            candidato = pedaco.split('"', 1)[0]
            if _parece_jwt(candidato):
                return candidato
    return None


def extrair_bearer_do_navegador(navegador, cookies: List[dict]) -> Optional[str]:
    """
    Captura o JWT a partir de:
      1) cookies conhecidos; 2) localStorage/sessionStorage; 3) variáveis globais comuns.
    """
    suspeitos = {
        "Authorization", "authorization", "token", "access_token", "id_token",
        "ssoGovBr", "SSOGOVBR", "supersapiens_token", "auth._token.local", "auth.token",
    }

    # 1) cookies
    for c in cookies or []:
        valor = c.get("value", "")
        nome  = c.get("name", "")
        if nome in suspeitos and _parece_jwt(valor):
            return valor
        if isinstance(valor, str) and valor.lower().startswith("bearer "):
            possivel = valor.split(" ", 1)[1].strip()
            if _parece_jwt(possivel):
                return possivel
        if _parece_jwt(valor):
            return valor

    # 2) local/sessionStorage + globais
    try:
        raw = navegador.execute_script("""
          const out = { localStorage:{}, sessionStorage:{}, globals:{} };
          for (let i=0;i<localStorage.length;i++){ const k=localStorage.key(i); out.localStorage[k]=localStorage.getItem(k); }
          for (let i=0;i<sessionStorage.length;i++){ const k=sessionStorage.key(i); out.sessionStorage[k]=sessionStorage.getItem(k); }
          out.globals.__env = (window.__env ? JSON.stringify(window.__env) : null);
          out.globals.__APP_STATE = (window.__APP_STATE ? JSON.stringify(window.__APP_STATE) : null);
          return JSON.stringify(out);
        """)
        store = json.loads(raw)
    except Exception:
        store = {"localStorage": {}, "sessionStorage": {}, "globals": {}}

    def _probe(dct: dict) -> Optional[str]:
        for v in (dct or {}).values():
            if not isinstance(v, str):
                continue
            if v.lower().startswith("bearer "):
                vv = v.split(" ", 1)[1].strip()
                if _parece_jwt(vv):
                    return vv
            if _parece_jwt(v):
                return v
            cand = _extrair_jwt_de_texto(v)
            if cand:
                return cand
        return None

    token = _probe(store.get("localStorage")) or _probe(store.get("sessionStorage"))
    if token:
        return token

    for g in ("__env", "__APP_STATE"):
        gv = (store.get("globals") or {}).get(g)
        if isinstance(gv, str):
            cand = _extrair_jwt_de_texto(gv)
            if cand:
                return cand

    return None


# ====================== NAVEGAÇÃO / LOGIN ======================
def option_navegador(headless: bool = HEADLESS_DEFAULT):
    """Opções padrão do Chrome (diminui fingerprints)"""
    options = webdriver.ChromeOptions()
    options.add_argument("enable-automation")
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--dns-prefetch-disable")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--use_subprocess")
    return options


def acessa_home(navegador) -> None:
    navegador.get(SUPERSAPIENS_URL_HOME)
    time.sleep(1)


def acessa_divida(navegador) -> None:
    navegador.get(SUPERSAPIENS_URL_DIVIDA)
    time.sleep(1)


def login(navegador) -> int:
    """
    ⚠️ Estrutura mantida conforme solicitado.
    Fluxo: clicar em 'Entrar com gov.br' → abrir QR Code → aguardar área logada.
    Retorna 0 em sucesso, 1 em falha.
    """
    path_btn_entrar_gov = '//*[@id="login"]/cdk-login-v2-form/div/div/div[2]/button'
    qr_code_path        = '//*[@id="login-cpf"]/div[5]/a'
    logado              = '//*[@id="container-3"]/content/painel/div[1]/div/div[1]/div[1]/span'

    alternativos_btn = [
        path_btn_entrar_gov,
        "//button[contains(., 'Entrar com gov.br')]",
        "//button[contains(@class, 'govbr')]",
        "//button[contains(translate(., 'ENTRAR', 'entrar'), 'entrar')]",
    ]
    alternativos_qr = [
        qr_code_path,
        "//a[contains(., 'QR Code') or contains(., 'QRcode') or contains(., 'QR')]",
        "//a[contains(@href, 'qrcode')]",
    ]

    try:
        navegador.get("https://supersapiens.agu.gov.br/auth/login?returnUrl=%2Fapps%2Fdivida")
        WebDriverWait(navegador, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # botão "Entrar com gov.br"
        clicked = False
        for xp in alternativos_btn:
            try:
                WebDriverWait(navegador, 30).until(EC.element_to_be_clickable((By.XPATH, xp))).click()
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            print("⚠️  Não localizei o botão 'Entrar com gov.br' (tentativas esgotadas).")
            return 1

        # link "QR Code"
        qr_ok = False
        for xp in alternativos_qr:
            try:
                WebDriverWait(navegador, 30).until(EC.element_to_be_clickable((By.XPATH, xp))).click()
                qr_ok = True
                break
            except Exception:
                continue
        if not qr_ok:
            print("⚠️  Não localizei o link 'QR Code'. Escaneie o QR se aparecer automaticamente.")

        # aguarda a área logada (ou mudança para /apps/*)
        try:
            WebDriverWait(navegador, 120).until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, logado)),
                    EC.url_contains("/apps/")
                )
            )
        except Exception:
            pass

        return 0
    except Exception:
        return 1


def _force_login_and_extract(navegador) -> Optional[str]:
    """
    Dispara o fluxo de login, salva cookies e tenta extrair o JWT.
    Retorna o token (str) ou None.
    """
    print("🔐 Iniciando login GOV.BR (QR)…")
    ok = login(navegador)
    if ok != 0:
        print("⚠️  login() não confirmou a área logada. Prosseguindo com tentativa de extração…")

    try:
        acessa_divida(navegador)
        time.sleep(2)
        navegador.refresh()
        time.sleep(1.5)
    except Exception:
        pass

    try:
        store_cookies(navegador)
    except Exception:
        pass

    try:
        cookies_atual = navegador.get_cookies()
    except Exception:
        cookies_atual = []

    return extrair_bearer_do_navegador(navegador, cookies_atual)


# ======================= OBTENÇÃO DO TOKEN =======================
def obter_token() -> str:
    """
    Estratégia:
      1) Usa token de arquivo, se ainda válido;
      2) Abre Chrome (preferência visível para facilitar auth), injeta cookies e tenta extrair;
      3) Se necessário, força login por QR, salva token e retorna.
    """
    # 1) Arquivo
    token = carregar_token_de_arquivo()
    if token and token_valido(token):
        return token

    # 2) Navegador
    headless = HEADLESS_DEFAULT
    if headless:
        print("ℹ️  Ativando automation visível para facilitar login.")
        headless = False

    navegador = webdriver.Chrome(options=option_navegador(headless))
    try:
        acessa_home(navegador)
        load_cookies(navegador)  # ok se não existir

        # tenta popular storages do app
        try:
            acessa_divida(navegador)
            time.sleep(2)
            navegador.refresh()
            time.sleep(1.5)
        except Exception:
            pass

        # primeira tentativa de captura
        token = extrair_bearer_do_navegador(navegador, navegador.get_cookies())

        # se não encontrou, força login
        try:
            url_atual = navegador.current_url or ""
        except Exception:
            url_atual = ""

        if (not token or not token_valido(token)) or ("/auth/login" in url_atual):
            token = _force_login_and_extract(navegador)

        if not token or not token_valido(token):
            print("❌ Não foi possível capturar JWT após login.")
            raise RuntimeError("Não foi possível obter um JWT válido (arquivo/cookies/login).")

        salvar_token_em_arquivo(token)
        return token

    finally:
        try:
            navegador.quit()
        except Exception:
            pass


# ===================[ FIM – LOGIN / TOKEN ]===================
