import flet as ft
from flet import Icons, Colors
import pandas as pd
import os
import time
import threading

from requests_data.requisicoes_cadin import consultar_cadin
from requests_data.login_cadin import abrir_cadin
from utils.popups import mostrar_alerta  # ✅ usa sua função existente


def aba_consulta_cadin(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page):
    resultados = []
    paginador_atual = 1
    registros_por_pagina = 3
    navegador_global = None
    login_realizado = False

    CAMPOS_TABELA_PRINCIPAIS = ["cpfCnpj", "nome", "numeroReferencia", "dataInadimplencia"]

    alerta_dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[],
        open=False
    )

    header = ft.Row([ft.Text("CADIN > Consulta CADIN", size=10, weight="bold")], alignment="center")

    titulo = ft.Text("🔎 Consulta CADIN", size=HEADING_FONT_SIZE, weight=ft.FontWeight.BOLD, color=Colors.BLUE_300)

    campo_token = ft.TextField(
        label="TOKEN_JWT (copie do navegador CADIN após login)",
        hint_text="Cole aqui o TOKEN_JWT obtido após login GOV.BR",
        multiline=False,
        border_color=Colors.BLUE_200,
        border_radius=8,
        color=Colors.WHITE,
        cursor_color=Colors.BLUE_200,
        text_size=DEFAULT_FONT_SIZE,
        expand=True,
        password=True,
        can_reveal_password=True,
    )

    campo_documentos = ft.TextField(
        label="CPF(s) ou CNPJ(s) para consulta",
        hint_text="Informe até 100 CPFs ou CNPJs (um por linha ou separados por vírgula)",
        multiline=True,
        min_lines=3,
        max_lines=6,
        border_color=Colors.BLUE_200,
        border_radius=8,
        color=Colors.WHITE,
        cursor_color=Colors.BLUE_200,
        text_size=DEFAULT_FONT_SIZE,
        expand=True,
    )

    tabela = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(col)) for col in CAMPOS_TABELA_PRINCIPAIS],
        rows=[],
        border=ft.border.all(0.5, Colors.with_opacity(0.3, Colors.WHITE)),
        horizontal_lines=ft.border.BorderSide(0.3, Colors.with_opacity(0.2, Colors.WHITE)),
        vertical_lines=ft.border.BorderSide(0.3, Colors.with_opacity(0.2, Colors.WHITE)),
    )

    paginador_info = ft.Text("Página 1 de 1", size=DEFAULT_FONT_SIZE)
    btn_anterior = ft.IconButton(icon=Icons.ARROW_BACK)
    btn_proximo = ft.IconButton(icon=Icons.ARROW_FORWARD)
    btn_consultar = ft.ElevatedButton("Consultar CADIN", icon=Icons.SEARCH)
    btn_exportar = ft.ElevatedButton("Exportar Excel (completo)", icon=Icons.DOWNLOAD, visible=False)
    progresso = ft.ProgressRing(width=40, height=40, visible=False)

    # 📝 Campo de log
    log_consulta = ft.TextField(
        label="📝 Log de Consulta CADIN",
        multiline=True,
        read_only=True,
        expand=True,
        height=200,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )

    def atualizar_tabela():
        tabela.rows.clear()
        inicio = (paginador_atual - 1) * registros_por_pagina
        fim = inicio + registros_por_pagina
        for linha in resultados[inicio:fim]:
            tabela.rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(str(linha.get(c, "")))) for c in CAMPOS_TABELA_PRINCIPAIS
            ]))
        total_paginas = max(1, (len(resultados) + registros_por_pagina - 1) // registros_por_pagina)
        paginador_info.value = f"Página {paginador_atual} de {total_paginas}"
        page.update()

    def exportar_excel(e):
        if not resultados:
            page.dialog = alerta_dialogo
            mostrar_alerta(ft, page, "Nenhum dado para exportar", "⚠️ Verifique a consulta.", tipo="warning")
            return

        try:
            import re
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(downloads_path, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            caminho = os.path.join(downloads_path, f"Consulta_CADIN_{ts}.xlsx")
            df = pd.DataFrame(resultados)
            campos_data = ["dataComunicacao", "dataInadimplencia", "dataAtualizacao"]
            for campo in campos_data:
                if campo in df.columns:
                    df[campo] = pd.to_datetime(df[campo], errors="coerce").dt.strftime("%d/%m/%Y")

            if "cpfCnpj" in df.columns:
                def aplicar_mascara(valor):
                    valor = re.sub(r"\D", "", str(valor))
                    if len(valor) == 11:
                        return f"{valor[:3]}.{valor[3:6]}.{valor[6:9]}-{valor[9:]}"
                    elif len(valor) == 14:
                        return f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}"
                    return valor
                df["cpfCnpj"] = df["cpfCnpj"].apply(aplicar_mascara)

            df.to_excel(caminho, index=False)
            page.dialog = alerta_dialogo
            mostrar_alerta(ft, page, "Exportado com sucesso", "✅ Disponível em C:\\Downloads", tipo="success")

        except Exception as ex:
            page.dialog = alerta_dialogo
            mostrar_alerta(ft, page, "Erro ao exportar", f"❌ {ex}", tipo="error")

    def anterior(e):
        nonlocal paginador_atual
        if paginador_atual > 1:
            paginador_atual -= 1
            atualizar_tabela()

    def proximo(e):
        nonlocal paginador_atual
        if paginador_atual * registros_por_pagina < len(resultados):
            paginador_atual += 1
            atualizar_tabela()

    def consultar(e):
        nonlocal resultados, login_realizado, navegador_global, paginador_atual
        token = campo_token.value.strip()
        entrada = campo_documentos.value.strip()

        def iniciar_consulta(token: str, entrada: str):
            nonlocal resultados, paginador_atual
            documentos = [
                "".join(ch for ch in d if ch.isdigit())
                for d in entrada.replace(",", "\n").split("\n")
                if d.strip()
            ]
            if len(documentos) > 100:
                page.dialog = alerta_dialogo
                mostrar_alerta(ft, page, "Limite excedido", "⚠️ Máximo de 100 documentos por consulta.", tipo="warning")
                return

            progresso.visible = True
            log_consulta.value += f"🧭 Iniciando varredura de {len(documentos)} documento(s)...\n"
            page.update()

            def tarefa_consulta():
                nonlocal resultados, paginador_atual
                try:
                    resultados = []
                    for idx, doc in enumerate(documentos, start=1):
                        page.update()
                        dados = consultar_cadin(token, [doc])
                        if not dados:
                            log_consulta.value += f"⚠️ {doc}: Nenhum registro encontrado.\n"
                        else:
                            log_consulta.value += f"✅ {doc}: {len(dados)} registro(s) localizado(s).\n"
                            resultados.extend(dados)
                        page.update()
                    if resultados:
                        atualizar_tabela()
                        btn_exportar.visible = True
                        page.dialog = alerta_dialogo
                        mostrar_alerta(ft, page, "Consulta concluída", f"{len(resultados)} registros retornados.", tipo="success")
                    else:
                        page.dialog = alerta_dialogo
                        mostrar_alerta(ft, page, "Sem dados", "Nenhum registro encontrado.", tipo="warning")
                except Exception as ex:
                    log_consulta.value += f"❌ Erro: {ex}\n"
                    page.dialog = alerta_dialogo
                    mostrar_alerta(ft, page, "Erro", f"❌ {ex}", tipo="error")
                finally:
                    progresso.visible = False
                    page.update()

            threading.Thread(target=tarefa_consulta).start()

        if not token:
            page.dialog = alerta_dialogo
            mostrar_alerta(ft, page, "Token ausente", "⚠️ Informe o TOKEN_JWT para prosseguir.", tipo="warning")
            return
        if not entrada:
            page.dialog = alerta_dialogo
            mostrar_alerta(ft, page, "Nenhum documento informado", "⚠️ Digite pelo menos um CPF ou CNPJ.", tipo="warning")
            return

        iniciar_consulta(token, entrada)

    btn_consultar.on_click = consultar
    btn_exportar.on_click = exportar_excel
    btn_anterior.on_click = anterior
    btn_proximo.on_click = proximo

    conteudo = ft.Column(
        [
            header,
            ft.Divider(),
            titulo,
            campo_token,
            campo_documentos,
            ft.Row([btn_consultar, btn_exportar, progresso], spacing=15, alignment="center"),
            ft.Divider(height=1, color=Colors.with_opacity(0.2, Colors.WHITE)),
            tabela,
            ft.Row([btn_anterior, paginador_info, btn_proximo], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
            log_consulta,
            alerta_dialogo,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=10,
    )

    return conteudo
