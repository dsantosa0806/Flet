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
PASTA_EXPORT_ADMIN = r"C:\Downloads"

# Constantes de estilo
DEFAULT_FONT_SIZE = 12
HEADING_FONT_SIZE = 16
PAGE_TITLE_SIZE = 10
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 1024
APP_TITLE = "RPA Search Data"

# ==========================================================
# LICENCIAMENTO / RENOVAÇÃO BIMESTRAL
# ==========================================================

URL_LICENCA_USUARIO = "https://dsantosa0806.github.io/Flet/licenca_usuario.json"
URL_LICENCA_ADMIN = "https://dsantosa0806.github.io/Flet/licenca_admin.json"

URL_LICENCA = URL_LICENCA_ADMIN if IS_ADMIN else URL_LICENCA_USUARIO


# ==========================================================
# CACHE LOCAL DA LICENÇA
# ==========================================================

LICENCA_CACHE_PATH = os.path.join(
    os.path.expanduser("~"),
    ".rpa_search_data_licenca.json"
)

LICENCA_REGISTRO_CACHE_PATH = os.path.join(
    os.path.expanduser("~"),
    ".rpa_search_data_maquina_registro.json"
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

URL_REGISTRO_MAQUINA = os.getenv(
    "RPA_REGISTRO_MAQUINA_URL",
    ""
)

REGISTRO_MAQUINA_SECRET = os.getenv(
    "RPA_REGISTRO_MAQUINA_SECRET",
    ""
)

URL_REGISTRO_MAQUINA = "https://script.google.com/macros/s/AKfycby-4_Itip0Wz1a6QObv2FtpD_fenhSA72it5DOpCshbDfvd_ajukhS0SF3YXQXF842K/exec"
REGISTRO_MAQUINA_SECRET = "Hipopotamo@2024"