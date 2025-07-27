import requests


def get_creditos_sapiens(cookies: dict, documento: str) -> dict:
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
            response = requests.post(url, headers=headers, cookies=cookies, json=payload)

            if response.status_code != 200:
                print(f"❌ Erro HTTP {response.status_code}: {response.text[:200]}")
                break

            data = response.json()

            if not isinstance(data, list) or not data or "result" not in data[0]:
                print(f"❌ Estrutura de resposta inválida: {data}")
                break

            registros = data[0]["result"]["records"]
            total = data[0]["result"]["total"]

            todos_registros.extend(registros)
            print(f"✅ Página {page} - Registros: {len(registros)} / Total: {total}")

            if len(todos_registros) >= total:
                break

            page += 1

        except Exception as ex:
            print(f"❌ Erro ao requisitar página {page}: {ex}")
            break

    return {
        "total": len(todos_registros),
        "records": todos_registros
    }
