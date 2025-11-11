# === aba_consulta_sapiens_divida.py (atualizado para Super Sapiens Backend) ===

import os
import json
import threading
import pandas as pd
from datetime import datetime
from requests_data.requisicoes_sapiens import get_creditos_sapiens
from navegador.login_super_sapiens import obter_token
from utils.popups import mostrar_alerta


def exportar_para_excel(ft,
                        registros,
                        nome_prefixo,
                        mensagem_sucesso,
                        mensagem_falha,
                        msg_output,
                        page,
                        alerta_dialogo):
    """Exporta todos os registros coletados para Excel com abas 'Resumo' e 'Geral'."""
    try:
        if not registros or len(registros) == 0:
            msg_output.value = "⚠ Nenhum dado disponível para exportação."
            page.dialog = alerta_dialogo
            mostrar_alerta(ft, page, "Aviso", "Nenhum dado disponível para exportação.", tipo="warning")
            return

        campos_data = [
            'dataVencimento', 'dataInicioMultaMora', 'dataInicioSelic',
            'dataConstituicaoDefinitiva', 'dataInscricaoDivida',
            'dataAtualizacao', 'dataValidadeAtualizacao'
        ]

        # 🔹 Normaliza e formata todos os registros
        for registro in registros:
            # Datas ISO → dd/mm/yyyy
            for campo in campos_data:
                valor = registro.get(campo)
                if isinstance(valor, str) and "T" in valor:
                    try:
                        data_fmt = valor.split("T")[0]
                        ano, mes, dia = data_fmt.split("-")
                        registro[campo] = f"{dia}/{mes}/{ano}"
                    except Exception:
                        registro[campo] = ""

            # CPF/CNPJ formatado
            doc_raw = registro.get("devedorPrincipal", {}).get("numeroDocumentoPrincipal", "")
            if str(doc_raw).isdigit():
                if len(doc_raw) == 11:
                    registro["Devedor_DocumentoFormatado"] = f"{doc_raw[:3]}.{doc_raw[3:6]}.{doc_raw[6:9]}-{doc_raw[9:]}"
                elif len(doc_raw) == 14:
                    registro["Devedor_DocumentoFormatado"] = f"{doc_raw[:2]}.{doc_raw[2:5]}.{doc_raw[5:8]}/{doc_raw[8:12]}-{doc_raw[12:]}"
                else:
                    registro["Devedor_DocumentoFormatado"] = doc_raw
            else:
                registro["Devedor_DocumentoFormatado"] = doc_raw

            # NUP (processo)
            registro["NUP"] = registro.get("processo", {}).get("NUPFormatado", "")

            # Unidade completa
            unidade = registro.get("unidadeResponsavel", {}) or {}
            sigla = unidade.get("sigla", "")
            nome_unidade = unidade.get("nome", "")
            registro["UnidadeResponsavel_Completa"] = f"{sigla} - {nome_unidade}".strip(" -")

            # Fase Atual completa
            especie_status = registro.get("faseAtual", {}).get("especieStatus", {}) or {}
            nome = especie_status.get("nome", "")
            descricao = especie_status.get("descricao", "")
            registro["FaseAtual_Completa"] = f"{nome} - {descricao}".strip(" -")

            # CDA
            cda = registro.get("certidaoDividaAtivaAtual", {}) or {}
            registro["NumeroCertidaoDividaAtiva"] = cda.get("numeroCertidaoDividaAtiva", "")

        # 🔹 Criação dos DataFrames
        df_out = pd.DataFrame(registros)

        # Campos da aba "Resumo" (somente os existentes)
        campos_resumo = [
            "NUP", "Devedor_DocumentoFormatado", "FaseAtual_Completa",
            "UnidadeResponsavel_Completa", "numeroCreditoSistemaOriginario",
            "valorOriginario", "NumeroCertidaoDividaAtiva", "dataInscricaoDivida",
            "valorInscricaoDivida", "saldoAtualizado", "dataConstituicaoDefinitiva",
            "raizDevedorPrincipal"
        ]
        colunas_existentes = [c for c in campos_resumo if c in df_out.columns]
        df_resumo = df_out[colunas_existentes].copy() if colunas_existentes else pd.DataFrame()

        # Adiciona credor_id fixo e reordena
        df_resumo["credor_id"] = 902
        df_resumo = df_resumo[["credor_id"] + [c for c in df_resumo.columns if c != "credor_id"]]

        # 🔹 Exporta para Excel (com abas)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        caminho = os.path.join(os.path.expanduser("~"), "Downloads", f"{nome_prefixo}_{ts}.xlsx")

        with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
            # Aba 1: Resumo (campos essenciais)
            df_resumo.to_excel(writer, sheet_name="Resumo", index=False)
            # Aba 2: Geral (todos os dados)
            df_out.to_excel(writer, sheet_name="Geral", index=False)

        msg_output.value = mensagem_sucesso
        page.dialog = alerta_dialogo
        mostrar_alerta(ft, page, "Exportado com sucesso", f"✅ Arquivo salvo em {caminho}", tipo="success")
        print(f"📁 Exportação concluída: {len(df_out)} registros totais — salvo em {caminho}")

    except Exception as ex:
        msg_output.value = f"{mensagem_falha}: {ex}"
        page.dialog = alerta_dialogo
        mostrar_alerta(ft, page, "Falha", f"Erro ao gerar o arquivo: {ex}", tipo="error")

    msg_output.visible = True
    page.update()
    threading.Timer(3, lambda: (setattr(msg_output, "visible", False), page.update())).start()


# === ABA ===
def aba_consulta_sapiens(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page, bloquear, desbloquear):
    # ===== Helpers =====
    def limpar_numero(s: str) -> str:
        return ''.join(filter(str.isdigit, s or ''))

    def is_cpf_cnpj(s: str) -> bool:
        return s.isdigit() and len(s) in (11, 14)

    def formatar_cpf_cnpj(s: str) -> str:
        n = limpar_numero(s)
        if len(n) == 11:
            return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"
        if len(n) == 14:
            return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
        return s

    page_index = 1
    items_per_page = 3
    paginated, all_records = [], []

    alerta_dialogo = ft.AlertDialog(modal=True, title=ft.Text(""), content=ft.Text(""), actions=[], open=False)

    # Campo de entrada
    doc_field = ft.TextField(
        label="CPF/CNPJ do(s) Devedor(es) (um por linha, até 100)",
        hint_text="Ex.: 123.456.789-09 ou 12.345.678/0001-90",
        width=420,
        multiline=True,
        min_lines=3,
        max_lines=6,
    )

    btn_consultar_doc = ft.ElevatedButton("Consultar", icon=ft.Icons.SEARCH)
    status_doc = ft.Text("", visible=False, color="blue")
    progress_doc = ft.ProgressBar(width=400, visible=False)
    log_doc = ft.TextField(
        label="📝 Log de Consulta Super Sapiens",
        multiline=True,
        read_only=True,
        height=200,
        expand=True,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )

    total_text_doc = ft.Text("Total: 0")
    paginador_doc = ft.Text()
    btn_prev_doc = ft.ElevatedButton("⬅ Anterior", visible=False)
    btn_next_doc = ft.ElevatedButton("Próxima ➡", visible=False)
    btn_export_doc = ft.ElevatedButton("📤 Exportar XLSX", icon=ft.Icons.SAVE, visible=False)
    msg_export_doc = ft.Text("", visible=False)

    # === Tabela com apenas 6 colunas visíveis (otimizada) ===
    table_fields = [
        'NUP',
        'Devedor_Nome',
        'NumeroCreditoSistemaOriginario',
        'ValorOriginario',
        'DataConstituicaoDefinitiva',
        'FaseAtual_Status'
    ]

    table_doc = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(f)) for f in table_fields],
        rows=[],
        expand=True,
        visible=True,
        data_text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )

    # === Funções UI ===
    def atualizar_tabela():
        nonlocal page_index
        total = len(paginated)
        total_text_doc.value = f"Total: {total}"

        pages = max(1, (total + items_per_page - 1) // items_per_page)
        page_index = max(1, min(page_index, pages))
        start, end = (page_index - 1) * items_per_page, page_index * items_per_page

        # 🔹 Exibir somente as 6 primeiras colunas
        colunas_visiveis = [
            'NUP',
            'Devedor_Nome',
            'NumeroCreditoSistemaOriginario',
            'ValorOriginario',
            'DataConstituicaoDefinitiva',
            'FaseAtual_Status'
        ]

        table_doc.rows = [
            ft.DataRow(
                cells=[ft.DataCell(ft.Text(str(r.get(col, '')))) for col in colunas_visiveis]
            )
            for r in paginated[start:end]
        ]

        paginador_doc.value = f"{page_index}/{pages}"

        # 🔹 Controle de visibilidade
        has_data = total > 0
        container_tabela_doc.visible = has_data
        table_doc.visible = has_data
        btn_prev_doc.visible = has_data
        btn_next_doc.visible = has_data
        btn_export_doc.visible = has_data

        # 🔹 Estado dos botões
        btn_prev_doc.disabled = (page_index == 1)
        btn_next_doc.disabled = (page_index == pages)

        page.update()

    def prev_page(e):
        nonlocal page_index
        page_index = max(1, page_index - 1)
        atualizar_tabela()

    def next_page(e):
        nonlocal page_index
        pages = max(1, (len(paginated) + items_per_page - 1) // items_per_page)
        page_index = min(page_index + 1, pages)
        atualizar_tabela()

    def export_all(e):
        exportar_para_excel(
            ft=ft,
            registros=all_records,
            nome_prefixo="Sapiens_All",
            mensagem_sucesso="📤 Exportado!",
            mensagem_falha="❌ Falha ao exportar",
            msg_output=msg_export_doc,
            page=page,
            alerta_dialogo=alerta_dialogo
        )

    # === Fluxo principal ===
    def run_consult(e):
        nonlocal paginated, all_records, page_index

        docs_raw = [ln.strip() for ln in (doc_field.value or "").splitlines() if ln.strip()]
        if not docs_raw:
            log_doc.value = "⚠ Informe ao menos um CPF/CNPJ (um por linha, até 100)."
            page.update()
            return
        if len(docs_raw) > 100:
            log_doc.value = "⚠ Máximo de 100 documentos por consulta. Apenas os 100 primeiros serão processados.\n"
            docs_raw = docs_raw[:100]

        docs = [limpar_numero(x) for x in docs_raw]
        invalidos = [formatar_cpf_cnpj(x) for x in docs if not is_cpf_cnpj(x)]
        if invalidos:
            log_doc.value = f"❌ Documento(s) inválido(s): {', '.join(invalidos)}"
            page.update()
            return

        # UI init
        btn_consultar_doc.disabled = True
        progress_doc.visible = True
        status_doc.visible = True
        status_doc.value = "Iniciando login e obtenção do token..."
        log_doc.value = f"🧹 Iniciando varredura para {len(docs)} documento(s)..."
        total_text_doc.value = "Total: 0"
        page.update()

        def task():
            nonlocal paginated, all_records, page_index
            try:
                bloquear()
                # 🔹 1. Obtém token (apenas uma vez)
                status_doc.value = "🔐 Aguardando login e obtenção do token..."
                page.update()
                token = obter_token()

                if not token:
                    status_doc.value = "❌ Falha ao obter token. Verifique o login."
                    page.dialog = alerta_dialogo
                    mostrar_alerta(ft, page, "Falha no login", "Token inválido ou expirado.", tipo="error")
                    page.update()
                    return

                status_doc.value = "✅ Token obtido! Iniciando consultas..."
                page.update()

                # 🔁 2. Loop pelos documentos
                all_records, paginated = [], []
                total_docs = len(docs)
                encontrados_total = 0

                for idx, doc in enumerate(docs, start=1):
                    status_doc.value = f"Consultando {idx}/{total_docs}: {formatar_cpf_cnpj(doc)}"
                    page.update()

                    try:
                        # Passa o token direto
                        res = get_creditos_sapiens(token, doc)
                        records = res.get("records", []) or []
                        qtd = len(records)

                        if qtd == 0:
                            log_doc.value += f"\n🔎 {formatar_cpf_cnpj(doc)}: nenhum registro localizado."
                        else:
                            log_doc.value += f"\n✅ {formatar_cpf_cnpj(doc)}: {qtd} registro(s) capturado(s) com sucesso."
                            encontrados_total += qtd
                            all_records.extend(records)

                            # 🔹 Construção segura (evita 'NoneType.get')
                            for r in records:
                                processo = r.get('processo') or {}
                                devedor = r.get('devedorPrincipal') or {}
                                fase = r.get('faseAtual') or {}
                                especie_status = fase.get('especieStatus') or {}
                                unidade = r.get('unidadeResponsavel') or {}
                                cda = r.get('certidaoDividaAtivaAtual') or {}

                                paginated.append({
                                    'NUP': processo.get('NUPFormatado', ''),
                                    'Devedor_Nome': devedor.get('nome', ''),
                                    'NumeroCreditoSistemaOriginario': r.get('numeroCreditoSistemaOriginario', ''),
                                    'ValorOriginario': r.get('valorOriginario', ''),
                                    'DataConstituicaoDefinitiva': r.get('dataConstituicaoDefinitiva', ''),
                                    'FaseAtual_Status': especie_status.get('nome', ''),
                                    'UnidadeResponsavel': unidade.get('nome', ''),
                                    'NumeroCertidaoDividaAtiva': cda.get('numeroCertidaoDividaAtiva', '')
                                })

                    except Exception as ex_consulta:
                        log_doc.value += f"\n❌ Erro ao consultar {formatar_cpf_cnpj(doc)}: {ex_consulta}"

                # 🔹 3. Atualiza a tabela e status final
                page_index = 1
                status_doc.value = (
                    "⚠ Nenhum registro localizado"
                    if encontrados_total == 0
                    else f"📦 {encontrados_total} registro(s) localizado(s) no total"
                )
                atualizar_tabela()

            except Exception as ex:
                log_doc.value += f"\n❌ Erro geral: {ex}"
                status_doc.value = "Erro durante a execução"
            finally:
                # 🔹 4. Restaura a interface
                progress_doc.visible = False
                btn_consultar_doc.disabled = False
                btn_consultar_doc.text = "Consultar novamente"
                desbloquear()
                page.update()

        threading.Thread(target=task).start()

    # Eventos
    btn_consultar_doc.on_click = run_consult
    btn_prev_doc.on_click = prev_page
    btn_next_doc.on_click = next_page
    btn_export_doc.on_click = export_all

    container_tabela_doc = ft.Container(
        content=table_doc,
        expand=True,
        height=200,
        padding=10,
        border_radius=10,
        border=ft.border.all(1, ft.Colors.GREY_600),
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        visible=False
    )

    children = [
        ft.Row([ft.Text("SUPER SAPIENS > Consulta Crédito Dívida", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        ft.Row([doc_field, btn_consultar_doc]),
        status_doc,
        progress_doc,
        container_tabela_doc,
        ft.Row([btn_prev_doc, paginador_doc, btn_next_doc, total_text_doc], alignment="center"),
        ft.Row([btn_export_doc], alignment="center"),
        msg_export_doc,
        log_doc,
        alerta_dialogo
    ]

    return ft.Column(children, expand=True, spacing=10)
