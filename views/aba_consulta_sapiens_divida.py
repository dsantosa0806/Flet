# === aba_consulta_sapiens_divida.py (Super Sapiens Backend) ===

import os
import re
import threading
from datetime import datetime

import pandas as pd

from navegador.login_super_sapiens import obter_token
from requests_data.requisicoes_sapiens import (
    get_creditos_sapiens,
    get_dados_creditos_raizes_devedores_sapiens,
)
from utils.open_dir_downloads import abrir_pasta_exportacao
from utils.popups import mostrar_alerta


# ==========================================================
# EXPORTAÇÃO
# ==========================================================
def exportar_para_excel(
    ft,
    registros,
    nome_prefixo,
    mensagem_sucesso,
    mensagem_falha,
    msg_output,
    page,
    alerta_dialogo,
):
    """Exporta todos os registros coletados para Excel com abas 'Resumo' e 'Geral'."""
    try:
        if not registros or len(registros) == 0:
            msg_output.value = "⚠ Nenhum dado disponível para exportação."
            page.dialog = alerta_dialogo
            mostrar_alerta(
                ft,
                page,
                "Aviso",
                "Nenhum dado disponível para exportação.",
                tipo="warning",
            )
            return

        campos_data = [
            "dataVencimento",
            "dataInicioMultaMora",
            "dataInicioSelic",
            "dataConstituicaoDefinitiva",
            "dataNotificacaoInicial",
            "dataDecursoPrazoDefesa",
            "dataDocumentoOrigem",
            "dataInscricaoDivida",
            "dataAtualizacao",
            "dataValidadeAtualizacao",
        ]

        registros_exportacao = []

        # 🔹 Normaliza e formata todos os registros sem alterar a lista original da tela
        for registro_original in registros:
            registro = dict(registro_original or {})

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

            devedor = registro.get("devedorPrincipal") or {}
            processo = registro.get("processo") or {}
            unidade = registro.get("unidadeResponsavel") or {}
            fase = registro.get("faseAtual") or {}
            especie_status = fase.get("especieStatus") or {}
            cda = registro.get("certidaoDividaAtivaAtual") or {}
            credor = registro.get("credor") or {}
            credor_pessoa = credor.get("pessoa") or {}
            especie_credito = registro.get("especieCredito") or {}
            regional = registro.get("regional") or {}
            modalidade = registro.get("modalidadeDocumentoOrigem") or {}

            # CPF/CNPJ formatado
            doc_raw = str(devedor.get("numeroDocumentoPrincipal", "") or "")
            if doc_raw.isdigit():
                if len(doc_raw) == 11:
                    registro["Devedor_DocumentoFormatado"] = (
                        f"{doc_raw[:3]}.{doc_raw[3:6]}.{doc_raw[6:9]}-{doc_raw[9:]}"
                    )
                elif len(doc_raw) == 14:
                    registro["Devedor_DocumentoFormatado"] = (
                        f"{doc_raw[:2]}.{doc_raw[2:5]}.{doc_raw[5:8]}/"
                        f"{doc_raw[8:12]}-{doc_raw[12:]}"
                    )
                else:
                    registro["Devedor_DocumentoFormatado"] = doc_raw
            else:
                registro["Devedor_DocumentoFormatado"] = doc_raw

            # Campos derivados para facilitar análise
            registro["Devedor_Nome"] = devedor.get("nome", "")
            registro["NUP"] = processo.get("NUPFormatado", "")
            registro["Credor_Nome"] = credor_pessoa.get("nome", "")
            registro["EspecieCredito_Nome"] = especie_credito.get("nome", "")
            registro["Regional_Nome"] = regional.get("nome", "")
            registro["ModalidadeDocumentoOrigem_Valor"] = modalidade.get("valor", "")

            sigla = unidade.get("sigla", "")
            nome_unidade = unidade.get("nome", "")
            registro["UnidadeResponsavel_Completa"] = (
                f"{sigla} - {nome_unidade}"
            ).strip(" -")

            nome_status = especie_status.get("nome", "")
            descricao_status = especie_status.get("descricao", "")
            registro["FaseAtual_Status"] = nome_status
            registro["FaseAtual_Completa"] = (
                f"{nome_status} - {descricao_status}"
            ).strip(" -")

            registro["NumeroCertidaoDividaAtiva"] = cda.get(
                "numeroCertidaoDividaAtiva",
                "",
            )

            registros_exportacao.append(registro)

        # 🔹 Criação dos DataFrames
        df_out = pd.DataFrame(registros_exportacao)

        # Campos da aba "Resumo" (somente os existentes)
        campos_resumo = [
            "NUP",
            "Devedor_DocumentoFormatado",
            "Devedor_Nome",
            "FaseAtual_Completa",
            "UnidadeResponsavel_Completa",
            "numeroCredito",
            "numeroCreditoSistemaOriginario",
            "valorOriginario",
            "NumeroCertidaoDividaAtiva",
            "dataInscricaoDivida",
            "valorInscricaoDivida",
            "saldoAtualizado",
            "dataConstituicaoDefinitiva",
            "raizDevedorPrincipal",
            "RaizPesquisada",
            "ConsultaPor",
        ]

        colunas_existentes = [c for c in campos_resumo if c in df_out.columns]
        df_resumo = (
            df_out[colunas_existentes].copy()
            if colunas_existentes
            else pd.DataFrame()
        )

        # Adiciona credor_id fixo e reordena
        df_resumo["credor_id"] = 902
        df_resumo = df_resumo[
            ["credor_id"] + [c for c in df_resumo.columns if c != "credor_id"]
        ]

        # 🔹 Exporta para Excel (com abas)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        caminho = os.path.join(
            os.path.expanduser("~"),
            "Downloads",
            f"{nome_prefixo}_{ts}.xlsx",
        )

        with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
            df_resumo.to_excel(writer, sheet_name="Resumo", index=False)
            df_out.to_excel(writer, sheet_name="Geral", index=False)

        msg_output.value = mensagem_sucesso
        page.dialog = alerta_dialogo
        mostrar_alerta(
            ft,
            page,
            "Exportado com sucesso",
            f"✅ Arquivo salvo em {caminho}",
            tipo="success",
        )
        print(
            f"📁 Exportação concluída: {len(df_out)} registros totais — salvo em {caminho}"
        )
        abrir_pasta_exportacao(caminho)

    except Exception as ex:
        msg_output.value = f"{mensagem_falha}: {ex}"
        page.dialog = alerta_dialogo
        mostrar_alerta(
            ft,
            page,
            "Falha",
            f"Erro ao gerar o arquivo: {ex}",
            tipo="error",
        )

    msg_output.visible = True
    page.update()
    threading.Timer(
        3,
        lambda: (setattr(msg_output, "visible", False), page.update()),
    ).start()


# ==========================================================
# ABA
# ==========================================================
def aba_consulta_sapiens(
    ft,
    DEFAULT_FONT_SIZE,
    HEADING_FONT_SIZE,
    page,
    bloquear,
    desbloquear,
):
    # ===== Helpers =====
    def limpar_numero(s: str) -> str:
        return "".join(filter(str.isdigit, s or ""))

    def is_cpf_cnpj(s: str) -> bool:
        return s.isdigit() and len(s) in (11, 14)

    def formatar_cpf_cnpj(s: str) -> str:
        n = limpar_numero(s)
        if len(n) == 11:
            return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"
        if len(n) == 14:
            return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"
        return s

    def formatar_raiz_cnpj(s: str) -> str:
        n = limpar_numero(s)
        if len(n) == 8:
            return f"{n[:2]}.{n[2:5]}.{n[5:8]}"
        return s

    def validar_raizes_cnpj(raizes_raw):
        erros = []
        raizes = []

        if not raizes_raw:
            erros.append("Informe ao menos uma raiz de CNPJ para consulta.")
            return erros, raizes

        if len(raizes_raw) > 100:
            erros.append("Limite máximo de 100 raízes de CNPJ por consulta.")

        for idx, valor in enumerate(raizes_raw, start=1):
            raiz = limpar_numero(valor)

            if len(raiz) != 8:
                erros.append(
                    f"Linha {idx}: raiz de CNPJ inválida ({valor}). "
                    "Informe exatamente 8 dígitos. Ex: 02762115 ou 02.762.115."
                )
                continue

            raizes.append(raiz)

        duplicadas = sorted({r for r in raizes if raizes.count(r) > 1})
        if duplicadas:
            erros.append(
                "Existem raízes de CNPJ duplicadas: "
                + ", ".join(duplicadas[:20])
            )

        return erros, raizes

    def validar_documentos(docs_raw):
        erros = []
        docs = []

        if not docs_raw:
            erros.append("Informe ao menos um CPF/CNPJ para consulta.")
            return erros, docs

        if len(docs_raw) > 100:
            erros.append("Limite máximo de 100 CPF/CNPJ por consulta.")

        for idx, valor in enumerate(docs_raw, start=1):
            doc = limpar_numero(valor)

            if not is_cpf_cnpj(doc):
                erros.append(
                    f"Linha {idx}: CPF/CNPJ inválido ({valor}). "
                    "Informe 11 dígitos para CPF ou 14 dígitos para CNPJ."
                )
                continue

            docs.append(doc)

        duplicados = sorted({d for d in docs if docs.count(d) > 1})
        if duplicados:
            erros.append(
                "Existem CPF/CNPJ duplicados: "
                + ", ".join(formatar_cpf_cnpj(d) for d in duplicados[:20])
            )

        return erros, docs

    def montar_linha_tabela(registro):
        registro = registro or {}
        processo = registro.get("processo") or {}
        devedor = registro.get("devedorPrincipal") or {}
        fase = registro.get("faseAtual") or {}
        especie_status = fase.get("especieStatus") or {}
        unidade = registro.get("unidadeResponsavel") or {}
        cda = registro.get("certidaoDividaAtivaAtual") or {}

        return {
            "NUP": processo.get("NUPFormatado", ""),
            "Devedor_Nome": devedor.get("nome", ""),
            "NumeroCreditoSistemaOriginario": registro.get(
                "numeroCreditoSistemaOriginario",
                "",
            ),
            "ValorOriginario": registro.get("valorOriginario", ""),
            "DataConstituicaoDefinitiva": registro.get(
                "dataConstituicaoDefinitiva",
                "",
            ),
            "FaseAtual_Status": especie_status.get("nome", ""),
            "UnidadeResponsavel": unidade.get("nome", ""),
            "NumeroCertidaoDividaAtiva": cda.get(
                "numeroCertidaoDividaAtiva",
                "",
            ),
        }

    page_index = 1
    items_per_page = 3
    paginated, all_records = [], []

    alerta_dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[],
        open=False,
    )

    page.dialog = alerta_dialogo

    # Campo de entrada único
    doc_field = ft.TextField(
        label="CPF/CNPJ ou Raiz do CNPJ do(s) Devedor(es) (um por linha, até 100)",
        hint_text="CPF/CNPJ: 123.456.789-09 ou 12.345.678/0001-90 | Raiz: 02762115 ou 02.762.115",
        width=560,
        multiline=True,
        min_lines=3,
        max_lines=6,
        label_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
    )

    toggle_buscar_raiz_cnpj = ft.Switch(
        label="Buscar pela raiz do CNPJ?",
        value=False,
        tooltip=(
            "Quando marcado, o campo aceitará apenas raiz de CNPJ com 8 dígitos. "
            "Ex: 02762115 ou 02.762.115."
        ),
    )

    txt_ajuda_raiz = ft.Text(
        (
            "Desmarcado: consulta por CPF/CNPJ completo. "
            "Marcado: consulta por raiz CNPJ com 8 dígitos."
        ),
        size=DEFAULT_FONT_SIZE,
        color=ft.Colors.GREY_600,
        selectable=True,
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
        text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
    )

    total_text_doc = ft.Text("Total: 0")
    paginador_doc = ft.Text()
    btn_prev_doc = ft.ElevatedButton("⬅ Anterior", visible=False)
    btn_next_doc = ft.ElevatedButton("Próxima ➡", visible=False)
    btn_export_doc = ft.ElevatedButton(
        "📤 Exportar XLSX",
        icon=ft.Icons.SAVE,
        visible=False,
    )
    msg_export_doc = ft.Text("", visible=False)

    # === Tabela com apenas 6 colunas visíveis (otimizada) ===
    table_fields = [
        "NUP",
        "Devedor_Nome",
        "NumeroCreditoSistemaOriginario",
        "ValorOriginario",
        "DataConstituicaoDefinitiva",
        "FaseAtual_Status",
    ]

    table_doc = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(f)) for f in table_fields],
        rows=[],
        expand=True,
        visible=True,
        data_text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE),
    )

    # === Funções UI ===
    def adicionar_log(mensagem: str):
        try:
            log_doc.value += f"\n{mensagem}"
            page.update()
        except Exception:
            pass

    def atualizar_tabela():
        nonlocal page_index
        total = len(paginated)
        total_text_doc.value = f"Total: {total}"

        pages = max(1, (total + items_per_page - 1) // items_per_page)
        page_index = max(1, min(page_index, pages))
        start, end = (page_index - 1) * items_per_page, page_index * items_per_page

        table_doc.rows = [
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(str(r.get(col, ""))))
                    for col in table_fields
                ]
            )
            for r in paginated[start:end]
        ]

        paginador_doc.value = f"{page_index}/{pages}"

        has_data = total > 0
        container_tabela_doc.visible = has_data
        table_doc.visible = has_data
        btn_prev_doc.visible = has_data
        btn_next_doc.visible = has_data
        btn_export_doc.visible = has_data

        btn_prev_doc.disabled = page_index == 1
        btn_next_doc.disabled = page_index == pages

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
            alerta_dialogo=alerta_dialogo,
        )

    # === Fluxo principal ===
    def run_consult(e):
        nonlocal paginated, all_records, page_index

        entrada_raw = [
            ln.strip()
            for ln in (doc_field.value or "").splitlines()
            if ln.strip()
        ]

        buscar_por_raiz = bool(toggle_buscar_raiz_cnpj.value)

        if buscar_por_raiz:
            erros, itens_consulta = validar_raizes_cnpj(entrada_raw)
            titulo_validacao = "Validação de Raiz de CNPJ"
            descricao_consulta = "raiz(es) de CNPJ"
            itens_formatados = [formatar_raiz_cnpj(i) for i in itens_consulta]
        else:
            erros, itens_consulta = validar_documentos(entrada_raw)
            titulo_validacao = "Validação de CPF/CNPJ"
            descricao_consulta = "documento(s)"
            itens_formatados = [formatar_cpf_cnpj(i) for i in itens_consulta]

        if erros:
            log_doc.value = "❌ " + "\n❌ ".join(erros)
            page.dialog = alerta_dialogo
            mostrar_alerta(
                ft,
                page,
                titulo_validacao,
                "\n".join(erros),
                tipo="error",
            )
            page.update()
            return

        # UI init
        btn_consultar_doc.disabled = True
        progress_doc.visible = True
        status_doc.visible = True
        status_doc.value = "Iniciando login e obtenção do token..."
        log_doc.value = (
            f"🧹 Iniciando varredura para {len(itens_consulta)} {descricao_consulta}..."
        )
        total_text_doc.value = "Total: 0"
        container_tabela_doc.visible = False
        btn_export_doc.visible = False
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
                    mostrar_alerta(
                        ft,
                        page,
                        "Falha no login",
                        "Token inválido ou expirado.",
                        tipo="error",
                    )
                    page.update()
                    return

                status_doc.value = "✅ Token obtido! Iniciando consultas..."
                page.update()

                all_records, paginated = [], []
                encontrados_total = 0

                if buscar_por_raiz:
                    status_doc.value = (
                        f"Consultando {len(itens_consulta)} raiz(es) de CNPJ..."
                    )
                    page.update()

                    resultado = get_dados_creditos_raizes_devedores_sapiens(
                        token=token,
                        raizes=itens_consulta,
                        log=adicionar_log,
                    )

                    records = resultado.get("records") or resultado.get("Data") or []
                    erros_request = resultado.get("Erros") or resultado.get("erros") or []

                    encontrados_total = len(records)
                    all_records.extend(records)
                    paginated.extend(montar_linha_tabela(r) for r in records)

                    for erro in erros_request[:20]:
                        adicionar_log(
                            f"❌ Raiz {erro.get('Raiz')}: {erro.get('Erro')}"
                        )

                    if not records:
                        adicionar_log(
                            "🔎 Nenhum registro localizado para as raízes informadas."
                        )
                    else:
                        adicionar_log(
                            f"✅ Consulta por raiz finalizada: {encontrados_total} registro(s) capturado(s)."
                        )

                else:
                    total_docs = len(itens_consulta)

                    for idx, doc in enumerate(itens_consulta, start=1):
                        doc_formatado = itens_formatados[idx - 1]
                        status_doc.value = f"Consultando {idx}/{total_docs}: {doc_formatado}"
                        page.update()

                        try:
                            res = get_creditos_sapiens(
                                token,
                                doc,
                                log=adicionar_log,
                            )
                            records = res.get("records", []) or []
                            qtd = len(records)

                            if qtd == 0:
                                adicionar_log(
                                    f"🔎 {doc_formatado}: nenhum registro localizado."
                                )
                            else:
                                adicionar_log(
                                    f"✅ {doc_formatado}: {qtd} registro(s) capturado(s) com sucesso."
                                )
                                encontrados_total += qtd
                                all_records.extend(records)
                                paginated.extend(montar_linha_tabela(r) for r in records)

                        except Exception as ex_consulta:
                            adicionar_log(
                                f"❌ Erro ao consultar {doc_formatado}: {ex_consulta}"
                            )

                # 🔹 3. Atualiza a tabela e status final
                page_index = 1
                status_doc.value = (
                    "⚠ Nenhum registro localizado"
                    if encontrados_total == 0
                    else f"📦 {encontrados_total} registro(s) localizado(s) no total"
                )
                atualizar_tabela()

            except Exception as ex:
                adicionar_log(f"❌ Erro geral: {ex}")
                status_doc.value = "Erro durante a execução"
            finally:
                progress_doc.visible = False
                btn_consultar_doc.disabled = False
                btn_consultar_doc.text = "Consultar novamente"
                desbloquear()
                page.update()

        threading.Thread(target=task, daemon=True).start()

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
        visible=False,
    )

    children = [
        ft.Row(
            [
                ft.Text(
                    "SUPER SAPIENS > Consulta Crédito Dívida",
                    size=10,
                    weight="bold",
                )
            ],
            alignment="center",
        ),
        ft.Divider(),
        ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [doc_field, btn_consultar_doc],
                        wrap=True,
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    toggle_buscar_raiz_cnpj,
                    txt_ajuda_raiz,
                ],
                spacing=6,
            ),
            padding=10,
            border_radius=10,
            border=ft.border.all(1, ft.Colors.GREY_600),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        ),
        status_doc,
        progress_doc,
        container_tabela_doc,
        ft.Row(
            [btn_prev_doc, paginador_doc, btn_next_doc, total_text_doc],
            alignment="center",
        ),
        ft.Row([btn_export_doc], alignment="center"),
        msg_export_doc,
        log_doc,
        alerta_dialogo,
    ]

    return ft.Column(children, expand=True, spacing=10)
