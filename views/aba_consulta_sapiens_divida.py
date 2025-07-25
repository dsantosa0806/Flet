import os
import re
import json
import threading
import pandas as pd
from datetime import datetime
from selenium import webdriver
from navegador.sapiens_selenium_execution import acessa_sapiens, login as sapiens_login, get_creditos_sapiens


# === Funções auxiliares ===
def carregar_credenciais():
    caminho = os.path.join(os.path.expanduser("~"), ".sapiens_cache.json")
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("user"), data.get("password")
        except Exception:
            return None, None
    return None, None


def salvar_credenciais(user, password):
    caminho = os.path.join(os.path.expanduser("~"), ".sapiens_cache.json")
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"user": user, "password": password}, f)
    except Exception as ex:
        print(f"Erro ao salvar credenciais: {ex}")


def exportar_para_excel(registros, nome_prefixo, mensagem_sucesso, mensagem_falha, msg_output, page):
    try:
        df_out = pd.DataFrame(registros)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        caminho = os.path.join(os.path.expanduser("~"), "Downloads", f"{nome_prefixo}_{ts}.xlsx")
        df_out.to_excel(caminho, index=False)
        msg_output.value = mensagem_sucesso
    except Exception as ex:
        msg_output.value = f"{mensagem_falha}: {ex}"
    msg_output.visible = True
    page.update()
    threading.Timer(3, lambda: (setattr(msg_output, 'visible', False), page.update())).start()


# === ABA ===
def aba_consulta_sapiens(ft, DEFAULT_FONT_SIZE, HEADING_FONT_SIZE, page):
    # Estado
    page_index = 1
    items_per_page = 5
    paginated, all_records = [], []

    cached_user, cached_pass = carregar_credenciais()

    txt_user_sapiens = ft.TextField(label="Usuário Sapiens", width=300) if not cached_user else None
    txt_pass_sapiens = ft.TextField(label="Senha Sapiens", width=300, password=True) if not cached_user else None

    doc_field = ft.TextField(label="CPF ou CNPJ do Devedor", width=300)
    btn_consultar_doc = ft.ElevatedButton("Consultar", icon=ft.Icons.SEARCH)
    status_doc = ft.Text("", visible=False, color="blue")
    progress_doc = ft.ProgressBar(width=400, visible=False)
    log_doc = ft.TextField(label="📝 Log de Consulta Sapiens", multiline=True, read_only=True, height=150, expand=True)

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
            registros=all_records,
            nome_prefixo="Sapiens_All",
            mensagem_sucesso="📤 Exportado!",
            mensagem_falha="❌ Falha ao exportar",
            msg_output=msg_export_doc,
            page=page
        )

    def run_consult(e):
        nonlocal paginated, all_records, page_index, cached_user, cached_pass

        doc = ''.join(filter(str.isdigit, doc_field.value or ''))
        if len(doc) not in (11, 14):
            log_doc.value = "CPF/CNPJ inválido"
            page.update()
            return

        if cached_user:
            user, pwd = cached_user, cached_pass
        else:
            user = txt_user_sapiens.value.strip()
            pwd = txt_pass_sapiens.value.strip()
            if not user or not pwd:
                log_doc.value = "Informe usuário/senha"
                page.update()
                return
            salvar_credenciais(user, pwd)

        doc_field.value = doc
        btn_consultar_doc.disabled = True
        progress_doc.visible = True
        status_doc.visible = True
        status_doc.value = "Iniciando"
        log_doc.value = ""
        total_text_doc.value = "Total: 0"
        paginador_doc.value = ""
        for w in [btn_prev_doc, btn_next_doc, btn_export_doc]:
            w.visible = False
        page.update()

        def task():
            nonlocal paginated, all_records, page_index
            try:
                nav = webdriver.Chrome()
                acessa_sapiens(nav)
                sapiens_login(nav, user, pwd)
                status_doc.value = "Buscando"
                page.update()
                res = get_creditos_sapiens(nav, doc)
                nav.quit()
                all_records = res.get("records", [])
                paginated = [
                    {
                        'NUP': r.get('pasta', {}).get('NUP', ''),
                        'OutroNumero': r.get('pasta', {}).get('outroNumero', ''),
                        'RaizDevedorPrincipal': r.get('raizDevedorPrincipal', ''),
                        'EspecieCredito': r.get('especieCredito', {}).get('nome', ''),
                        'FaseAtual_Status': r.get('faseAtual', {}).get('especieStatus', {}).get('nome', ''),
                        'Devedor_Nome': r.get('devedorPrincipal', {}).get('nome', ''),
                        'Devedor_PostIt': r.get('postIt', '')
                    }
                    for r in all_records
                ]
                page_index = 1
                status_doc.value = f"{len(paginated)} registros encontrados"
                atualizar_tabela()
            except Exception as ex:
                log_doc.value = f"Erro: {ex}"
                status_doc.value = "Erro"
            finally:
                progress_doc.visible = False
                btn_consultar_doc.disabled = False
                page.update()

        threading.Thread(target=task).start()

    # Eventos
    btn_consultar_doc.on_click = run_consult
    btn_prev_doc.on_click = prev_page
    btn_next_doc.on_click = next_page
    btn_export_doc.on_click = export_all

    # Layout
    children = [ft.Text("📑 CONSULTA CRÉDITO SAPIENS DÍVIDA", size=HEADING_FONT_SIZE, weight="bold")]
    if txt_user_sapiens:
        children.append(ft.Row([txt_user_sapiens, txt_pass_sapiens]))
    children.append(ft.Row([doc_field, btn_consultar_doc]))
    children += [
        status_doc, progress_doc, table_doc,
        ft.Row([btn_prev_doc, paginador_doc, btn_next_doc, total_text_doc], alignment="center"),
        ft.Row([btn_export_doc], alignment="center"),
        msg_export_doc, log_doc
    ]

    return ft.Column(children, expand=True)
