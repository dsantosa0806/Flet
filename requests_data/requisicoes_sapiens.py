import requests


def get_creditos_sapiens(token: str, documento: str) -> dict:
    """
    Consulta créditos no Super Sapiens usando o endpoint /v1/divida/credito.
    Percorre todas as páginas até coletar todos os registros disponíveis.
    Exibe logs progressivos com a quantidade de itens varridos.
    """
    if not token:
        raise RuntimeError("Token inválido — não foi fornecido JWT.")

    base_url = (
        "https://supersapiensbackend.agu.gov.br/v1/divida/credito"
        "?where=%7B%22andX%22%3A%5B%7B%22devedorPrincipal.numeroDocumentoPrincipal%22%3A%22eq%3A"
        f"{documento}%22%7D%5D%7D"
        "&limit=100&offset={offset}&order=%7B%7D"
        "&populate=%5B%22credor%22%2C%22credor.pessoa%22%2C%22faseAtual%22%2C%22faseAtual.especieStatus%22%2C"
        "%22unidadeResponsavel%22%2C%22especieStatusAtual%22%2C%22processo%22%2C%22processo.documentoAvulsoOrigem%22%2C"
        "%22vinculacoesEtiquetas%22%2C%22vinculacoesEtiquetas.etiqueta%22%2C%22vinculacaoLoteAtual%22%2C"
        "%22vinculacaoLoteAtual.lote%22%2C%22especieCredito%22%2C%22devedorPrincipal%22%2C%22regional%22%2C"
        "%22modalidadeDocumentoOrigem%22%2C%22certidaoDividaAtivaAtual%22%2C%22certidaoDividaAtivaCancelada%22%2C"
        "%22usuarioInscricaoDivida%22%2C%22unidadeInscricaoDivida%22%2C%22creditoOrigem%22%2C%22criadoPor%22%2C"
        "%22atualizadoPor%22%5D&context=%7B%7D"
    )

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Origin": "https://supersapiens.agu.gov.br",
        "Referer": "https://supersapiens.agu.gov.br/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
        ),
    }

    registros = []
    offset = 0
    limit = 100
    pagina = 1

    try:
        while True:
            url = base_url.format(offset=offset)
            resp = requests.get(url, headers=headers, timeout=60)

            if resp.status_code != 200:
                raise RuntimeError(f"Erro HTTP {resp.status_code}: {resp.text[:300]}")

            data = resp.json()
            entidades = data.get("entities", [])
            if not entidades:
                break

            for item in entidades:
                registros.append({
                    "id": item.get("id"),
                    "numeroCredito": item.get("numeroCredito"),  # 🆕 incluído aqui
                    "numeroCreditoSistemaOriginario": item.get("numeroCreditoSistemaOriginario"),
                    "valorOriginario": item.get("valorOriginario"),
                    "dataVencimento": item.get("dataVencimento"),
                    "dataInicioMultaMora": item.get("dataInicioMultaMora"),
                    "dataInicioSelic": item.get("dataInicioSelic"),
                    "descricaoComplementoFundamentoLegal": item.get("descricaoComplementoFundamentoLegal"),
                    "dataConstituicaoDefinitiva": item.get("dataConstituicaoDefinitiva"),
                    "defesaApresentada": item.get("defesaApresentada"),
                    "dataNotificacaoInicial": item.get("dataNotificacaoInicial"),
                    "dataDecursoPrazoDefesa": item.get("dataDecursoPrazoDefesa"),
                    "postIt": item.get("postIt"),
                    "dataDocumentoOrigem": item.get("dataDocumentoOrigem"),
                    "numeroDocumentoOrigem": item.get("numeroDocumentoOrigem"),
                    "saldoAtualizado": item.get("saldoAtualizado"),
                    "dataAtualizacao": item.get("dataAtualizacao"),
                    "dataInscricaoDivida": item.get("dataInscricaoDivida"),
                    "valorInscricaoDivida": item.get("valorInscricaoDivida"),
                    "numeroInscricaoDivida": item.get("numeroInscricaoDivida"),
                    "raizDevedorPrincipal": item.get("raizDevedorPrincipal"),
                    "devedorPrincipal": item.get("devedorPrincipal"),
                    "credor": item.get("credor"),
                    "regional": item.get("regional"),
                    "unidadeResponsavel": item.get("unidadeResponsavel"),
                    "faseAtual": item.get("faseAtual"),
                    "certidaoDividaAtivaAtual": item.get("certidaoDividaAtivaAtual"),
                    "criadoPor": item.get("criadoPor"),
                    "atualizadoPor": item.get("atualizadoPor"),
                    "processo": item.get("processo"),
                })

            print(f"✅ Página {pagina} — {len(entidades)} registros (total: {len(registros)})")

            if len(entidades) < limit:
                break

            offset += limit
            pagina += 1

        print(f"\n📊 Total de registros coletados: {len(registros)}\n")
        return {"total": len(registros), "records": registros}

    except Exception as ex:
        print(f"❌ Falha na requisição Super Sapiens: {ex}")
        return {"total": 0, "records": []}
