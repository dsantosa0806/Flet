import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import requests



def acessa_sapiens(navegador):
    try:
        # Acesso a tela de login
        url_login = 'https://sapiens.agu.gov.br'
        navegador.get(url_login)
    except:
        print('Erro', 'O SAPIENS apresentou instabilidade, '
                      'por favor reinicie a aplicação e tente novamente T:acessa_SAPIENS ')


def login(navegador, usuario, senha):
    username = usuario
    userpass = senha
    err = True
    # Tratamento de erro
    while err:
        try:
            WebDriverWait(navegador, 30).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="cpffield-1017-inputEl"]'))).send_keys(username)
            WebDriverWait(navegador, 30).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="textfield-1018-inputEl"]'))).send_keys(userpass)
            navegador.find_element(By.XPATH, '//*[@id="button-1019-btnInnerEl"]').click()
            WebDriverWait(navegador, 30).until(
                EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="painelUsuario_header_hd-textEl"]'))).is_displayed()
            err = False
            print('Logado')
            time.sleep(2)

        except TimeoutException:
            print("loading...")


def acessa_divida(navegador):
    try:
        navegador.get(f'https://sapiens.agu.gov.br/divida')
    except:
        return 1


def get_creditos_sapiens(navegador, documento: str) -> dict:
    # Extrair cookies da sessão selenium
    selenium_cookies = navegador.get_cookies()
    cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
    url = "https://sapiens.agu.gov.br/route"

    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://sapiens.agu.gov.br",
        "Referer": "https://sapiens.agu.gov.br/divida",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    }

    page = 1
    limit = 100
    todos_registros = []

    while True:
        payload = {
            "action": "SapiensDivida_Credito",
            "method": "getCredito",
            "data": [{
                "fetch": [
                    "pasta", "criadoPor", "atualizadoPor", "modalidadeDocumentoOrigem", "especieCredito",
                    "especieCredito.vinculacoesEspeciesFundamentosLegais",
                    "especieCredito.vinculacoesEspeciesFundamentosLegais.fundamentoLegal",
                    "especieCredito.vinculacoesEspeciesFundamentosLegais.fundamentoLegal.modalidadeFundamentoLegal",
                    "faseAtual", "faseAtual.especieStatus", "devedorPrincipal",
                    "devedorPrincipal.enderecos", "devedorPrincipal.enderecos.municipio",
                    "devedorPrincipal.enderecos.municipio.estado",
                    "devedorPrincipal.cadastrosIdentificadores", "credor", "credor.pessoa", "regional",
                    "unidadeResponsavel", "unidadeInscricaoDivida", "numeroUnicoIdentificacao",
                    "usuarioInscricaoDivida", "documentoTermoInscricaoDivida",
                    "documentoTermoInscricaoDivida.tipoDocumento",
                    "documentoTermoInscricaoDivida.componentesDigitais",
                    "documentoTermoInscricaoDivida.componentesDigitais.assinaturas",
                    "creditoOrigem", "certidaoDividaAtivaAtual", "certidaoDividaAtivaCancelada"
                ],
                "filter": [{
                    "property": "devedorPrincipal.cadastrosIdentificadores.numero",
                    "value": f"eq:{documento}"
                }],
                "page": page,
                "start": (page - 1) * limit,
                "limit": limit
            }],
            "type": "rpc",
            "tid": page
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                cookies=cookies,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            registros = data[0]['result']['records']
            total = data[0]['result']['total']

            todos_registros.extend(registros)

            print(f"✅ Página {page} - Registros: {len(registros)} / Total: {total}")

            if len(todos_registros) >= total:
                break

            page += 1

        except Exception as ex:
            print(f"❌ Erro ao requisitar página {page}: {ex}")
            break

    json_result = {
        "total": len(todos_registros),
        "records": todos_registros
    }

    return json_result


def formatar_documento(documento: str) -> str:
    """Formata CPF ou CNPJ conforme o tamanho."""
    if not documento:
        return ''
    documento = ''.join(filter(str.isdigit, documento))
    if len(documento) == 11:
        return f"{documento[:3]}.{documento[3:6]}.{documento[6:9]}-{documento[9:]}"
    elif len(documento) == 14:
        return f"{documento[:2]}.{documento[2:5]}.{documento[5:8]}/{documento[8:12]}-{documento[12:]}"
    else:
        return documento


def formatar_nup(nup: str) -> str:
    """Formata NUP no padrão xxxxx.xxxxxx/xxxx-xx."""
    if not nup or len(nup) != 17:
        return nup
    return f"{nup[:5]}.{nup[5:11]}/{nup[11:15]}-{nup[15:]}"


def extrair_dados_response_dataframe(registros: list) -> pd.DataFrame:
    """
    Extrai informações específicas da lista de registros do Sapiens Dívida e retorna um DataFrame formatado.

    Dados extraídos e formatados:
    - NUP (com formatação XXXXX.XXXXXX/XXXX-XX)
    - outroNumero (de pasta)
    - raizDevedorPrincipal (formatação CPF/CNPJ)
    - nome da especieCredito
    - nome da especieStatus (de faseAtual)
    - nome do devedorPrincipal
    - postIt do devedorPrincipal

    Parâmetro:
    - registros: lista de dicionários retornados pela função get_credito_sapiens_com_filtros

    Retorna:
    - DataFrame com os dados extraídos e formatados
    """
    dados_extraidos = []

    try:
        for item in registros:
            nup = item.get('pasta', {}).get('NUP', '')
            raiz = item.get('raizDevedorPrincipal', '')

            dado = {
                'NUP': formatar_nup(nup),
                'OutroNumero': item.get('pasta', {}).get('outroNumero', ''),
                'RaizDevedorPrincipal': formatar_documento(raiz),
                'EspecieCredito': item.get('especieCredito', {}).get('nome', ''),
                'FaseAtual_Status': item.get('faseAtual', {}).get('especieStatus', {}).get('nome', ''),
                'Devedor_Nome': item.get('devedorPrincipal', {}).get('nome', ''),
                'Devedor_PostIt': item.get('postIt', '')
            }
            dados_extraidos.append(dado)

        df = pd.DataFrame(dados_extraidos)
        return df

    except Exception as e:
        print(f"Erro na extração dos dados: {e}")
        return pd.DataFrame()