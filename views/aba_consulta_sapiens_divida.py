import os
import json
import threading
import pandas as pd
from datetime import datetime
from selenium import webdriver
from navegador.sapiens_selenium_execution import login as sapiens_login, options_nav
from requests_data.requisicoes_sapiens import get_creditos_sapiens
from utils.popups import mostrar_alerta
import config

COOKIE_PATH_SAPIENS = config.COOKIE_PATH_SAPIENS


# === Funções auxiliares ===
def carregar_credenciais():
    caminho = COOKIE_PATH_SAPIENS
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("user"), data.get("password")
        except Exception:
            return None, None
    return None, None


def salvar_credenciais(user, password):
    caminho = COOKIE_PATH_SAPIENS
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"user": user, "password": password}, f)
    except Exception as ex:
        print(f"Erro ao salvar credenciais: {ex}")


def exportar_para_excel(ft,
                        registros,
                        nome_prefixo,
                        mensagem_sucesso,
                        mensagem_falha,
                        msg_output,
                        page,
                        alerta_dialogo):
    try:
        campos_data = [
            'dataVencimento', 'dataInicioMultaMora', 'dataInicioSelic',
            'dataConstituicaoDefinitiva', 'dataNotificacaoInicial',
            'dataDecursoPrazoDefesa', 'dataDocumentoOrigem', 'criadoEm', 'atualizadoEm',
            'dataInscricaoDivida', 'dataValidadeAtualizacao', 'dataAtualizacao'
        ]

        for registro in registros:
            # ⏱️ Formatando campos de data
            for campo in campos_data:
                valor = registro.get(campo)
                if isinstance(valor, dict) and 'date' in valor:
                    try:
                        data_original = valor['date'].split(' ')[0]
                        ano, mes, dia = data_original.split('-')
                        registro[campo] = f"{dia}/{mes}/{ano}"
                    except Exception:
                        registro[campo] = ""

            # 📄 Formatando CPF/CNPJ
            doc_raw = registro.get("devedorPrincipal", {}).get("numeroDocumentoPrincipal", "")
            doc_formatado = ""
            if str(doc_raw).isdigit():
                if len(doc_raw) == 11:
                    doc_formatado = f"{doc_raw[:3]}.{doc_raw[3:6]}.{doc_raw[6:9]}-{doc_raw[9:]}"
                elif len(doc_raw) == 14:
                    doc_formatado = f"{doc_raw[:2]}.{doc_raw[2:5]}.{doc_raw[5:8]}/{doc_raw[8:12]}-{doc_raw[12:]}"
                else:
                    doc_formatado = doc_raw
            registro["Devedor_DocumentoFormatado"] = doc_formatado

            # 📂 NUP
            registro["NUP"] = registro.get("pasta", {}).get("NUP", "")

            # 👤 Criado/Atualizado por
            registro["CriadoPor_Nome"] = registro.get("criadoPor", {}).get("nome", "")
            registro["AtualizadoPor_Nome"] = registro.get("atualizadoPor", {}).get("nome", "")

            # 📝 Modalidade documento origem
            registro["ModalidadeDocumentoDescricao"] = registro.get("modalidadeDocumentoOrigem", {}).get("descricao", "")

            # 🔄 Fase Atual (nome - descrição)
            especie_status = registro.get("faseAtual", {}).get("especieStatus", {})
            nome = especie_status.get("nome", "")
            descricao = especie_status.get("descricao", "")
            registro["FaseAtual_Completa"] = f"{nome} - {descricao}".strip(" -") if (nome or descricao) else ""

            # 🏛️ Credor nome
            registro["Credor_Nome"] = registro.get("credor", {}).get("pessoa", {}).get("nome", "")

            # 🌎 Regional nome
            registro["Regional_Nome"] = registro.get("regional", {}).get("nome", "")

            # 🏢 Unidade Responsável (sigla - nome)
            unidade = registro.get("unidadeResponsavel", {})
            sigla = unidade.get("sigla", "")
            nome_unidade = unidade.get("nome", "")
            registro["UnidadeResponsavel_Completa"] = f"{sigla} - {nome_unidade}".strip(" -") if (sigla or nome_unidade) else ""

            # 🔎 Numero da CDA (se existir)
            cda = registro.get("certidaoDividaAtivaAtual", {})
            registro["NumeroCertidaoDividaAtiva"] = cda.get("numeroCertidaoDividaAtiva", "")

        # === DataFrames de saída ===
        df_out = pd.DataFrame(registros)

        # Campos desejados para a aba Resumo (somente os que existirem em df_out serão usados)
        campos_resumo_desejados = [
            "NUP",
            "Devedor_DocumentoFormatado",
            "FaseAtual_Completa",
            "UnidadeResponsavel_Completa",
            "numeroCreditoSistemaOriginario",
            "valorOriginario",
            "NumeroCertidaoDividaAtiva",
            "dataInscricaoDivida",
            "valorInscricaoDivida",
            "saldoAtualizado",
            "dataConstituicaoDefinitiva",
            "raizDevedorPrincipal",
        ]
        colunas_existentes = [c for c in campos_resumo_desejados if c in df_out.columns]
        df_resumo = df_out[colunas_existentes].copy() if colunas_existentes else pd.DataFrame()
        # Adiciona credor_id = 902
        df_resumo["credor_id"] = 902
        # Reposiciona credor_id como primeira coluna
        cols_ordenadas = ["credor_id"] + [c for c in df_resumo.columns if c != "credor_id"]
        df_resumo = df_resumo[cols_ordenadas]

        # === Gravação em duas abas ===
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        caminho = os.path.join(os.path.expanduser("~"), "Downloads", f"{nome_prefixo}_{ts}.xlsx")
        with pd.ExcelWriter(caminho) as writer:
            df_resumo.to_excel(writer, sheet_name="Resumo", index=False)
            df_out.to_excel(writer, sheet_name="Geral", index=False)

        msg_output.value = mensagem_sucesso
        page.dialog = alerta_dialogo
        mostrar_alerta(ft, page, "Exportado com sucesso", "✅ Disponível em C:\\Downloads", tipo="success")

    except Exception as ex:
        msg_output.value = f"{mensagem_falha}: {ex}"
        page.dialog = alerta_dialogo
        mostrar_alerta(ft, page, "Falha", "Uma falha ocorreu ao gerar o arquivo.", tipo="error")

    msg_output.visible = True
    page.update()
    threading.Timer(3, lambda: (setattr(msg_output, 'visible', False), page.update())).start()


# === ABA ===
def aba_consulta_sapiens(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page, bloquear, desbloquear):
    # ===== Helpers locais =====
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

    # Estado
    page_index = 1
    items_per_page = 3
    paginated, all_records = [], []

    cached_user, cached_pass = carregar_credenciais()

    alerta_dialogo = ft.AlertDialog(
        modal=True,
        title=ft.Text(""),
        content=ft.Text(""),
        actions=[],
        open=False
    )

    # Campos SEMPRE visíveis e criados corretamente
    txt_user_sapiens = ft.TextField(
        label="Usuário Sapiens",
        width=300,
        value=cached_user or ""
    )

    txt_pass_sapiens = ft.TextField(
        label="Senha Sapiens",
        width=300,
        password=True,
        can_reveal_password=True,
        value=cached_pass or ""
    )
    credenciais_expander = ft.ExpansionTile(
        title=ft.Text("🔐 Credenciais Sapiens"),
        initially_expanded=False,
        controls=[ft.Row([txt_user_sapiens, txt_pass_sapiens])]
    )

    # 🔄 Agora aceita lista (até 5), um por linha
    doc_field = ft.TextField(
        label="CPF/CNPJ do(s) Devedor(es) (um por linha, até 5)",
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
        label="📝 Log de Consulta Sapiens",
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

    table_fields = [
        'NUP', 'OutroNumero', 'RaizDevedorPrincipal',
        'EspecieCredito', 'FaseAtual_Status',
        'Devedor_Nome', 'Devedor_PostIt'
    ]
    table_doc = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(f)) for f in table_fields],
        rows=[], expand=True, visible=True,
        data_text_style=ft.TextStyle(size=DEFAULT_FONT_SIZE)
    )

    def atualizar_tabela():
        nonlocal page_index
        total = len(paginated)
        total_text_doc.value = f"Total: {total}"
        pages = max(1, (total + items_per_page - 1) // items_per_page)
        page_index = max(1, min(page_index, pages))
        start, end = (page_index - 1) * items_per_page, page_index * items_per_page
        table_doc.rows = [
            ft.DataRow(cells=[ft.DataCell(ft.Text(str(r.get(col, '')))) for col in table_fields])
            for r in paginated[start:end]
        ]
        paginador_doc.value = f"{page_index}/{pages}"
        container_tabela_doc.visible = total > 0
        table_doc.visible = total > 0
        for w in [btn_prev_doc, btn_next_doc, btn_export_doc]:
            w.visible = total > 0

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

    def run_consult(e):
        nonlocal paginated, all_records, page_index, cached_user, cached_pass

        # 🔎 Coleta e saneamento dos documentos (até 5)
        docs_raw = [ln.strip() for ln in (doc_field.value or "").splitlines() if ln.strip()]
        if not docs_raw:
            log_doc.value = "⚠ Informe ao menos um CPF/CNPJ (um por linha, até 5)."
            page.update()
            return
        if len(docs_raw) > 5:
            log_doc.value = "⚠ Máximo de 5 documentos por consulta. Os 5 primeiros serão processados.\n"
            docs_raw = docs_raw[:5]

        docs = [limpar_numero(x) for x in docs_raw]
        invalidos = [formatar_cpf_cnpj(x) for x in docs if not is_cpf_cnpj(x)]
        if invalidos:
            log_doc.value = (log_doc.value + "\n" if log_doc.value else "") + \
                            "❌ Documento(s) inválido(s): " + ", ".join(invalidos)
            page.update()
            return

        user_input = txt_user_sapiens.value.strip()
        pass_input = txt_pass_sapiens.value.strip()
        if not user_input or not pass_input:
            log_doc.value = "⚠ Informe usuário e senha."
            page.update()
            return

        if user_input != cached_user or pass_input != cached_pass:
            salvar_credenciais(user_input, pass_input)
            cached_user, cached_pass = user_input, pass_input

        user, pwd = user_input, pass_input

        # UI init
        btn_consultar_doc.disabled = True
        progress_doc.visible = True
        status_doc.visible = True
        status_doc.value = "Iniciando"
        log_doc.value = (log_doc.value + "\n" if log_doc.value else "") + \
                        f"🧹 Iniciando varredura para {len(docs)} documento(s)..."
        total_text_doc.value = "Total: 0"
        paginador_doc.value = ""
        for w in [btn_prev_doc, btn_next_doc, btn_export_doc]:
            w.visible = False
        page.update()

        def task():
            nonlocal paginated, all_records, page_index
            try:
                bloquear()

                # Login uma única vez
                nav = webdriver.Chrome(options=options_nav())
                nav.minimize_window()
                nav, cookies = sapiens_login(nav, user, pwd)

                if not cookies:
                    status_doc.value = "❌ Falha no login. Usuário ou senha incorreto."
                    page.dialog = alerta_dialogo
                    mostrar_alerta(ft, page, "Falha no login", "Usuário ou senha incorreto.", tipo="error")
                    page.update()
                    return

                status_doc.value = "🔐 Login OK. Iniciando consultas..."
                page.update()

                # 🔁 Loop por documento
                all_records = []
                paginated = []
                total_docs = len(docs)
                encontrados_total = 0

                for idx, doc in enumerate(docs, start=1):
                    status_doc.value = f"Consultando {idx}/{total_docs}: {formatar_cpf_cnpj(doc)}"
                    page.update()

                    try:
                        res = get_creditos_sapiens(cookies, doc)
                        records = res.get("records", []) or []
                        qtd = len(records)
                        if qtd == 0:
                            log_doc.value += f"\n🔎 {formatar_cpf_cnpj(doc)}: nenhum registro localizado."
                        else:
                            log_doc.value += f"\n✅ {formatar_cpf_cnpj(doc)}: {qtd} registro(s) capturado(s) com sucesso."
                            encontrados_total += qtd
                            all_records.extend(records)
                            paginated.extend([
                                {
                                    'NUP': r.get('pasta', {}).get('NUP', ''),
                                    'OutroNumero': r.get('pasta', {}).get('outroNumero', ''),
                                    'RaizDevedorPrincipal': r.get('raizDevedorPrincipal', ''),
                                    'EspecieCredito': r.get('especieCredito', {}).get('nome', ''),
                                    'FaseAtual_Status': r.get('faseAtual', {}).get('especieStatus', {}).get('nome', ''),
                                    'Devedor_Nome': r.get('devedorPrincipal', {}).get('nome', ''),
                                    'Devedor_PostIt': r.get('postIt', '')
                                }
                                for r in records
                            ])
                    except Exception as ex_consulta:
                        log_doc.value += f"\n❌ Erro ao consultar {formatar_cpf_cnpj(doc)}: {ex_consulta}"

                nav.quit()

                # Atualiza tabela/contadores
                page_index = 1
                status_doc.value = ("⚠ Nenhum registro localizado"
                                    if encontrados_total == 0
                                    else f"📦 {encontrados_total} registro(s) localizado(s) no total")
                atualizar_tabela()

            except Exception as ex:
                log_doc.value += f"\n❌ Erro geral: {ex}"
                status_doc.value = "Erro"
            finally:
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

    # Layout
    children = [
        ft.Row([ft.Text("SAPIENS > Consulta Crédito Sapiens Dívida", size=10, weight="bold")], alignment="center"),
        ft.Divider(),
        credenciais_expander
    ]

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

    children.extend([
        ft.Row([doc_field, btn_consultar_doc]),
        status_doc,
        progress_doc,
        container_tabela_doc,
        ft.Row([btn_prev_doc, paginador_doc, btn_next_doc, total_text_doc], alignment="center"),
        ft.Row([btn_export_doc], alignment="center"),
        msg_export_doc,
        log_doc,
        alerta_dialogo
    ])

    return ft.Column(children, expand=True, spacing=10)