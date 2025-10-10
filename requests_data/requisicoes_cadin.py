import requests
import time
from typing import List, Dict, Any

def consultar_cadin(token: str, documentos: List[str]) -> List[Dict[str, Any]]:
    """
    Consulta o CADIN usando TOKEN_JWT manual.
    Retorna lista de registros detalhados para cada CPF/CNPJ consultado.
    """
    resultados = []
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0.0.0 Safari/537.36",
        "Origin": "https://cadin.pgfn.gov.br",
        "Referer": "https://cadin.pgfn.gov.br/",
    }

    base_url = "https://cadin.pgfn.gov.br/cadastro/apirest/registro"

    print(f"🚀 Iniciando consultas CADIN | Total: {len(documentos)} documentos")

    for i, doc in enumerate(documentos, start=1):
        doc_limpo = "".join(ch for ch in doc if ch.isdigit())
        tipo = "cnpj" if len(doc_limpo) == 14 else "cpf"
        url = f"{base_url}/{doc_limpo}/{tipo}"

        print(f"[{i}/{len(documentos)}] 🔍 Consultando {tipo.upper()}: {doc_limpo}")
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 200:
                dados = resp.json()

                # ✅ Caso a API retorne lista diretamente
                if isinstance(dados, list):
                    for registro in dados:
                        resultados.append({
                            "cpfCnpj": registro.get("cpfCnpj", ""),
                            "nome": registro.get("nome", ""),
                            "numeroTransacao": registro.get("numeroTransacao", ""),
                            "numeroReferencia": registro.get("numeroReferencia", ""),
                            "complementoReferencia": registro.get("complementoReferencia", ""),
                            "dataComunicacao": registro.get("dataComunicacao", ""),
                            "dataInadimplencia": registro.get("dataInadimplencia", ""),
                            "nomeInstituicao": registro.get("nomeInstituicao", ""),
                            "motivo": registro.get("motivo", ""),
                            "tipoTransacao": registro.get("tipoTransacao", ""),
                            "tipoAtualizacao": registro.get("tipoAtualizacao", ""),
                            "nivelFederativo": registro.get("nivelFederativo", ""),
                        })

                # ✅ Caso retorne dict com chave "registros"
                elif isinstance(dados, dict):
                    for registro in dados.get("registros", []):
                        resultados.append({
                            "cpfCnpj": registro.get("cpfCnpj", ""),
                            "nome": dados.get("nome", ""),
                            "numeroTransacao": registro.get("numeroTransacao", ""),
                            "numeroReferencia": registro.get("numeroReferencia", ""),
                            "complementoReferencia": registro.get("complementoReferencia", ""),
                            "dataComunicacao": registro.get("dataComunicacao", ""),
                            "dataInadimplencia": registro.get("dataInadimplencia", ""),
                            "nomeInstituicao": registro.get("nomeInstituicao", ""),
                            "motivo": registro.get("motivo", ""),
                            "tipoTransacao": registro.get("tipoTransacao", ""),
                            "tipoAtualizacao": registro.get("tipoAtualizacao", ""),
                            "nivelFederativo": registro.get("nivelFederativo", ""),
                        })

                else:
                    print(f"⚠️ Retorno inesperado: {type(dados)}")

            elif resp.status_code == 404:
                print(f"ℹ️ Nenhum registro encontrado para {doc_limpo}.")
            else:
                print(f"⚠️ HTTP {resp.status_code} | {resp.text[:150]}")

        except Exception as e:
            print(f"❌ Erro ao consultar {doc_limpo}: {e}")

        time.sleep(1.0)

    print(f"✅ Concluído. Total de registros coletados: {len(resultados)}")
    return resultados
