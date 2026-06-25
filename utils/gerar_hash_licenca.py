# ==========================================================
# TOOL - GERADOR DE HASH DA SENHA DA LICENÇA
# ==========================================================
import argparse
import hashlib
import os


DEFAULT_SALT = os.getenv(
    "RPA_LICENSE_SALT",
    "Contrato247/2024RpaSearchData"
)


def gerar_hash(
    senha: str,
    perfil: str,
    salt: str,
) -> str:
    texto = "|".join(
        [
            salt,
            perfil.upper().strip(),
            senha.strip(),
        ]
    )

    return hashlib.sha256(
        texto.encode("utf-8")
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description="Gerador de hash SHA-256 para senha bimestral da aplicação."
    )

    parser.add_argument(
        "--senha",
        required=True,
        help="Senha que será compartilhada com os usuários."
    )

    parser.add_argument(
        "--perfil",
        required=True,
        choices=["USUARIO", "ADMIN"],
        help="Perfil da aplicação."
    )

    parser.add_argument(
        "--salt",
        default=DEFAULT_SALT,
        help="Mesmo salt usado no config.py."
    )

    args = parser.parse_args()

    hash_gerado = gerar_hash(
        senha=args.senha,
        perfil=args.perfil,
        salt=args.salt,
    )

    print("\nHASH GERADO:")
    print(hash_gerado)
    print("\nCole esse valor no campo senha_hash_sha256 do JSON.")


if __name__ == "__main__":
    main()