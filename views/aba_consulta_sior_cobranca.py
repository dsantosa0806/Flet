import os
import re
import threading
from datetime import datetime
import pandas as pd
from navegador.sior_selenium_execution import iniciar_sessao_sior
from requests_data.requisicoes_sior import get_dados_auto_cobranca
from utils.popups import mostrar_alerta


def aba_consulta_auto_cobranca(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page, bloquear, desbloquear):
    tabela_resultados = []
    pagina_atual = 1
    itens_por_pagina = 3
    filtro_ativo = {}

    alerta_dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[],
        open=False
    )

    input_consulta = ft.TextField(label="Número do AIT (um por linha)", multiline=True, min_lines=5, max_lines=10,
                                  height=150, label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
                                  text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE))
    expander_input = ft.ExpansionTile(
        title=ft.Text("📥 Inserir Número do AIT"),
        initially_expanded=True,
        controls=[input_consulta],
    )
    btn_consultar = ft.ElevatedButton("Iniciar Consulta", icon=ft.Icons.SEARCH, bgcolor="green", color="white")
    progress = ft.ProgressBar(width=400, visible=False)
    status = ft.Text("", size=DEFAULT_FONT_SIZE, color="blue", visible=False)
    log = ft.TextField(label="📝 Log", multiline=True, read_only=True, expand=True, height=200,
                       label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
                       text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE))

    filtro_numero = ft.TextField(label="Filtrar por Número", visible=False, width=200)
    filtro_tipo = ft.Dropdown(label="Filtrar por Tipo Recuperação", options=[], width=250, visible=False)
    filtro_situacao = ft.Dropdown(label="Filtrar por Situação Fase", options=[], width=250, visible=False)

    btn_filtrar = ft.ElevatedButton("🔍 Filtrar Tabela", visible=False)
    btn_limpar = ft.ElevatedButton("Limpar Filtros", visible=False)
    loading_filtro = ft.Row([ft.ProgressRing()], alignment="center", visible=False)

    total_text = ft.Text("Total de registros: 0", size=DEFAULT_FONT_SIZE)
    paginador_text = ft.Text(size=DEFAULT_FONT_SIZE)
    btn_anterior = ft.ElevatedButton("⬅ Anterior", visible=False)
    btn_proximo = ft.ElevatedButton("Próxima ➡", visible=False)
    btn_export = ft.ElevatedButton("📤 Exportar XLSX", icon=ft.Icons.SAVE, visible=False)
    msg_export = ft.Text("", color="green", size=DEFAULT_FONT_SIZE, visible=False)

    cols = ["NumeroAuto", "Devedor", "TipoRecuperacaoCredito", "NUPFormatado", "DataConstituicaoDefinitiva", "ValorOriginal", "Enquadramento", "SituacaoFase"]

    table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c, size=DEFAULT_FONT_SIZE)) for c in cols],
        rows=[],
        expand=True,
        visible=False,
        data_text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )

    def atualizar_tabela():
        table.rows.clear()
        dados = tabela_resultados
        for chave, valor in filtro_ativo.items():
            dados = [d for d in dados if valor.lower() in str(d.get(chave, "")).lower()]

        total = len(dados)
        total_text.value = f"Total de registros: {total}"
        total_paginas = max(1, (total + itens_por_pagina - 1) // itens_por_pagina)
        nonlocal pagina_atual
        pagina_atual = max(1, min(pagina_atual, total_paginas))
        inicio = (pagina_atual - 1) * itens_por_pagina
        fim = inicio + itens_por_pagina

        for row in dados[inicio:fim]:
            table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(row.get(k, "")), size=DEFAULT_FONT_SIZE)) for k in cols
                ])
            )

        for w in [filtro_numero, filtro_tipo, filtro_situacao, btn_filtrar, btn_limpar]:
            w.visible = True

        vis = total > 0
        for w in [table, total_text, paginador_text, btn_anterior, btn_proximo, btn_export, container_tabela]:
            w.visible = vis

        btn_anterior.disabled = pagina_atual == 1
        btn_proximo.disabled = pagina_atual == total_paginas
        page.update()

    def aplicar_filtro(e):
        def task():
            nonlocal pagina_atual
            loading_filtro.visible = True
            table.visible = False
            page.update()

            pagina_atual = 1
            filtro_ativo.clear()
            if filtro_numero.value.strip():
                filtro_ativo["NumeroAuto"] = filtro_numero.value.strip()
            if filtro_tipo.value:
                filtro_ativo["TipoRecuperacaoCredito"] = filtro_tipo.value
            if filtro_situacao.value:
                filtro_ativo["SituacaoFase"] = filtro_situacao.value

            atualizar_tabela()
            loading_filtro.visible = False
            table.visible = True
            page.update()

        threading.Thread(target=task).start()

    def limpar_filtros(e):
        nonlocal pagina_atual, filtro_ativo
        pagina_atual = 1
        filtro_ativo.clear()
        filtro_numero.value = ""
        filtro_tipo.value = None
        filtro_situacao.value = None
        atualizar_tabela()

    def pagina_anterior(e):
        nonlocal pagina_atual
        pagina_atual = max(1, pagina_atual - 1)
        atualizar_tabela()

    def pagina_proxima(e):
        nonlocal pagina_atual
        pagina_atual += 1
        atualizar_tabela()

    def exportar_xlsx(e):
        try:
            dados_filtrados = tabela_resultados
            for chave, valor in filtro_ativo.items():
                dados_filtrados = [d for d in dados_filtrados if valor.lower() in str(d.get(chave, '')).lower()]

            df = pd.DataFrame(dados_filtrados)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            nome_arquivo = f"Consulta_AIT_Cobranca{ts}.xlsx"
            path = os.path.join(os.path.expanduser("~"), "Downloads", nome_arquivo)
            df.to_excel(path, index=False)

            page.dialog = alerta_dialogo
            msg_export.value = "📤 Exportação concluída com sucesso!"
            mostrar_alerta(ft, page, "Exportado com sucesso",
                           "✅ Disponível em C:\\Downloads",
                           tipo="success")

            msg_export.color = "green"
            msg_export.visible = True
            page.update()

            threading.Timer(3, lambda: (setattr(msg_export, "visible", False), page.update())).start()
        except Exception as ex:
            msg_export.value = f"❌ Falha ao exportar: {ex}"
            msg_export.color = "red"
            msg_export.visible = True
            page.update()

    def run_consulta(e):
        nonlocal tabela_resultados, pagina_atual
        codigos = [c.strip() for c in input_consulta.value.splitlines() if c.strip()]
        tabela_resultados.clear()
        pagina_atual = 1
        status.visible = True
        status.value = "Iniciando..."
        progress.visible = True
        progress.value = 0
        btn_consultar.disabled = True
        btn_consultar.text = "Consultando..."
        table.visible = False
        log.value = ""
        page.update()

        def task():
            try:
                bloquear()
                navegador, session = iniciar_sessao_sior()
                total = len(codigos)
                for idx, codigo in enumerate(codigos, 1):
                    status.value = f"Consultando {idx}/{total}: {codigo}"
                    progress.value = idx / total
                    page.update()
                    resposta = get_dados_auto_cobranca(codigo, session)
                    for item in resposta.get("Data", []):
                        linha = {}
                        for k in cols:
                            valor = item.get(k, "")
                            if isinstance(valor, dict) and "DateString" in valor:
                                linha[k] = valor["DateString"]
                            else:
                                linha[k] = valor
                        tabela_resultados.append(linha)
                filtro_tipo.options = [ft.dropdown.Option(key=f, text=f) for f in sorted({r.get("TipoRecuperacaoCredito", "") for r in tabela_resultados}) if f]
                filtro_situacao.options = [ft.dropdown.Option(key=f, text=f) for f in sorted({r.get("SituacaoFase", "") for r in tabela_resultados}) if f]
                atualizar_tabela()
                status.value = "✅ Consulta concluída"
            except Exception as ex:
                log.value = f"❌ Erro: {ex}"
                status.value = "Erro"
            finally:
                btn_consultar.disabled = False
                btn_consultar.text = "Nova Consulta"
                progress.visible = False
                expander_input.initially_expanded = False
                expander_input.expanded = False
                desbloquear()
                page.update()

        threading.Thread(target=task).start()

    btn_consultar.on_click = run_consulta
    btn_filtrar.on_click = aplicar_filtro
    btn_limpar.on_click = limpar_filtros
    btn_anterior.on_click = pagina_anterior
    btn_proximo.on_click = pagina_proxima
    btn_export.on_click = exportar_xlsx

    container_tabela = ft.Container(
        content=table,
        height=250,
        padding=10,
        border_radius=10,
        border=ft.border.all(1, ft.Colors.GREY_600),
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        visible=False
    )

    return ft.Column([
        ft.Row([ft.Text("SIOR > Consultar Auto de Infração Cobrança", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        expander_input,
        ft.Row([btn_consultar], alignment="center"),
        status,
        progress,
        ft.Row([filtro_numero, filtro_tipo, filtro_situacao, btn_filtrar, btn_limpar, btn_export], alignment="center"),
        loading_filtro,
        container_tabela,
        ft.Row([btn_anterior, paginador_text, btn_proximo, total_text], alignment="center"),
        msg_export,
        log,
        alerta_dialogo
    ], expand=True)
