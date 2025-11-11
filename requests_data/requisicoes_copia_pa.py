# ===================[ REQUISIÇÕES CÓPIA DE P.A.s – SUPER SAPIENS (CORRIGIDO FINAL) ]===================
import requests
import base64
import os
import time

BACKEND = "https://supersapiensbackend.agu.gov.br"
PASTA_DOWNLOADS = r"C:\Downloads"


def buscar_processo_por_nup(token: str, nup: str):
    """Busca o ID do processo administrativo pelo NUP, testando formatos limpo e formatado."""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
    }

    # Remover formatação para usar em like
    nup_limpo = "".join(filter(str.isdigit, nup))

    # Tentar com campo NUPFormatado primeiro
    urls = [
        f"{BACKEND}/v1/administrativo/processo?where=%7B%22andX%22:%5B%7B%22NUPFormatado%22:%22eq:{nup}%22%7D%5D%7D",
        f"{BACKEND}/v1/administrativo/processo?where=%7B%22andX%22:%5B%7B%22NUP%22:%22like:{nup_limpo}%25%22%7D%5D%7D"
    ]

    for tentativa, url in enumerate(urls, start=1):
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            print(f"❌ Tentativa {tentativa}: erro {resp.status_code} na busca de processo.")
            continue

        try:
            dados = resp.json()
            if isinstance(dados, dict):
                entidades = dados.get("entities", [])
            elif isinstance(dados, list):
                entidades = dados
            else:
                entidades = []

            if entidades:
                processo_id = entidades[0].get("id")
                print(f"✅ Processo localizado (tentativa {tentativa}) → ID {processo_id}")
                return processo_id

        except Exception as e:
            print(f"⚠️ Erro ao processar resposta da tentativa {tentativa}: {e}")

    print(f"⚠️ Nenhum processo encontrado para NUP {nup}")
    return None


def gerar_relatorio_processo(token: str, processo_id: int):
    """Solicita a geração do relatório PDF do processo."""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
    }
    url = f"{BACKEND}/v1/administrativo/processo/{processo_id}/download/PDF/all"
    resp = requests.get(url, headers=headers)

    if resp.status_code == 200:
        print(f"📤 Relatório gerado para processo {processo_id}.")
        return True
    else:
        print(f"❌ Falha ao gerar relatório ({resp.status_code})")
        return False


def baixar_pdf_direto(token: str, processo_id: int, tentativas: int = 15, intervalo: int = 5):
    """
    Faz o download direto do PDF em base64 do componente digital mais recente do processo.
    """
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
    }

    for tentativa in range(1, tentativas + 1):
        # 🔹 Request direta ao endpoint do componente digital
        url = f"{BACKEND}/v1/administrativo/componente_digital/{processo_id}/download?context=%7B%7D&populate=%5B%5D"
        resp = requests.get(url, headers=headers)

        if resp.status_code == 200:
            try:
                dados = resp.json()
                conteudo = dados.get("conteudo", "")
                nome_arquivo = dados.get("fileName", f"{processo_id}.pdf")

                if not conteudo:
                    print(f"⚠️ Nenhum conteúdo retornado na tentativa {tentativa}.")
                    time.sleep(intervalo)
                    continue

                # Remove prefixo e decodifica base64
                if "," in conteudo:
                    conteudo = conteudo.split(",", 1)[1]

                pdf_bytes = base64.b64decode(conteudo)
                os.makedirs(PASTA_DOWNLOADS, exist_ok=True)
                caminho = os.path.join(PASTA_DOWNLOADS, nome_arquivo)

                with open(caminho, "wb") as f:
                    f.write(pdf_bytes)

                print(f"✅ PDF salvo com sucesso em: {caminho}")
                return caminho

            except Exception as e:
                print(f"⚠️ Erro ao processar base64 (tentativa {tentativa}): {e}")

        else:
            print(f"⚠️ Tentativa {tentativa}: {resp.status_code}")
        time.sleep(intervalo)

    print("❌ Não foi possível obter o PDF após várias tentativas.")
    return None


def fluxo_download_pa(nup_formatado: str, token: str):
    """
    Fluxo completo:
      1️⃣ Buscar processo
      2️⃣ Gerar relatório
      3️⃣ Fazer o download direto do PDF (base64)
    """
    try:
        print(f"🔎 Buscando processo para NUP {nup_formatado}...")
        processo_id = buscar_processo_por_nup(token, nup_formatado)
        if not processo_id:
            print(f"❌ Processo não encontrado para {nup_formatado}")
            return None

        print(f"✅ Processo encontrado: {nup_formatado} → ID {processo_id}")

        if not gerar_relatorio_processo(token, processo_id):
            print("❌ Falha ao gerar relatório PDF.")
            return None

        caminho_pdf = baixar_pdf_direto(token, processo_id)
        return caminho_pdf

    except Exception as e:
        print(f"❌ Erro no fluxo de {nup_formatado}: {e}")
        return None
