import os

import os

# ==========================================================
# PERFIL / CANAL DA APLICAÇÃO
# ==========================================================

APP_PROFILE = os.getenv("SIOR_APP_PROFILE", "USUARIO").upper()

PERFIL_USUARIO = "USUARIO"
PERFIL_ADMIN = "ADMIN"

IS_ADMIN = APP_PROFILE == PERFIL_ADMIN
IS_USUARIO = APP_PROFILE == PERFIL_USUARIO


# ==========================================================
# VERSIONAMENTO
# ==========================================================

BASE_VERSION = "1.4.1"

VERSAO_USUARIO = f"{BASE_VERSION}"
VERSAO_ADMIN = f"{BASE_VERSION}-admin"

current_version = VERSAO_ADMIN if IS_ADMIN else VERSAO_USUARIO


# ==========================================================
# URLS DE ATUALIZAÇÃO POR PERFIL
# ==========================================================

URL_VERSAO_USUARIO = "https://dsantosa0806.github.io/Flet/version_usuario.json"
URL_VERSAO_ADMIN = "https://dsantosa0806.github.io/Flet/version_admin.json"

URL_VERSAO = URL_VERSAO_ADMIN if IS_ADMIN else URL_VERSAO_USUARIO


# ==========================================================
# TÍTULO DA APLICAÇÃO
# ==========================================================

APP_TITLE_BASE = "RPA Search Data"

APP_TITLE = (
    f"{APP_TITLE_BASE} - Admin"
    if IS_ADMIN
    else f"{APP_TITLE_BASE} - Usuário"
)

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

# Constantes de estilo
DEFAULT_FONT_SIZE = 12
HEADING_FONT_SIZE = 16
PAGE_TITLE_SIZE = 10
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 1024
APP_TITLE = "RPA Search Data"

