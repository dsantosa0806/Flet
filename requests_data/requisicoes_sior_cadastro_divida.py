import time  # Para gerar o valor do timestamp
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime


def enviar_requisicao_get(s, codigos_equipes=[1, 2, 3, 4, 5]):
    inicio = datetime.now()
    """
    Envia requisições GET para múltiplas equipes e retorna os dados combinados em um único DataFrame.
    """

    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://servicos.dnit.gov.br/sior/Cobranca/SupervisaoSapiensAcompanhamento",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Lt-Session-Guid": "",
        "X-Requested-With": "XMLHttpRequest",
        "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    }

    s.headers.update(headers)

    todos_dados = []

    for codigo in codigos_equipes:
        url = (
            f"https://servicos.dnit.gov.br/sior/Cobranca/SupervisaoSapiensAcompanhamento/List"
            f"?sort=&page=1&pageSize=10000&group=&filter=&equipeselecionada={codigo}"
            f"&faseselecionada=37&bind=true&calledfromapi=true&calledFromApi=true&"
        )

        try:
            response = s.get(url)

            if response.status_code == 200:
                json_result = response.json()

                if 'Data' in json_result and isinstance(json_result['Data'], list):
                    for item in json_result['Data']:
                        item['EquipeSelecionada'] = codigo  # adiciona a origem
                    todos_dados.extend(json_result['Data'])
                else:
                    print(f"[Equipe {codigo}] Retorno inválido ou sem dados.")

            else:
                print(f"[Equipe {codigo}] Erro HTTP {response.status_code}")

        except Exception as e:
            print(f"[Equipe {codigo}] Erro: {e}")

    # Criação do DataFrame final
    df = pd.DataFrame(todos_dados)

    # Conversão e formatação das colunas de data
    colunas_data = [
        'DataDistribuicaoEquipe',
        'DataDistribuicaoAnalise',
        'DataAnalise',
        'DataDistribuicaoConferencia',
        'DataConferencia'
    ]
    for col in colunas_data:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime("%d/%m/%Y")

    fim = datetime.now()
    duracao = fim - inicio
    print(f"Executado em {str(duracao).split('.')[0]}")
    return df


def get_data_sior(s, df):
    inicio = datetime.now()

    """
    Para cada Código de Processo de Infração no DataFrame,
    realiza uma requisição GET, extrai os campos com class 'lt-label',
    anexa a legenda (fieldset), trata valores em <a>, <textarea> e texto direto,
    e garante nomes únicos em caso de campos duplicados.
    """

    dados_extraidos = []

    for i, cod_infra in enumerate(df['CodigoProcessoInfracao'].unique(), start=1):
        url = f"https://servicos.dnit.gov.br/sior/Cobranca/CobrancaConsulta/DetailsPFE/{cod_infra}"
        s.headers.update({"Referer": url})

        try:
            response = s.get(url)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                labels = soup.find_all("label", class_="lt-label")

                dados_item = {"CodigoProcessoInfracao": cod_infra}
                contador_campos = {}

                for label in labels:
                    nome_campo = label.get_text(strip=True)

                    # Localiza o fieldset ascendente com legenda
                    fieldset = label.find_parent("fieldset")
                    legenda = fieldset.find("legend").get_text(strip=True) if fieldset and fieldset.find("legend") else None

                    # Adiciona legenda ao nome do campo
                    if legenda:
                        nome_campo = f"{nome_campo} - {legenda}"

                    # Trata os diferentes formatos de valor
                    valor = ""
                    if "Número do Auto" in nome_campo and label.find_next_sibling("a"):
                        valor = label.find_next_sibling("a").get_text(strip=True)
                    else:
                        textarea = label.find_next_sibling("textarea")
                        if textarea:
                            valor = textarea.get_text(strip=True)
                        else:
                            valor_texto = label.find_next_sibling(text=True)
                            valor = valor_texto.strip() if valor_texto else ""

                    # Garante nome único em caso de duplicatas
                    chave_base = nome_campo
                    contador_campos.setdefault(chave_base, 0)
                    contador_campos[chave_base] += 1
                    if contador_campos[chave_base] > 1:
                        nome_campo = f"{chave_base} [{contador_campos[chave_base]}]"

                    dados_item[nome_campo] = valor

                dados_extraidos.append(dados_item)

            else:
                print(f"[{cod_infra}] Erro HTTP {response.status_code}")

        except Exception as e:
            print(f"[{cod_infra}] Erro na requisição: {e}")

        # Pausa a cada 1000 requisições
        if i % 1000 == 0:
            # print(f"--- {i} requisições concluídas. Pausando por 60 segundos... ---")
            print(f"--- ✅ {i} requisições concluídas... {datetime.now().strftime("%d-%m-%Y (%H:%M:%S)")}")
            # time.sleep(60)

    # Converte lista de dicionários em DataFrame
    df_resultado = pd.DataFrame(dados_extraidos)
    df_resultado = df_resultado.groupby("CodigoProcessoInfracao").first().reset_index()

    fim = datetime.now()
    duracao = fim - inicio
    print(f"Executado em {str(duracao).split('.')[0]}")

    return df_resultado
