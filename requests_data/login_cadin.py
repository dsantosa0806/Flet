# ===================[ CADIN – LOGIN SIMPLIFICADO ]===================
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ========================== CONFIG ==========================
CADIN_URL_HOME = "https://cadin.pgfn.gov.br/"
CADIN_URL_LOGIN = "https://cadin.pgfn.gov.br/autenticacao"

HEADLESS_DEFAULT = False  # mantém visível para permitir login GOV.BR


# ====================== OPÇÕES DO NAVEGADOR ======================
def option_navegador(headless: bool = HEADLESS_DEFAULT):
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
    return options


# ============================ LOGIN ============================
def login(navegador) -> int:
    """Fluxo de login CADIN via gov.br (com confirmação visual e de URL)."""
    try:
        navegador.get(CADIN_URL_LOGIN)
        WebDriverWait(navegador, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        alternativas_btn = [
            "//button[contains(., 'Entrar com gov.br')]",
            "//a[contains(., 'Entrar com gov.br')]",
            "//button[contains(@class,'govbr')]",
        ]

        clicked = False
        for xp in alternativas_btn:
            try:
                WebDriverWait(navegador, 25).until(EC.element_to_be_clickable((By.XPATH, xp))).click()
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            print("⚠️ Botão 'Entrar com gov.br' não encontrado.")
            return 1

        print("📱 Escaneie o QR Code do gov.br para autenticação no CADIN...")

        # 🔹 Aguarda redirecionamento dinâmico
        WebDriverWait(navegador, 180).until(EC.url_contains("principal"))
        print("🔄 Redirecionamento detectado (URL contém 'principal').")

        # 🔹 Aguarda elemento de cabeçalho ou avatar
        seletor_cabecalho = "//div[contains(@class,'header-title') and contains(.,'Cadin')]"
        seletor_avatar = "//button[contains(@id,'avatar-dropdown-trigger')]"

        WebDriverWait(navegador, 60).until(
            EC.any_of(
                EC.visibility_of_element_located((By.XPATH, seletor_cabecalho)),
                EC.visibility_of_element_located((By.XPATH, seletor_avatar))
            )
        )

        print("✅ Login CADIN confirmado (interface carregada).")
        return 0

    except Exception as ex:
        print(f"❌ Erro durante o login CADIN: {ex}")
        return 1


# ============================ ACESSO ============================
def abrir_cadin():
    """
    Abre o navegador Chrome, realiza o login manual e retorna o navegador logado.
    """
    print("🌐 Iniciando navegador do CADIN...")
    navegador = webdriver.Chrome(options=option_navegador(headless=False))

    print("🔓 Acessando tela de login...")
    resultado = login(navegador)

    if resultado != 0:
        print("❌ Falha no login. Verifique se o QR Code foi autenticado corretamente.")
        navegador.quit()
        raise RuntimeError("Falha ao realizar login no CADIN.")

    print("✅ Login confirmado — navegador pronto para uso nas requisições.")
    return navegador


# ===================[ FIM – LOGIN CADIN ]===================
