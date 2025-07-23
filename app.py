import flet as ft
import threading
import re
import os
import pandas as pd
from datetime import datetime
from main import executar_fluxo_completo
from Navegador.selenium_execution import iniciar_sessao_sior
from requests_data.requisicoes import get_dados_auto

# Constantes de estilo
DEFAULT_FONT_SIZE = 12
HEADING_FONT_SIZE = 16

# Variáveis globais
navegador_global = None
historico_logs = []
tabela_resultados = []
pagina_atual = 1
itens_por_pagina = 5  # Itens por página
filtro_ativo = {}


def main(page: ft.Page):
    global navegador_global, historico_logs, tabela_resultados, pagina_atual, filtro_ativo

    # Configurações da página
    page.title = "SIOR - Relatórios de AIT"
    page.window_width = 1200
    page.window_height = 1024
    page.scroll = "AUTO"
    page.padding = 25
    page.theme_mode = "dark"
    page.window_resizable = True


    # Alternar tema
    def toggle_theme(e):
        page.theme_mode = "dark" if page.theme_mode == "light" else "light"
        toggle_switch.label = "🌙 Modo Escuro" if page.theme_mode == "light" else "🌞 Modo Claro"
        page.update()

    toggle_switch = ft.Switch(
        label="🌙 Modo Escuro",
        value=False,
        on_change=toggle_theme,
        tooltip="Alternar claro/escuro"
    )

    # === Componentes Consulta AIT ===
    input_consulta = ft.TextField(
        label="Número do AIT (um por linha)", multiline=True,
        min_lines=5, max_lines=10, height=150,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )
    btn_consultar = ft.ElevatedButton(
        "Iniciar Consulta", icon=ft.Icons.SEARCH,
        bgcolor="green", color="white"
    )
    progress_consulta = ft.ProgressBar(width=400, visible=False)
    status_consulta = ft.Text("", size=DEFAULT_FONT_SIZE, color="blue", visible=False)
    log_consulta = ft.TextField(
        label="📝 Log de Consulta", multiline=True,
        read_only=True, expand=True, height=200,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )
    # Dropdowns de filtro
    filtro_numero_auto = ft.TextField(
        label="Pesquisar por NumeroAuto",
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        visible=False
    )
    filtro_situacao_fase = ft.Dropdown(
        label="Filtrar por SituacaoFase", options=[], width=200,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        visible=False
    )
    filtro_situacao_debito = ft.Dropdown(
        label="Filtrar por SituacaoDebito", options=[], width=200,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        visible=False
    )
    btn_filtrar = ft.ElevatedButton("🔍 Filtrar Tabela", visible=False)
    btn_limpar = ft.ElevatedButton("Limpar Filtros", visible=False)
    loading_filtro = ft.Row(
        [ft.ProgressRing()],  # <— use ProgressRing, não CircularProgressIndicator
        alignment="center",
        visible=False
    )

    # Contador, paginador e export
    total_text = ft.Text("Total de registros: 0", size=DEFAULT_FONT_SIZE)
    paginador_text = ft.Text(size=DEFAULT_FONT_SIZE)
    btn_anterior = ft.ElevatedButton("⬅ Anterior", visible=False)
    btn_proximo = ft.ElevatedButton("Próxima ➡", visible=False)
    btn_export_consulta = ft.ElevatedButton("📤 Exportar XLSX", icon=ft.Icons.SAVE, visible=False)
    msg_export = ft.Text(
        value="",
        color="green",
        size=DEFAULT_FONT_SIZE,
        visible=False
    )

    # Tabela de resultados
    cols = [
        "NumeroAuto", "DataInfracao", "Enquadramento", "Local", "Municipio",
        "EquipamentoAfericao", "Proprietario", "SituacaoFase",
        "SituacaoDebito", "ValorMulta", "VencimentoNP"
    ]
    table_consulta = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(c, size=DEFAULT_FONT_SIZE)) for c in cols],
        rows=[], expand=True,
        data_text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )

    # Funções de interação
    def atualizar_tabela():
        table_consulta.rows.clear()
        dados_filtrados = tabela_resultados
        for chave, valor in filtro_ativo.items():
            dados_filtrados = [d for d in dados_filtrados if valor.lower() in str(d.get(chave, '')).lower()]
        total = len(dados_filtrados)
        total_text.value = f"Total de registros: {total}"
        total_paginas = max(1, (total + itens_por_pagina - 1) // itens_por_pagina)
        pagina = max(1, min(pagina_atual, total_paginas))
        inicio = (pagina - 1) * itens_por_pagina
        fim = inicio + itens_por_pagina
        for row in dados_filtrados[inicio:fim]:
            table_consulta.rows.append(
                ft.DataRow(cells=[ft.DataCell(ft.Text(str(row[col]), size=DEFAULT_FONT_SIZE)) for col in cols])
            )
        # ==== Ajuste de visibilidade ====
        # filtros e botões sempre visíveis
        for w in [
            filtro_numero_auto,
            filtro_situacao_fase,
            filtro_situacao_debito,
            btn_filtrar,
            btn_limpar
        ]:
            w.visible = True
        # controles de paginação e export apenas se houver registros
        vis_controles = (total > 0)
        for w in [
            total_text,
            paginador_text,
            btn_anterior,
            btn_proximo,
            btn_export_consulta
        ]:
            w.visible = vis_controles
        btn_anterior.disabled = (pagina == 1)
        btn_proximo.disabled = (pagina == total_paginas)
        page.update()

    def aplicar_filtro(e):
        def task_filtro():
            global pagina_atual
            # mostra loading e oculta tabela
            loading_filtro.visible = True
            table_consulta.visible = False
            page.update()

            # reseta página e filtros
            pagina_atual = 1
            filtro_ativo.clear()
            if filtro_numero_auto.value.strip():
                filtro_ativo["NumeroAuto"] = filtro_numero_auto.value.strip()
            if filtro_situacao_fase.value:
                filtro_ativo["SituacaoFase"] = filtro_situacao_fase.value
            if filtro_situacao_debito.value:
                filtro_ativo["SituacaoDebito"] = filtro_situacao_debito.value

            # aplica e atualiza tabela
            atualizar_tabela()

            # esconde loading e mostra tabela
            loading_filtro.visible = False
            table_consulta.visible = True
            page.update()

        # roda em thread para que o UI possa renderizar o loading
        threading.Thread(target=task_filtro).start()

    def limpar_filtros(e):
        global pagina_atual, filtro_ativo

        # Reseta a página e limpa o dicionário de filtros
        pagina_atual = 1
        filtro_ativo.clear()

        # Zera TODOS os campos de filtro
        filtro_numero_auto.value = ""
        filtro_situacao_fase.value = None  # <— limpa o dropdown SituaçãoFase
        filtro_situacao_debito.value = None  # <— limpa o dropdown SituaçãoDebito

        # Re-renderiza a tabela com todos os registros
        atualizar_tabela()

    def pagina_anterior(e):
        global pagina_atual
        pagina_atual = max(1, pagina_atual - 1)
        atualizar_tabela()

    def pagina_proxima(e):
        global pagina_atual
        pagina_atual += 1
        atualizar_tabela()

    def run_consulta(e):
        global tabela_resultados, pagina_atual
        erros = []
        codigos = [c.strip() for c in input_consulta.value.splitlines() if c.strip()]
        if not codigos:
            erros.append("⚠ É necessário inserir ao menos um código AIT.")
        if len(set(codigos)) < len(codigos):
            erros.append("⚠ Existem Número de AITs duplicados.")
        if len(codigos) > 2000:
            erros.append("⚠ Limite máximo de 2000 AITs por vez.")
        if any(" " in c for c in codigos):
            erros.append("⚠ Os Número de AIT não podem conter espaços.")
        if any(not re.match(r"^[A-Za-z][0-9]{9}$", c)
               for c in codigos):
            erros.append("⚠ Todos os Número de AITs devem ter o formato: Letra + 9 dígitos.")
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
        btn_consultar.text = "Consultando."
        table_consulta.visible = False
        log_consulta.value = ""
        page.update()
        def task():
            try:
                navegador, session = iniciar_sessao_sior()
                total = len(codigos)
                for idx, codigo in enumerate(codigos, start=1):
                    status_consulta.value = f"Consultando {idx}/{total}: {codigo}"
                    progress_consulta.value = idx / total; page.update()
                    resp = get_dados_auto(codigo, session)
                    for rec in resp.get("Data", []):
                        registro = {}
                        for k in cols:
                            valor = rec.get(k, "")
                            if k in ["DataInfracao", "VencimentoNP"] and isinstance(valor, dict):
                                registro[k] = valor.get("DateString", "")
                            else:
                                registro[k] = valor
                        tabela_resultados.append(registro)
                # Popula dropdowns
                unique_fases = sorted({d.get("SituacaoFase", "") for d in tabela_resultados})
                filtro_situacao_fase.options = [ft.dropdown.Option(key=f, text=f) for f in unique_fases if f]
                unique_debitos = sorted({d.get("SituacaoDebito", "") for d in tabela_resultados})
                filtro_situacao_debito.options = [ft.dropdown.Option(key=d, text=d) for d in unique_debitos if d]
                atualizar_tabela()
                status_consulta.value = "✅ Concluído"
            except Exception as ex:
                log_consulta.value = f"❌ Erro: {ex}"
            finally:
                btn_consultar.disabled = False; btn_consultar.text = "Iniciar Consulta"
                progress_consulta.visible = False; table_consulta.visible = True
                page.update()
        threading.Thread(target=task).start()

    def exportar_xlsx(e):
        try:
            # Aplica os filtros antes de exportar
            dados_filtrados = tabela_resultados
            for chave, valor in filtro_ativo.items():
                dados_filtrados = [d for d in dados_filtrados if valor.lower() in str(d.get(chave, '')).lower()]

            # Converte os dados para DataFrame
            df = pd.DataFrame(dados_filtrados)

            # Gera nome do arquivo com timestamp
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            nome_arquivo = f"Consulta_AIT_{ts}.xlsx"
            path = os.path.join(os.path.expanduser("~"), "Downloads", nome_arquivo)

            # Exporta para Excel
            df.to_excel(path, index=False)

            # Mostra mensagem de sucesso
            msg_export.value = "📤 Exportação concluída com sucesso!"
            msg_export.color = "green"
            msg_export.visible = True
            page.update()

            # Oculta a mensagem após 3 segundos
            def limpa_msg():
                msg_export.visible = False
                page.update()

            threading.Timer(3, limpa_msg).start()

        except Exception as ex:
            # Mostra mensagem de erro
            msg_export.value = f"❌ Falha ao exportar: {ex}"
            msg_export.color = "red"
            msg_export.visible = True
            page.update()

    # Associação de eventos
    btn_consultar.on_click = run_consulta
    btn_filtrar.on_click = aplicar_filtro
    btn_anterior.on_click = pagina_anterior
    btn_proximo.on_click = pagina_proxima
    btn_export_consulta.on_click = exportar_xlsx
    btn_limpar.on_click = limpar_filtros

    aba_consulta = ft.Column([
        # Cabeçalho da aba
        ft.Row(
            [
                ft.Text("🔍 CONSULTA AIT", size=HEADING_FONT_SIZE, weight="bold"),
                ft.Container(expand=True)
            ]
        ),
        # Área de entrada dos códigos AIT
        input_consulta,
        # Botão de consulta
        ft.Row([btn_consultar], alignment="center"),
        # Status e barra de progresso
        status_consulta,
        progress_consulta,
        # Linha de filtros
        ft.Row(
            [
                filtro_numero_auto,
                filtro_situacao_fase,
                filtro_situacao_debito,
                btn_filtrar,
                btn_limpar,
                btn_export_consulta
            ],
            alignment="center"
        ),
        # Indicador de loading durante o filtro
        loading_filtro,
        # Tabela de resultados
        table_consulta,
        # Controles de paginação e exportação
        ft.Row(
            [btn_anterior, paginador_text, btn_proximo, total_text],
            alignment="center"
        ),
        # <<< aqui: a label de feedback de exportação >>>
        msg_export,
        log_consulta
    ], expand=True)

    # === ABA 2: DOWNLOAD DE RELATÓRIOS ===
    input_download = ft.TextField(
        label="Número do AIT (um por linha)", multiline=True,
        min_lines=5, max_lines=10, height=150,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )
    check_financeiro = ft.Checkbox(label="Relatório Financeiro", value=True)
    check_resumido = ft.Checkbox(label="Relatório Resumido")
    btn_download = ft.ElevatedButton("Iniciar Processo", icon=ft.Icons.DOWNLOAD)
    progress_download = ft.ProgressBar(width=400, visible=False)
    status_download = ft.Text("", size=DEFAULT_FONT_SIZE, color="blue", visible=False)
    log_download = ft.TextField(label="📝 Log de Download", multiline=True, read_only=True, expand=True, height=200)

    def run_download(e):
        erros = []
        codigos = [c.strip() for c in input_download.value.splitlines() if c.strip()]
        if not codigos:
            erros.append("⚠ É necessário inserir ao menos um código AIT.")
        if len(set(codigos)) < len(codigos):
            erros.append("⚠ Existem Número de AITs duplicados.")
        if len(codigos) > 2000:
            erros.append("⚠ Limite máximo de 2000 AITs por vez.")
        if any(" " in c for c in codigos):
            erros.append("⚠ Os Número de AIT não podem conter espaços.")
        if any(not re.match(r"^[A-Za-z][0-9]{9}$", c)
               for c in codigos):
            erros.append("⚠ Todos os Número de AITs devem ter o formato: Letra + 9 dígitos.")
        if not (check_financeiro.value or check_resumido.value):
            erros.append("⚠ Selecione ao menos um tipo de relatório.")
        if erros:
            log_download.value = "\n".join(erros)
            page.update()
            return
        log_download.value = ""
        progress_download.value = 0
        status_download.visible = True
        status_download.value = "Preparando..."
        btn_download.disabled = True
        btn_download.text = "Processando..."
        snack = ft.SnackBar(
            ft.Text("✅ Relatórios extraídos com sucesso!"),
            bgcolor=ft.Colors.GREEN
        )
        page.snack_bar = snack
        page.snack_bar.open = True
        page.update()
        page.update()

        def task_download():
            try:
                total = len(codigos)
                for idx, codigo in enumerate(codigos, start=1):
                    status_download.value = f"Processando {idx}/{total}: {codigo}"
                    progress_download.value = idx / total
                    page.update()
                    result = executar_fluxo_completo(codigo,
                                                     log=log_download,
                                                     baixar_financeiro=check_financeiro.value,
                                                     baixar_resumido=check_resumido.value,
                                                     atualizar_progresso=lambda a, t: None,
                                                     total=total)
                    historico_logs.append(result)
                status_download.value = "✅ Concluído"
            except Exception as ex:
                log_download.value += f"❌ Erro em {codigo}: {ex}\n"
            finally:
                btn_download.disabled = False
                btn_download.text = "Iniciar Processo"
                page.update()

        threading.Thread(target=task_download).start()

    btn_download.on_click = run_download
    aba_download = ft.Column([
        ft.Text("📥 DOWNLOAD DE RELATÓRIOS", size=HEADING_FONT_SIZE, weight="bold"),
        input_download, ft.Row([check_financeiro, check_resumido], alignment="start"),
        ft.Row([btn_download], alignment="center"), status_download, progress_download, log_download
    ], expand=True)

    # === ABA 3: LOGS ===
    def exportar_logs(e):
        try:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            path = os.path.join(os.path.expanduser("~"), "Downloads", f"Logs_{ts}.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("-- Log Download --\n" + (log_download.value or "Nenhum log de download."))
                f.write("\n\n-- Log Consulta --\n" + (log_consulta.value or "Nenhum log de consulta."))
            page.snack_bar = ft.SnackBar(ft.Text("Logs exportados com sucesso!"))
            page.snack_bar.open = True
            page.update()
        except Exception as ex:
            page.snack_bar = ft.SnackBar(ft.Text(f"❌ Erro ao exportar logs: {ex}"))
            page.snack_bar.open = True
            page.update()

    aba_logs = ft.Column([
        ft.Text("🧾 LOGS", size=HEADING_FONT_SIZE, weight="bold"),
        ft.Row([ft.ElevatedButton("Exportar Logs",
                                  icon=ft.Icons.DOWNLOAD,
                                  on_click=exportar_logs)],
               alignment="center")
    ], expand=True)

    # === ABA 4: SOBRE ===
    aba_sobre = ft.Column([
        ft.Text("ℹ️ SOBRE", size=HEADING_FONT_SIZE, weight="bold"),
        ft.Text("Consulta e download de AIT via SIOR.", size=DEFAULT_FONT_SIZE)
    ], expand=True)

    # Montagem das abas
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=200,
        tabs=[
            ft.Tab(text="Consulta AIT", content=aba_consulta),
            ft.Tab(text="Download de Relatórios", content=aba_download),
            ft.Tab(text="Logs", content=aba_logs),
            ft.Tab(text="Sobre", content=aba_sobre)
        ],
        expand=1
    )

    page.add(
        ft.Row([ft.Text("SIOR - Relatórios", size=HEADING_FONT_SIZE, weight="bold"), toggle_switch]),
        tabs
    )


if __name__ == "__main__":
    ft.app(
        target=main
    )
