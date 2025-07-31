import requests
import json
from config import APP_TITLE, current_version, URL_VERSAO


VERSAO_LOCAL = current_version
# VERSAO_LOCAL = 'teste'
URL_VERSAO = URL_VERSAO


def verificar_versao():
    try:
        response = requests.get(URL_VERSAO, timeout=10)
        response.raise_for_status()
        dados = response.json()
        nova_versao = dados.get("version")
        changelog = dados.get("changelog", "")
        link = dados.get("download_url", "#")

        if nova_versao and nova_versao != VERSAO_LOCAL:
            return {
                "nova_versao": nova_versao,
                "changelog": changelog,
                "link": link
            }
    except Exception as e:
        print(f"Erro ao verificar versão: {e}")
    return None
