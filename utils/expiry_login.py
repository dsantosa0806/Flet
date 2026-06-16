import os
import json
import base64
from datetime import datetime


# =========================================================
# DIRETÓRIOS PADRÃO DOS LOGINS
# =========================================================

def _get_config_attr(nome, padrao):
    try:
        import config
        return getattr(config, nome, padrao)
    except Exception:
        return padrao


DIRETORIOS_LOGIN = {
    "SIOR": {
        "diretorio": _get_config_attr("SIOR_COOKIES_DIR", r"C:\Cookies-Selenium"),
        "nomes_preferenciais": [
            ".SIOR_AUTH_prod_v2",
            "SIOR_AUTH",
            "AUTH",
        ],
    },
    "Sapiens": {
        "diretorio": _get_config_attr("SS_COOKIES_DIR", r"C:\Cookies-Selenium-SuperSapiens"),
        "nomes_preferenciais": [
            "token",
            "access_token",
            "Authorization",
            "authorization",
            "jwt",
            "id_token",
        ],
    },
    "CADIN": {
        "diretorio": _get_config_attr("CADIN_COOKIES_DIR", r"C:\Cookies-Selenium-Cadin"),
        "nomes_preferenciais": [
            "TOKEN_JWT",
            "token",
            "access_token",
            "Authorization",
            "authorization",
            "jwt",
            "auth",
        ],
    },
}


# =========================================================
# LEITURA E CONVERSÃO
# =========================================================

def converter_epoch_para_datetime_local(valor):
    """
    Converte epoch para horário local.

    Aceita:
    - segundos: 1781632688
    - milissegundos: 1781632688000
    """

    if valor is None:
        return None

    try:
        valor = int(float(valor))
    except Exception:
        return None

    try:
        if valor > 9999999999:
            valor = valor / 1000

        return datetime.fromtimestamp(valor)

    except Exception:
        return None


def ler_json(caminho):
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except Exception:
        return None


def listar_jsons(diretorio):
    arquivos_json = []

    if not diretorio or not os.path.exists(diretorio):
        return arquivos_json

    try:
        for raiz, _, arquivos in os.walk(diretorio):
            for nome in arquivos:
                if nome.lower().endswith(".json"):
                    arquivos_json.append(os.path.join(raiz, nome))
    except Exception:
        pass

    return arquivos_json


# =========================================================
# JWT
# =========================================================

def _b64url_decode(data):
    try:
        padding = len(data) % 4
        if padding:
            data += "=" * (4 - padding)

        return base64.urlsafe_b64decode(data.encode("utf-8"))
    except Exception:
        return None


def extrair_exp_de_jwt(token):
    """
    Extrai o campo exp de um JWT, caso exista.
    """

    if not isinstance(token, str):
        return None

    token = token.strip()

    if token.lower().startswith("bearer "):
        token = token.split(" ", 1)[1].strip()

    partes = token.split(".")

    if len(partes) != 3:
        return None

    payload_bytes = _b64url_decode(partes[1])

    if not payload_bytes:
        return None

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
        return converter_epoch_para_datetime_local(payload.get("exp"))
    except Exception:
        return None


# =========================================================
# CAPTURA DE EXPIRAÇÕES
# =========================================================

def _nome_preferencial(nome, nomes_preferenciais):
    if not nome:
        return False

    nome = str(nome).lower()

    for item in nomes_preferenciais:
        if str(item).lower() in nome:
            return True

    return False


def extrair_expiracoes(obj, caminho_arquivo, nomes_preferenciais):
    """
    Procura expiração em qualquer estrutura JSON.

    Suporta:
    - Cookies Selenium com "expiry"
    - Tokens com "exp"
    - JWT em campos "value", "token", "access_token", etc.
    """

    candidatos = []

    def adicionar_candidato(expiracao, nome, campo):
        if not expiracao:
            return

        candidatos.append({
            "expiracao": expiracao,
            "nome": nome,
            "campo": campo,
            "arquivo": caminho_arquivo,
            "preferencial": _nome_preferencial(nome, nomes_preferenciais),
        })

    def percorrer(valor, contexto_nome=None):
        if isinstance(valor, dict):
            nome = valor.get("name") or contexto_nome

            # Campos diretos de expiração
            for campo in ["expiry", "exp", "expires", "expirationDate", "expires_at", "expiresAt"]:
                if campo in valor:
                    expiracao = converter_epoch_para_datetime_local(valor.get(campo))
                    adicionar_candidato(expiracao, nome or campo, campo)

            # Campos que podem guardar JWT
            for campo_token in ["value", "token", "access_token", "id_token", "authorization", "Authorization"]:
                if campo_token in valor:
                    expiracao_jwt = extrair_exp_de_jwt(valor.get(campo_token))
                    adicionar_candidato(expiracao_jwt, nome or campo_token, f"{campo_token}.jwt.exp")

            # Continua aninhado
            for chave, subvalor in valor.items():
                percorrer(subvalor, nome or chave)

        elif isinstance(valor, list):
            for item in valor:
                percorrer(item, contexto_nome)

        elif isinstance(valor, str):
            expiracao_jwt = extrair_exp_de_jwt(valor)
            adicionar_candidato(expiracao_jwt, contexto_nome or "jwt", "jwt.exp")

    percorrer(obj)

    return candidatos


def obter_expiracao_login(nome_app, diretorio=None, nomes_preferenciais=None):
    """
    Retorna a expiração local de uma aplicação.

    Retorno:
    {
        "app": "SIOR",
        "expiracao": datetime | None,
        "expirado": bool,
        "icone": "✅" | "❌",
        "arquivo": str | None,
        "nome": str | None,
        "campo": str | None,
        "mensagem": str
    }
    """

    cfg = DIRETORIOS_LOGIN.get(nome_app, {})

    diretorio = diretorio or cfg.get("diretorio")
    nomes_preferenciais = nomes_preferenciais or cfg.get("nomes_preferenciais", [])

    arquivos_json = listar_jsons(diretorio)

    if not arquivos_json:
        return {
            "app": nome_app,
            "expiracao": None,
            "expirado": True,
            "icone": "❌",
            "arquivo": None,
            "nome": None,
            "campo": None,
            "mensagem": "sem arquivo",
        }

    candidatos = []

    for caminho in arquivos_json:
        data = ler_json(caminho)

        if data is None:
            continue

        candidatos.extend(
            extrair_expiracoes(
                obj=data,
                caminho_arquivo=caminho,
                nomes_preferenciais=nomes_preferenciais,
            )
        )

    if not candidatos:
        return {
            "app": nome_app,
            "expiracao": None,
            "expirado": True,
            "icone": "❌",
            "arquivo": arquivos_json[0],
            "nome": None,
            "campo": None,
            "mensagem": "sem expiração",
        }

    agora = datetime.now()

    # Prioriza cookies/tokens conhecidos da aplicação
    preferenciais = [c for c in candidatos if c.get("preferencial")]
    base = preferenciais if preferenciais else candidatos

    # Se houver expirações futuras, usa a menor futura
    futuros = [c for c in base if c.get("expiracao") and c["expiracao"] > agora]

    if futuros:
        escolhido = min(futuros, key=lambda c: c["expiracao"])
    else:
        escolhido = max(base, key=lambda c: c["expiracao"])

    expiracao = escolhido.get("expiracao")
    expirado = not expiracao or expiracao <= agora

    return {
        "app": nome_app,
        "expiracao": expiracao,
        "expirado": expirado,
        "icone": "❌" if expirado else "✅",
        "arquivo": escolhido.get("arquivo"),
        "nome": escolhido.get("nome"),
        "campo": escolhido.get("campo"),
        "mensagem": "expirado" if expirado else "válido",
    }


# =========================================================
# FORMATADORES PARA O APP.PY
# =========================================================

def formatar_expiracao_login(nome_app):
    info = obter_expiracao_login(nome_app)

    icone = info.get("icone", "❌")
    expiracao = info.get("expiracao")

    if not expiracao:
        return f"{icone} {nome_app}: sem expiração"

    data_hora = expiracao.strftime("%d/%m/%Y %H:%M")

    if info.get("expirado"):
        return f"{icone} {nome_app}: expirado em {data_hora}"

    return f"{icone} {nome_app}: expira em {data_hora}"


def obter_texto_expiracoes_login():
    """
    Texto simples para exibir no cabeçalho do app.py.
    """

    partes = [
        formatar_expiracao_login("SIOR"),
        formatar_expiracao_login("Sapiens"),
        formatar_expiracao_login("CADIN"),
    ]

    return "  |  ".join(partes)