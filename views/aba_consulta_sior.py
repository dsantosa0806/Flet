import os
import re
import threading
from datetime import datetime
import pandas as pd
from navegador.sior_selenium_execution import iniciar_sessao_sior
from requests_data.requisicoes_sior import get_dados_auto
from utils.popups import mostrar_alerta


# === ABA DE CONSULTA DE AIT ===
def aba_consulta(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page):
    # === ESTADO GLOBAL LOCAL ===
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

    # === COMPONENTES ===
    input_consulta = ft.TextField(label="Número do AIT (um por linha)", multiline=True, min_lines=5, max_lines=10,
                                  height=150, label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
                                  text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE))
    expander_input_consulta = ft.ExpansionTile(
        title=ft.Text("📥 Inserir Número do AIT"),
        initially_expanded=True,  # começa expandido
        controls=[input_consulta],
    )
    btn_consultar = ft.ElevatedButton("Iniciar Consulta", icon=ft.Icons.SEARCH, bgcolor="green", color="white")
    progress_consulta = ft.ProgressBar(width=400, visible=False)
    status_consulta = ft.Text("", size=DEFAULT_FONT_SIZE, color="blue", visible=False)
    log_consulta = ft.TextField(label="📝 Log de Consulta", multiline=True, read_only=True, expand=True, height=200,
                                label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
                                text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE))

    filtro_numero_auto = ft.TextField(label="Pesquisar por NumeroAuto", visible=False,
                                      label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
                                      text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE))
    filtro_situacao_fase = ft.Dropdown(label="Filtrar por SituacaoFase", options=[], width=200, visible=False,
                                       label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE))
    filtro_situacao_debito = ft.Dropdown(label="Filtrar por SituacaoDebito", options=[], width=200, visible=False,
                                         label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE))

    btn_filtrar = ft.ElevatedButton("🔍 Filtrar Tabela", visible=False)
    btn_limpar = ft.ElevatedButton("Limpar Filtros", visible=False)
    loading_filtro = ft.Row([ft.ProgressRing()], alignment="center", visible=False)

    total_text = ft.Text("Total de registros: 0", size=DEFAULT_FONT_SIZE)
    paginador_text = ft.Text(size=DEFAULT_FONT_SIZE)
    btn_anterior = ft.ElevatedButton("⬅ Anterior", visible=False)
    btn_proximo = ft.ElevatedButton("Próxima ➡", visible=False)
    btn_export_consulta = ft.ElevatedButton("📤 Exportar XLSX", icon=ft.Icons.SAVE, visible=False)
    msg_export = ft.Text(value="", color="green", size=DEFAULT_FONT_SIZE, visible=False)

    cols = [
        "NumeroAuto", "DataInfracao", "Enquadramento", "Local", "Municipio",
        "EquipamentoAfericao", "Proprietario", "SituacaoFase",
        "SituacaoDebito", "ValorMulta", "VencimentoNP"
    ]
    table_consulta = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c, size=DEFAULT_FONT_SIZE)) for c in cols],
        rows=[],
        expand=True,
        visible=False,
        data_text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )

    # === FUNÇÕES AUXILIARES ===
    def validar_codigos(codigos):
        erros = []
        if not codigos:
            erros.append("⚠ É necessário inserir ao menos um código AIT.")
        if len(set(codigos)) < len(codigos):
            erros.append("⚠ Existem Número de AITs duplicados.")
        if len(codigos) > 2000:
            erros.append("⚠ Limite máximo de 2000 AITs por vez.")
        if any(" " in c for c in codigos):
            erros.append("⚠ Os Número de AIT não podem conter espaços.")
        if any(not re.match(r"^[A-Za-z][0-9]{9}$", c) for c in codigos):
            erros.append("⚠ Todos os Número de AITs devem ter o formato: Letra + 9 dígitos.")
        return erros

    def atualizar_tabela():
        table_consulta.rows.clear()
        dados_filtrados = tabela_resultados
        for chave, valor in filtro_ativo.items():
            dados_filtrados = [d for d in dados_filtrados if valor.lower() in str(d.get(chave, '')).lower()]

        total = len(dados_filtrados)
        total_text.value = f"Total de registros: {total}"
        total_paginas = max(1, (total + itens_por_pagina - 1) // itens_por_pagina)

        nonlocal pagina_atual
        pagina = max(1, min(pagina_atual, total_paginas))
        inicio = (pagina - 1) * itens_por_pagina
        fim = inicio + itens_por_pagina

        for row in dados_filtrados[inicio:fim]:
            table_consulta.rows.append(
                ft.DataRow(cells=[ft.DataCell(ft.Text(str(row[col]), size=DEFAULT_FONT_SIZE)) for col in cols])
            )

        # Atualiza visibilidades
        for w in [filtro_numero_auto, filtro_situacao_fase, filtro_situacao_debito, btn_filtrar, btn_limpar]:
            w.visible = True

        vis = total > 0
        for w in [total_text, paginador_text, btn_anterior, btn_proximo, btn_export_consulta, table_consulta,
                  container_tabela]:
            w.visible = vis  # ⬅️ Controla a visibilidade do container e tabela

        btn_anterior.disabled = (pagina == 1)
        btn_proximo.disabled = (pagina == total_paginas)
        page.update()

    def aplicar_filtro(e):
        def task():
            nonlocal pagina_atual
            loading_filtro.visible = True
            table_consulta.visible = False
            page.update()

            pagina_atual = 1
            filtro_ativo.clear()
            if filtro_numero_auto.value.strip():
                filtro_ativo["NumeroAuto"] = filtro_numero_auto.value.strip()
            if filtro_situacao_fase.value:
                filtro_ativo["SituacaoFase"] = filtro_situacao_fase.value
            if filtro_situacao_debito.value:
                filtro_ativo["SituacaoDebito"] = filtro_situacao_debito.value

            atualizar_tabela()

            loading_filtro.visible = False
            table_consulta.visible = True
            page.update()

        threading.Thread(target=task).start()

    def limpar_filtros(e):
        nonlocal pagina_atual, filtro_ativo
        pagina_atual = 1
        filtro_ativo.clear()
        filtro_numero_auto.value = ""
        filtro_situacao_fase.value = None
        filtro_situacao_debito.value = None
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
            nome_arquivo = f"Consulta_AIT_{ts}.xlsx"
            path = os.path.join(os.path.expanduser("~"), "Downloads", nome_arquivo)
            df.to_excel(path, index=False)
            msg_export.value = "📤 Exportação concluída com sucesso!"
            page.dialog = alerta_dialogo
            mostrar_alerta(ft, page, "Exportado com sucesso",
                           "✅ Disponível em C:\\Downloads!",
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
        erros = validar_codigos(codigos)

        if erros:
            log_consulta.value = "\n".join(erros)
            page.update()
            return

        tabela_resultados.clear()
        pagina_atual = 1
        status_consulta.visible = True
        status_consulta.value = "Iniciando consulta."
        progress_consulta.visible = True
        progress_consulta.value = 0
        btn_consultar.disabled = True
        btn_consultar.text = "Consultando..."
        table_consulta.visible = False
        log_consulta.value = ""
        page.update()

        def task():
            try:
                navegador, session = iniciar_sessao_sior()
                total = len(codigos)
                for idx, codigo in enumerate(codigos, start=1):
                    status_consulta.value = f"Consultando {idx}/{total}: {codigo}"
                    progress_consulta.value = idx / total
                    page.update()
                    resp = get_dados_auto(codigo, session)
                    for rec in resp.get("Data", []):
                        registro = {}
                        for k in cols:
                            valor = rec.get(k, "")
                            registro[k] = valor.get("DateString", "") if isinstance(valor, dict) else valor
                        tabela_resultados.append(registro)
                filtro_situacao_fase.options = [ft.dropdown.Option(key=f, text=f)
                                                for f in sorted({d.get("SituacaoFase", "")
                                                                 for d in tabela_resultados}) if f]
                filtro_situacao_debito.options = [ft.dropdown.Option(key=d, text=d)
                                                  for d in sorted({d.get("SituacaoDebito", "")
                                                                   for d in tabela_resultados}) if d]
                atualizar_tabela()
                status_consulta.value = "✅ Concluído"
            except Exception as ex:
                log_consulta.value = f"❌ Erro: {ex}"
                status_consulta.value = "Erro"
            finally:
                btn_consultar.disabled = False
                btn_consultar.text = "Nova Consulta"
                progress_consulta.visible = False
                expander_input_consulta.expanded = False  # 👈 colapsa de verdade
                expander_input_consulta.update()  # 👈 redesenha só o tile

                page.update()  # 👈 redesenha a página

        threading.Thread(target=task).start()

    # === EVENTOS ===
    btn_consultar.on_click = run_consulta
    btn_filtrar.on_click = aplicar_filtro
    btn_limpar.on_click = limpar_filtros
    btn_anterior.on_click = pagina_anterior
    btn_proximo.on_click = pagina_proxima
    btn_export_consulta.on_click = exportar_xlsx

    # ⬇️ Tabela com formatação aplicada
    container_tabela = ft.Container(
        content=table_consulta,
        height=200,  # Aumente ou ajuste conforme necessário
        padding=10,
        border_radius=10,
        border=ft.border.all(1, ft.Colors.GREY_600),
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        visible=False  # ⬅️ Oculto inicialmente

    )

    # === LAYOUT FINAL ===
    return ft.Column([
        ft.Row([ft.Text("SIOR > Consultar Auto de Infração", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        expander_input_consulta,
        ft.Row([btn_consultar], alignment="center"),

        status_consulta,
        progress_consulta,

        ft.Row([
            filtro_numero_auto,
            filtro_situacao_fase,
            filtro_situacao_debito,
            btn_filtrar,
            btn_limpar,
            btn_export_consulta
        ], alignment="center"),

        loading_filtro,
        container_tabela,

        ft.Row([btn_anterior, paginador_text, btn_proximo, total_text], alignment="center"),
        msg_export,
        log_consulta,
        alerta_dialogo

    ], expand=True, spacing=10)
