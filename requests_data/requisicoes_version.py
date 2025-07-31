import requests
import json
from config import APP_TITLE, current_version, URL_VERSAO


VERSAO_LOCAL = current_version
URL_VERSAO = URL_VERSAO


def verificar_versao(ft, page):
    try:
        response = requests.get(URL_VERSAO, timeout=10)
        response.raise_for_status()
        dados = response.json()
        nova_versao = dados.get("version")
        changelog = dados.get("changelog", "")
        link = dados.get("download_url", "#")

        if nova_versao and nova_versao != VERSAO_LOCAL:
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("🚨 Nova versão disponível"),
                content=ft.Column([
                    ft.Text(f"Sua versão: {VERSAO_LOCAL}"),
                    ft.Text(f"Nova versão: {nova_versao}"),
                    ft.Text(f"\nNovidades:\n{changelog}"),
                ]),
                actions=[
                    ft.TextButton("Baixar atualização", on_click=lambda _: page.launch_url(link)),
                    ft.TextButton("Agora não", on_click=lambda _: page.dialog.close())
                ],
                open=True
            )
            page.dialog = dlg
            dlg.open = True
            page.update()
    except Exception as e:
        print(f"Erro ao verificar versão: {e}")
