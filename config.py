import os

import os

# ==========================================================
# PERFIL / CANAL DA APLICAÇÃO
# ==========================================================

APP_PROFILE = os.getenv("SIOR_APP_PROFILE", "USUARIO").upper()

# ==========================================================
# PERFIL / CANAL DA APLICAÇÃO
# ==========================================================

PERFIL_ADMIN = "ADMIN"
PERFIL_SUPERVISAO = "SUPERVISAO"
PERFIL_TECNICO = "TECNICO"

# Mantido apenas por compatibilidade com builds antigos.
# Daqui para frente, USUARIO passa a ser SUPERVISAO.
PERFIL_USUARIO = PERFIL_SUPERVISAO

PERFIS_VALIDOS = {
    PERFIL_ADMIN,
    PERFIL_SUPERVISAO,
    PERFIL_TECNICO,
}

MAPA_PERFIS_LEGADOS = {
    "USUARIO": PERFIL_SUPERVISAO,
}

APP_PROFILE_RAW = os.getenv(
    "SIOR_APP_PROFILE",
    PERFIL_TECNICO
).upper().strip()

APP_PROFILE = MAPA_PERFIS_LEGADOS.get(
    APP_PROFILE_RAW,
    APP_PROFILE_RAW
)

if APP_PROFILE not in PERFIS_VALIDOS:
    APP_PROFILE = PERFIL_TECNICO

IS_ADMIN = APP_PROFILE == PERFIL_ADMIN
IS_SUPERVISAO = APP_PROFILE == PERFIL_SUPERVISAO
IS_TECNICO = APP_PROFILE == PERFIL_TECNICO

# Compatibilidade com códigos antigos que ainda usam IS_USUARIO.
IS_USUARIO = IS_SUPERVISAO


# ==========================================================
# VERSIONAMENTO
# ==========================================================

BASE_VERSION = "1.4.1"

VERSAO_ADMIN = f"{BASE_VERSION}-admin"
VERSAO_SUPERVISAO = f"{BASE_VERSION}-supervisao"
VERSAO_TECNICO = f"{BASE_VERSION}-tecnico"

VERSOES_POR_PERFIL = {
    PERFIL_ADMIN: VERSAO_ADMIN,
    PERFIL_SUPERVISAO: VERSAO_SUPERVISAO,
    PERFIL_TECNICO: VERSAO_TECNICO,
}

current_version = VERSOES_POR_PERFIL.get(
    APP_PROFILE,
    VERSAO_TECNICO
)


# ==========================================================
# URLS DE ATUALIZAÇÃO POR PERFIL
# ==========================================================

URL_VERSAO_ADMIN = "https://dsantosa0806.github.io/Flet/version_admin.json"
URL_VERSAO_SUPERVISAO = "https://dsantosa0806.github.io/Flet/version_supervisao.json"
URL_VERSAO_TECNICO = "https://dsantosa0806.github.io/Flet/version_tecnico.json"

# Compatibilidade com nome antigo
URL_VERSAO_USUARIO = URL_VERSAO_SUPERVISAO

URLS_VERSAO_POR_PERFIL = {
    PERFIL_ADMIN: URL_VERSAO_ADMIN,
    PERFIL_SUPERVISAO: URL_VERSAO_SUPERVISAO,
    PERFIL_TECNICO: URL_VERSAO_TECNICO,
}

URL_VERSAO = URLS_VERSAO_POR_PERFIL.get(
    APP_PROFILE,
    URL_VERSAO_TECNICO
)


# ==========================================================
# TÍTULO DA APLICAÇÃO
# ==========================================================

APP_TITLE_BASE = "RPA Search Data"

ROTULO_PERFIL = {
    PERFIL_ADMIN: "Admin",
    PERFIL_SUPERVISAO: "Supervisão",
    PERFIL_TECNICO: "Técnico",
}.get(APP_PROFILE, "Técnico")

APP_TITLE = f"{APP_TITLE_BASE} - {ROTULO_PERFIL}"

diretorio = r'C:\\'
pasta_arquivos = r'C:\Extracao-Relatorio-Financeiro-Processo-Arquivos'
pasta_autos = r'C:\Extracao-Relatorio-Financeiro-Processo-Autos'
caminho_padrao = os.path.join(os.path.expanduser("~"), "Downloads")
caminho_destino_padrao = r'C:\Extracao-Relatorio-Financeiro-Processo-Arquivos'
COOKIE_PATH = r'C:\Cookies-Selenium\cookies_sapiens.json'
COOKIE_PATH_SAPIENS = os.path.join(os.path.expanduser("~"), ".sapiens_cache.json")
CACHE_PATH_SUPERVISOR = os.path.join(os.path.expanduser("~"), ".sior_supervisor_cache.json")
SIOR_PROFILE_DIR = r"C:\Selenium-Profiles\SIOR"
SIOR_PROFILE_NAME = "Default"
SIOR_COOKIES_DIR = r"C:\Cookies-Selenium"
SIOR_COOKIES_FILE = "cookies.json"
PASTA_EXPORT_ADMIN = r"C:\Downloads"

# Constantes de estilo
DEFAULT_FONT_SIZE = 12
HEADING_FONT_SIZE = 16
PAGE_TITLE_SIZE = 10
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 1024

# ==========================================================
# LICENCIAMENTO / RENOVAÇÃO BIMESTRAL
# ==========================================================

URL_LICENCA_ADMIN = "https://dsantosa0806.github.io/Flet/licenca_admin.json"
URL_LICENCA_SUPERVISAO = "https://dsantosa0806.github.io/Flet/licenca_supervisao.json"
URL_LICENCA_TECNICO = "https://dsantosa0806.github.io/Flet/licenca_tecnico.json"

# Compatibilidade com nome antigo
URL_LICENCA_USUARIO = URL_LICENCA_SUPERVISAO

URLS_LICENCA_POR_PERFIL = {
    PERFIL_ADMIN: URL_LICENCA_ADMIN,
    PERFIL_SUPERVISAO: URL_LICENCA_SUPERVISAO,
    PERFIL_TECNICO: URL_LICENCA_TECNICO,
}

URL_LICENCA = URLS_LICENCA_POR_PERFIL.get(
    APP_PROFILE,
    URL_LICENCA_TECNICO
)


# ==========================================================
# CACHE LOCAL DA LICENÇA
# ==========================================================

LICENCA_CACHE_PATH = os.path.join(
    os.path.expanduser("~"),
    ".rpa_search_data_licenca.json"
)


# ==========================================================
# SALT USADO NA GERAÇÃO DOS HASHES
# ==========================================================
# IMPORTANTE:
# - Troque esse texto por uma frase própria antes de compilar.
# - Use o mesmo valor ao gerar o hash no tools/gerar_hash_licenca.py.
# - Se mudar o SALT depois de gerar o hash, a senha deixará de validar.

LICENCA_SALT = os.getenv(
    "RPA_LICENSE_SALT",
    "Contrato247/2024RpaSearchData"
)


# ==========================================================
# TOLERÂNCIA OFFLINE
# ==========================================================
# Se o GitHub Pages não responder, permite usar o cache local
# por alguns dias após a última validação online.

LICENCA_TOLERANCIA_OFFLINE_DIAS = 3


# ==========================================================
# REGISTRO OPCIONAL DE MÁQUINA - GOOGLE APPS SCRIPT
# ==========================================================
# Recomendado:
# - URL e SECRET via variável de ambiente.
# - Evita deixar segredo fixo no código.
#
# Se quiser deixar desativado, mantenha os valores vazios.

