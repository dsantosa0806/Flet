# ==========================================================
# CORE - LICENCIAMENTO / RENOVAÇÃO MENSAL DA APLICAÇÃO
# ==========================================================
import getpass
import hashlib
import hmac
import json
import os
import platform
import socket
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Optional

import requests

import config


# ==========================================================
# MODELOS
# ==========================================================
@dataclass
class LicencaResultado:
    liberado: bool
    requer_senha: bool = False
    titulo: str = ""
    mensagem: str = ""
    origem: str = "online"
    politica: Dict[str, Any] = field(default_factory=dict)
    machine_id: str = ""
    mes_referencia: str = ""
    valido_ate: str = ""


# ==========================================================
# HELPERS BÁSICOS
# ==========================================================
def _hoje() -> date:
    return date.today()


def _agora_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_data_iso(valor: str) -> Optional[date]:
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except Exception:
        return None


def _sha256(texto: str) -> str:
    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


def _garantir_pasta_cache() -> None:
    pasta = os.path.dirname(config.LICENCA_CACHE_PATH)

    if pasta:
        os.makedirs(pasta, exist_ok=True)


def _ler_json_local(caminho: str) -> Dict[str, Any]:
    if not caminho or not os.path.exists(caminho):
        return {}

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

        return dados if isinstance(dados, dict) else {}

    except Exception:
        return {}


def _salvar_json_local(caminho: str, dados: Dict[str, Any]) -> None:
    pasta = os.path.dirname(caminho)

    if pasta:
        os.makedirs(pasta, exist_ok=True)

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(
            dados,
            arquivo,
            ensure_ascii=False,
            indent=4
        )


# ==========================================================
# IDENTIFICAÇÃO DA MÁQUINA
# ==========================================================
def obter_identidade_maquina() -> Dict[str, str]:
    """
    Gera um identificador estável da máquina.

    Importante:
    - O machine_id é um hash.
    - Não depende de um arquivo local.
    - Evita expor diretamente MAC, usuário e hostname.
    """

    try:
        hostname = platform.node() or socket.gethostname() or ""
    except Exception:
        hostname = ""

    try:
        usuario = getpass.getuser() or ""
    except Exception:
        usuario = ""

    try:
        mac = str(uuid.getnode())
    except Exception:
        mac = ""

    try:
        sistema = platform.system()
        release = platform.release()
        machine = platform.machine()
    except Exception:
        sistema = ""
        release = ""
        machine = ""

    base = "|".join(
        [
            hostname,
            usuario,
            mac,
            sistema,
            release,
            machine,
            config.APP_PROFILE,
            config.LICENCA_SALT,
        ]
    )

    machine_id = _sha256(base)

    return {
        "machine_id": machine_id,
        "hostname": hostname,
        "usuario": usuario,
        "sistema": sistema,
        "release": release,
        "machine": machine,
    }


# ==========================================================
# HASH DA SENHA MENSAL
# ==========================================================
def gerar_hash_senha_mensal(
    senha: str,
    mes_referencia: str,
    perfil: Optional[str] = None,
) -> str:
    """
    Gera o hash da senha mensal.

    O mesmo texto de senha gera hash diferente para USUARIO e ADMIN,
    porque o perfil entra na composição.
    """

    perfil = (perfil or config.APP_PROFILE or "").upper()

    texto = "|".join(
        [
            config.LICENCA_SALT,
            perfil,
            str(mes_referencia or "").strip(),
            str(senha or "").strip(),
        ]
    )

    return _sha256(texto)


def _obter_hash_esperado(politica: Dict[str, Any]) -> Optional[str]:
    """
    Aceita diferentes formatos de JSON para facilitar manutenção.

    Formato recomendado:
    {
      "mes_referencia": "2026-07",
      "senhas": {
        "2026-07": {
          "USUARIO": "hash...",
          "ADMIN": "hash..."
        }
      }
    }
    """

    mes = str(
        politica.get("mes_referencia") or ""
    ).strip()

    perfil = str(
        config.APP_PROFILE or ""
    ).upper()

    senhas = politica.get("senhas") or {}

    # Formato recomendado: senhas > mes > perfil
    try:
        valor = senhas.get(mes, {}).get(perfil)

        if valor:
            return str(valor).strip().lower()
    except Exception:
        pass

    # Formato alternativo: senhas > perfil > mes
    try:
        valor = senhas.get(perfil, {}).get(mes)

        if valor:
            return str(valor).strip().lower()
    except Exception:
        pass

    # Formato simples para JSON por perfil
    valor = (
        politica.get("senha_hash_sha256")
        or politica.get("hash_senha_sha256")
        or politica.get("password_hash_sha256")
    )

    if valor:
        return str(valor).strip().lower()

    return None


# ==========================================================
# POLÍTICA REMOTA
# ==========================================================
def baixar_politica_licenca(timeout: int = 8) -> Dict[str, Any]:
    """
    Baixa o JSON de licença do GitHub Pages.

    Usa parâmetro cache-buster para reduzir chance de cache antigo.
    """

    url = getattr(config, "URL_LICENCA", "")

    if not url:
        raise RuntimeError("URL_LICENCA não configurada no config.py.")

    params = {
        "_": int(datetime.now().timestamp())
    }

    response = requests.get(
        url,
        params=params,
        timeout=timeout,
        headers={
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )

    response.raise_for_status()

    dados = response.json()

    if not isinstance(dados, dict):
        raise RuntimeError("JSON de licença inválido.")

    return dados


def _hash_politica(politica: Dict[str, Any]) -> str:
    texto = json.dumps(
        politica,
        ensure_ascii=False,
        sort_keys=True
    )

    return _sha256(texto)


def _assinatura_cache(
    machine_id: str,
    perfil: str,
    mes_referencia: str,
    valido_ate: str,
    hash_politica: str,
) -> str:
    texto = "|".join(
        [
            config.LICENCA_SALT,
            machine_id,
            perfil,
            mes_referencia,
            valido_ate,
            hash_politica,
        ]
    )

    return _sha256(texto)


# ==========================================================
# VALIDAÇÕES DA POLÍTICA
# ==========================================================
def _validar_regras_politica(
    politica: Dict[str, Any],
    machine_id: str,
) -> LicencaResultado:
    perfil = str(config.APP_PROFILE or "").upper()

    if not politica.get("ativo", True):
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Aplicação bloqueada",
            mensagem=politica.get(
                "mensagem_bloqueio",
                "A aplicação está desativada temporariamente."
            ),
            politica=politica,
            machine_id=machine_id,
        )

    perfil_cfg = (
        politica.get("perfis", {})
        .get(perfil, {})
    )

    if perfil_cfg and not perfil_cfg.get("ativo", True):
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Perfil bloqueado",
            mensagem=f"O perfil {perfil} está desativado na política de licença.",
            politica=politica,
            machine_id=machine_id,
        )

    maquinas_bloqueadas = set(
        str(x).strip()
        for x in politica.get("maquinas_bloqueadas", [])
        if str(x).strip()
    )

    if machine_id in maquinas_bloqueadas:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Computador bloqueado",
            mensagem="Este computador está bloqueado para uso da aplicação.",
            politica=politica,
            machine_id=machine_id,
        )

    controlar_maquinas = bool(
        politica.get("controlar_maquinas", False)
    )

    maquinas_liberadas = set(
        str(x).strip()
        for x in politica.get("maquinas_liberadas", [])
        if str(x).strip()
    )

    if controlar_maquinas and maquinas_liberadas and machine_id not in maquinas_liberadas:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Computador não autorizado",
            mensagem=(
                "Este computador ainda não está na lista de máquinas autorizadas. "
                f"Machine ID: {machine_id[:16]}"
            ),
            politica=politica,
            machine_id=machine_id,
        )

    mes_referencia = str(
        politica.get("mes_referencia") or ""
    ).strip()

    valido_ate = str(
        politica.get("valido_ate") or ""
    ).strip()

    data_validade = _parse_data_iso(valido_ate)

    if not mes_referencia:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Licença mal configurada",
            mensagem="O JSON de licença não possui mes_referencia.",
            politica=politica,
            machine_id=machine_id,
        )

    if not data_validade:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Licença mal configurada",
            mensagem="O JSON de licença não possui valido_ate em formato YYYY-MM-DD.",
            politica=politica,
            machine_id=machine_id,
        )

    if _hoje() > data_validade:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Licença remota vencida",
            mensagem=(
                f"A licença publicada venceu em {valido_ate}. "
                "Atualize o JSON no GitHub com a nova competência mensal."
            ),
            politica=politica,
            machine_id=machine_id,
            mes_referencia=mes_referencia,
            valido_ate=valido_ate,
        )

    hash_esperado = _obter_hash_esperado(politica)

    if not hash_esperado:
        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Licença mal configurada",
            mensagem="O JSON de licença não possui hash de senha válido.",
            politica=politica,
            machine_id=machine_id,
            mes_referencia=mes_referencia,
            valido_ate=valido_ate,
        )

    return LicencaResultado(
        liberado=True,
        requer_senha=False,
        titulo="Política válida",
        mensagem="Política remota validada.",
        politica=politica,
        machine_id=machine_id,
        mes_referencia=mes_referencia,
        valido_ate=valido_ate,
    )


# ==========================================================
# CACHE LOCAL
# ==========================================================
def _cache_local_valido(
    cache: Dict[str, Any],
    machine_id: str,
    politica: Optional[Dict[str, Any]] = None,
    permitir_offline: bool = False,
) -> bool:
    if not cache:
        return False

    perfil = str(config.APP_PROFILE or "").upper()

    if cache.get("machine_id") != machine_id:
        return False

    if str(cache.get("perfil", "")).upper() != perfil:
        return False

    mes_referencia = str(cache.get("mes_referencia") or "").strip()
    valido_ate = str(cache.get("valido_ate") or "").strip()
    hash_politica = str(cache.get("hash_politica") or "").strip()

    data_validade = _parse_data_iso(valido_ate)

    if not mes_referencia or not data_validade:
        return False

    if _hoje() > data_validade:
        return False

    if politica is not None:
        hash_politica_atual = _hash_politica(politica)

        if hash_politica != hash_politica_atual:
            return False

    assinatura_esperada = _assinatura_cache(
        machine_id=machine_id,
        perfil=perfil,
        mes_referencia=mes_referencia,
        valido_ate=valido_ate,
        hash_politica=hash_politica,
    )

    assinatura_cache = str(
        cache.get("assinatura") or ""
    ).strip()

    if not hmac.compare_digest(
        assinatura_cache,
        assinatura_esperada,
    ):
        return False

    if permitir_offline:
        try:
            validado_em = datetime.fromisoformat(
                str(cache.get("validado_em"))
            ).date()

            dias_offline = (_hoje() - validado_em).days

            limite = int(
                getattr(config, "LICENCA_TOLERANCIA_OFFLINE_DIAS", 3)
            )

            if dias_offline > limite:
                return False

        except Exception:
            return False

    return True


def salvar_cache_licenca(
    politica: Dict[str, Any],
    machine_id: str,
) -> None:
    _garantir_pasta_cache()

    perfil = str(config.APP_PROFILE or "").upper()
    mes_referencia = str(politica.get("mes_referencia") or "").strip()
    valido_ate = str(politica.get("valido_ate") or "").strip()
    hash_politica = _hash_politica(politica)

    cache = {
        "app": getattr(config, "APP_TITLE_BASE", "RPA Search Data"),
        "perfil": perfil,
        "machine_id": machine_id,
        "mes_referencia": mes_referencia,
        "valido_ate": valido_ate,
        "hash_politica": hash_politica,
        "validado_em": _agora_iso(),
        "assinatura": _assinatura_cache(
            machine_id=machine_id,
            perfil=perfil,
            mes_referencia=mes_referencia,
            valido_ate=valido_ate,
            hash_politica=hash_politica,
        ),
    }

    _salvar_json_local(
        config.LICENCA_CACHE_PATH,
        cache,
    )


# ==========================================================
# REGISTRO OPCIONAL DA MÁQUINA
# ==========================================================
def registrar_maquina_se_configurado(
    politica: Dict[str, Any],
    identidade: Dict[str, str],
) -> None:
    """
    Registro opcional via Google Apps Script.

    Evita repetir envio:
    - não envia se URL_REGISTRO_MAQUINA estiver vazia;
    - não envia se já registrou a mesma máquina/perfil/mês.
    """

    url = getattr(config, "URL_REGISTRO_MAQUINA", "") or ""

    if not url:
        return

    mes_referencia = str(
        politica.get("mes_referencia") or ""
    ).strip()

    machine_id = identidade.get("machine_id", "")
    perfil = str(config.APP_PROFILE or "").upper()

    cache_registro = _ler_json_local(
        config.LICENCA_REGISTRO_CACHE_PATH
    )

    chave_atual = f"{machine_id}|{perfil}|{mes_referencia}|{url}"

    if cache_registro.get("ultima_chave") == chave_atual:
        return

    payload = {
        "secret": getattr(config, "REGISTRO_MAQUINA_SECRET", ""),
        "app": getattr(config, "APP_TITLE_BASE", "RPA Search Data"),
        "perfil": perfil,
        "versao": getattr(config, "current_version", ""),
        "mes_referencia": mes_referencia,
        "machine_id": machine_id,
        "hostname": identidade.get("hostname", ""),
        "usuario": identidade.get("usuario", ""),
        "sistema": identidade.get("sistema", ""),
        "release": identidade.get("release", ""),
        "machine": identidade.get("machine", ""),
        "registrado_em": _agora_iso(),
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=6,
        )

        if response.status_code in (200, 201, 204):
            _salvar_json_local(
                config.LICENCA_REGISTRO_CACHE_PATH,
                {
                    "ultima_chave": chave_atual,
                    "machine_id": machine_id,
                    "perfil": perfil,
                    "mes_referencia": mes_referencia,
                    "registrado_em": _agora_iso(),
                },
            )

    except Exception:
        # Registro de máquina não deve impedir a abertura do app.
        pass


# ==========================================================
# FUNÇÕES PÚBLICAS
# ==========================================================
def verificar_acesso_aplicacao() -> LicencaResultado:
    identidade = obter_identidade_maquina()
    machine_id = identidade["machine_id"]

    cache = _ler_json_local(
        config.LICENCA_CACHE_PATH
    )

    try:
        politica = baixar_politica_licenca()

    except Exception as ex:
        if _cache_local_valido(
            cache=cache,
            machine_id=machine_id,
            politica=None,
            permitir_offline=True,
        ):
            return LicencaResultado(
                liberado=True,
                requer_senha=False,
                titulo="Licença local válida",
                mensagem=(
                    "Não foi possível consultar a licença online, "
                    "mas o cache local ainda está dentro da tolerância offline."
                ),
                origem="cache_offline",
                politica={},
                machine_id=machine_id,
                mes_referencia=str(cache.get("mes_referencia") or ""),
                valido_ate=str(cache.get("valido_ate") or ""),
            )

        return LicencaResultado(
            liberado=False,
            requer_senha=False,
            titulo="Falha ao consultar licença",
            mensagem=(
                "Não foi possível consultar a licença online e não há cache local válido.\n\n"
                f"Detalhe: {ex}"
            ),
            origem="erro_online",
            politica={},
            machine_id=machine_id,
        )

    regras = _validar_regras_politica(
        politica=politica,
        machine_id=machine_id,
    )

    if not regras.liberado:
        return regras

    if _cache_local_valido(
        cache=cache,
        machine_id=machine_id,
        politica=politica,
        permitir_offline=False,
    ):
        return LicencaResultado(
            liberado=True,
            requer_senha=False,
            titulo="Licença válida",
            mensagem="Licença local validada com a política online atual.",
            origem="cache_online",
            politica=politica,
            machine_id=machine_id,
            mes_referencia=regras.mes_referencia,
            valido_ate=regras.valido_ate,
        )

    return LicencaResultado(
        liberado=False,
        requer_senha=True,
        titulo="Renovação necessária",
        mensagem=(
            f"Informe a senha de renovação mensal para {regras.mes_referencia}.\n"
            f"Validade da licença: {regras.valido_ate}."
        ),
        origem="senha_necessaria",
        politica=politica,
        machine_id=machine_id,
        mes_referencia=regras.mes_referencia,
        valido_ate=regras.valido_ate,
    )


def validar_senha_renovacao(
    senha: str,
    politica: Optional[Dict[str, Any]] = None,
) -> LicencaResultado:
    identidade = obter_identidade_maquina()
    machine_id = identidade["machine_id"]

    if politica is None:
        try:
            politica = baixar_politica_licenca()
        except Exception as ex:
            return LicencaResultado(
                liberado=False,
                requer_senha=True,
                titulo="Falha ao consultar licença",
                mensagem=f"Não foi possível consultar o JSON de licença: {ex}",
                origem="erro_online",
                politica={},
                machine_id=machine_id,
            )

    regras = _validar_regras_politica(
        politica=politica,
        machine_id=machine_id,
    )

    if not regras.liberado:
        return regras

    hash_esperado = _obter_hash_esperado(politica)

    hash_informado = gerar_hash_senha_mensal(
        senha=senha,
        mes_referencia=regras.mes_referencia,
        perfil=config.APP_PROFILE,
    )

    if not hmac.compare_digest(
        str(hash_informado).lower(),
        str(hash_esperado).lower(),
    ):
        return LicencaResultado(
            liberado=False,
            requer_senha=True,
            titulo="Senha inválida",
            mensagem="A senha informada não corresponde à renovação mensal atual.",
            origem="senha_invalida",
            politica=politica,
            machine_id=machine_id,
            mes_referencia=regras.mes_referencia,
            valido_ate=regras.valido_ate,
        )

    salvar_cache_licenca(
        politica=politica,
        machine_id=machine_id,
    )

    registrar_maquina_se_configurado(
        politica=politica,
        identidade=identidade,
    )

    return LicencaResultado(
        liberado=True,
        requer_senha=False,
        titulo="Licença renovada",
        mensagem="Licença renovada com sucesso.",
        origem="senha_validada",
        politica=politica,
        machine_id=machine_id,
        mes_referencia=regras.mes_referencia,
        valido_ate=regras.valido_ate,
    )