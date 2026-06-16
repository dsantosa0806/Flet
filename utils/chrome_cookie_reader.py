import os
import json
import sqlite3
import shutil
import tempfile
import requests

try:
    import win32crypt
except ImportError:
    win32crypt = None


SIOR_DOMAIN = "servicos.dnit.gov.br"


def decrypt_cookie(encrypted_value):
    try:

        if not win32crypt:
            return None

        return win32crypt.CryptUnprotectData(
            encrypted_value,
            None,
            None,
            None,
            0
        )[1].decode()

    except Exception:
        return None


def localizar_cookie_db():

    base = os.path.join(
        os.environ["LOCALAPPDATA"],
        "Google",
        "Chrome",
        "User Data"
    )

    perfis = [
        "Default",
        "Profile 1",
        "Profile 2",
        "Profile 3",
        "Profile 4"
    ]

    for perfil in perfis:

        cookie_db = os.path.join(
            base,
            perfil,
            "Network",
            "Cookies"
        )

        if os.path.exists(cookie_db):
            return cookie_db

    return None


def capturar_cookies_sior():

    cookie_db = localizar_cookie_db()

    if not cookie_db:
        raise RuntimeError(
            "Não foi possível localizar o banco de cookies do Google Chrome."
        )

    temp_db = tempfile.mktemp(suffix=".db")

    shutil.copy2(cookie_db, temp_db)

    conn = sqlite3.connect(temp_db)

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            host_key,
            name,
            encrypted_value
        FROM cookies
        WHERE host_key LIKE ?
    """, (f"%{SIOR_DOMAIN}%",))

    cookies = {}

    for host, name, encrypted_value in cursor.fetchall():

        valor = decrypt_cookie(encrypted_value)

        if valor:
            cookies[name] = valor

    conn.close()

    try:
        os.remove(temp_db)
    except:
        pass

    return cookies


def validar_login_sior():

    cookies = capturar_cookies_sior()

    if (
        "ASP.NET_SessionId" not in cookies
        or ".SIOR_AUTH_prod_v2" not in cookies
    ):
        return False, None

    session = requests.Session()

    for nome, valor in cookies.items():

        session.cookies.set(
            nome,
            valor,
            domain=".servicos.dnit.gov.br"
        )

    try:

        teste = session.get(
            "https://servicos.dnit.gov.br/sior/Infracao/ConsultaAutoInfracao/List",
            params={
                "page": 1,
                "pageSize": 1,
                "calledfromapi": "true"
            },
            timeout=15
        )

        if teste.status_code == 200:
            return True, session

    except Exception:
        pass

    return False, None