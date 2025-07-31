import threading
import flet as ft
import pandas as pd
from navegador.sior_selenium_execution import iniciar_sessao_sior
from requests_data.requisicoes_sior import get_acompanhamento_sior, get_valores_original
from collections import Counter
from datetime import datetime
import os

from utils.popups import mostrar_alerta


# === NOVA ABA DE SUPERVISOR ===
def aba_consulta_sior_painel_supervisor(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page):
    dados_tabela = []
    valores_equipes_saldos = []
    alerta_dialogo = ft.AlertDialog(modal=True, title=ft.Text(""), content=ft.Text(""), actions=[], open=False)

    dropdown_equipes = ft.Dropdown(
        label="Selecione a Equipe",
        options=[
            ft.dropdown.Option(key="2", text="Equipe Cobrança 1"),
            ft.dropdown.Option(key="1", text="Equipe Cobrança 2"),
            ft.dropdown.Option(key="3", text="Equipe Cobrança 3"),
            ft.dropdown.Option(key="4", text="Equipe Cobrança 4"),
            ft.dropdown.Option(key="5", text="Equipe Cobrança 5"),
        ],
        width=300
    )

    btn_consultar = ft.ElevatedButton("Consultar", icon=ft.Icons.SEARCH)
    btn_exportar = ft.ElevatedButton("Exportar Excel", icon=ft.Icons.SAVE, visible=False)
    status = ft.Text("", size=DEFAULT_FONT_SIZE, color="blue", visible=False)
    progress = ft.ProgressBar(width=400, visible=False)

    cards_container = ft.Row(wrap=True, spacing=10, run_spacing=10)
    abas_indicadores = ft.Tabs(selected_index=0, tabs=[], visible=False, expand=True)

    def atualizar_cards():
        cards_container.controls.clear()
        contagem = Counter([d.get("SituacaoFase", "Não Informado") for d in dados_tabela])
        cards_container.controls = [
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text(situacao, weight="bold", size=DEFAULT_FONT_SIZE),
                        ft.Text(f"{qtd} registros")
                    ]),
                    padding=15,
                    width=200
                )
            )
            for situacao, qtd in contagem.items()
        ]
        page.update()

    def atualizar_abas_indicadores():
        df = pd.DataFrame(dados_tabela)
        abas_indicadores.tabs = []
        metricas = {
            "Qtd por Analisador": df["TecnicoAnalise"].value_counts(),
            "Qtd por Situação Fase": df["SituacaoFase"].value_counts()
        }
        for nome, serie in metricas.items():
            linhas = [
                ft.DataRow(cells=[ft.DataCell(ft.Text(str(idx))), ft.DataCell(ft.Text(str(val)))] )
                for idx, val in serie.items()
            ]
            tabela_metricas = ft.DataTable(
                columns=[ft.DataColumn(ft.Text("Categoria")), ft.DataColumn(ft.Text("Quantidade"))],
                rows=linhas,
                expand=True
            )
            abas_indicadores.tabs.append(
                ft.Tab(text=nome, content=ft.Container(content=tabela_metricas, padding=10))
            )

        abas_indicadores.visible = True
        page.update()

    def preencher_tabela():
        btn_exportar.visible = True
        atualizar_cards()
        atualizar_abas_indicadores()
        page.update()

    def exportar_excel(e):
        try:
            df = pd.DataFrame(dados_tabela)
            df["DataAnalise"] = pd.to_datetime(df["DataAnalise"], errors="coerce").dt.strftime("%d/%m/%Y")
            df["DataConferencia"] = pd.to_datetime(df["DataConferencia"], errors="coerce").dt.strftime("%d/%m/%Y")
            df["DataDistribuicaoEquipe"] = pd.to_datetime(df["DataDistribuicaoEquipe"],
                                                          errors="coerce").dt.strftime("%d/%m/%Y")
            df["DataDistribuicaoAnalise"] = pd.to_datetime(df["DataDistribuicaoAnalise"],
                                                           errors="coerce").dt.strftime("%d/%m/%Y")
            df["DataDistribuicaoConferencia"] = pd.to_datetime(df["DataDistribuicaoConferencia"],
                                                           errors="coerce").dt.strftime("%d/%m/%Y")

            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            path = os.path.join(os.path.expanduser("~"), "Downloads", f"Painel_Supervisor_{ts}.xlsx")

            with pd.ExcelWriter(path) as writer:
                df.to_excel(writer, sheet_name="Todos os Dados", index=False)

                resumo = {
                    "Qtd por Analisador": df["TecnicoAnalise"].value_counts(),
                    "Qtd por Conferidor": df["TecnicoConferencia"].value_counts(),
                    "Qtd por Situação Fase": df["SituacaoFase"].value_counts(),
                    "Qtd por Data de Análise": df["DataAnalise"].value_counts(),
                    "Qtd por Data de Conferência": df["DataConferencia"].value_counts()
                }

                for nome, serie in resumo.items():
                    pd.DataFrame({"Categoria": serie.index, nome: serie.values}).to_excel(
                        writer,
                        sheet_name="Indicadores",
                        startrow=writer.sheets.get("Indicadores", 0).max_row if "Indicadores" in writer.sheets else 0,
                        index=False
                    )

                df_aberto = df[df["SituacaoFase"] == "Em Aberto / Equipe Cadastro Sapiens"]
                df_outros = df[df["SituacaoFase"] != "Em Aberto / Equipe Cadastro Sapiens"]

                df_aberto_group = df_aberto.groupby("DevedorIdentificacao").size().reset_index(name="Quantidade à distribuir")
                df_outros_group = df_outros.groupby("DevedorIdentificacao").size().reset_index(name="Quantidade outras fases")

                df_saldos = pd.merge(df_aberto_group, df_outros_group, on="DevedorIdentificacao", how="outer").fillna(0)
                df_saldos["Quantidade à distribuir"] = df_saldos["Quantidade à distribuir"].astype(int)
                df_saldos["Quantidade outras fases"] = df_saldos["Quantidade outras fases"].astype(int)

                # ➕ Correlaciona com os valores originais
                if valores_equipes_saldos:
                    df_valores = pd.DataFrame(valores_equipes_saldos)
                    if "DevedorIdentificacao" in df_valores and "ValorOriginal" in df_valores:
                        df_valores_resumo = df_valores.groupby("DevedorIdentificacao")["ValorOriginal"].sum().reset_index()
                        df_valores_resumo.rename(columns={"ValorOriginal": "Valor Total à Distribuir"}, inplace=True)
                        df_merge = pd.merge(df_saldos, df_valores_resumo, on="DevedorIdentificacao", how="left")
                        df_merge["Valor Total à Distribuir"] = df_merge["Valor Total à Distribuir"].fillna(0).astype(float)
                        df_merge = df_merge.sort_values("Quantidade à distribuir", ascending=True)
                        df_merge.to_excel(writer, sheet_name="Equipe Cadastro Sapiens", index=False)
                    else:
                        df_saldos.to_excel(writer, sheet_name="Equipe Cadastro Sapiens", index=False)
                else:
                    df_saldos.to_excel(writer, sheet_name="Equipe Cadastro Sapiens", index=False)

                # 🆕 Nova aba: Distribuição por Devedor
                df_aberto_filtro = df[df["SituacaoFase"] == "Em Aberto / Equipe Cadastro Sapiens"]
                df_outros_filtro = df[df["SituacaoFase"] != "Em Aberto / Equipe Cadastro Sapiens"]

                df_qtd_aberto = df_aberto_filtro.groupby("DevedorIdentificacao").size().reset_index(
                    name="Qtd Em Aberto / Equipe Cadastro Sapiens")
                df_qtd_outros = df_outros_filtro.groupby("DevedorIdentificacao").size().reset_index(
                    name="Qtd Outras Situações")

                df_dist = pd.merge(df_qtd_aberto, df_qtd_outros, on="DevedorIdentificacao", how="outer").fillna(0)
                df_dist["Qtd Em Aberto / Equipe Cadastro Sapiens"] = df_dist[
                    "Qtd Em Aberto / Equipe Cadastro Sapiens"].astype(int)
                df_dist["Qtd Outras Situações"] = df_dist["Qtd Outras Situações"].astype(int)

                df_dist = df_dist.sort_values("Qtd Em Aberto / Equipe Cadastro Sapiens", ascending=True)

                df_dist.to_excel(writer, sheet_name="Distribuição por Devedor", index=False)
            page.dialog = alerta_dialogo
            mostrar_alerta(ft,
                           page,
                           "Download concluído",
                           f"Disponível em C:\\Downloads.",
                           tipo="success")
            status.value = "📤 Exportado com sucesso! Verifique a pasta Downloads."
        except Exception as ex:
            status.value = f"❌ Falha ao exportar: {ex}"
        finally:
            status.visible = True
            page.update()

    def run_consulta(e):
        nonlocal dados_tabela, valores_equipes_saldos

        equipe_id = dropdown_equipes.value
        if not equipe_id:
            status.value = "⚠ Selecione uma equipe."
            status.visible = True
            page.update()
            return

        status.visible = True
        status.value = "🔄 Iniciando..."
        progress.visible = True
        btn_consultar.disabled = True
        cards_container.controls.clear()
        abas_indicadores.tabs.clear()
        abas_indicadores.visible = False
        page.update()

        def task():
            nonlocal valores_equipes_saldos
            try:
                status.value = "Iniciando Login"
                navegador, session = iniciar_sessao_sior()
                status.value = "Iniciando Varredura de dados..."
                dados = get_acompanhamento_sior(equipe_id, session)
                valores_equipes_saldos = get_valores_original(equipe_id, session)
                navegador.quit()
                status.value = "Iniciando Tratamento de dados..."
                dados_tabela.clear()
                dados_tabela.extend({k: (v[:10] if isinstance(v, str) and v.endswith("T00:00:00") else v)
                                     for k, v in item.items()} for item in dados)
                status.value = f"✅ {len(dados_tabela)} registros encontrados."
                preencher_tabela()
            except Exception as ex:
                status.value = f"❌ Erro: {ex}"
            finally:
                btn_consultar.disabled = False
                progress.visible = False
                page.update()

        threading.Thread(target=task).start()

    btn_consultar.on_click = run_consulta
    btn_exportar.on_click = exportar_excel

    return ft.Column([
        ft.Row([ft.Text("SIOR > Painel Supervisor", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        ft.Row([dropdown_equipes, btn_consultar, btn_exportar]),
        status,
        progress,
        cards_container,
        abas_indicadores,
        alerta_dialogo
    ], expand=True, spacing=10)

