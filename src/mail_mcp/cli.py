from __future__ import annotations

import argparse
import getpass
import sys

import keyring
import keyring.errors

from .config import KEYRING_SERVICE, config_path, load_accounts


def set_secret(name: str) -> int:
    """Range le mot de passe d'un compte dans le trousseau du système, saisi sans écho."""
    try:
        accounts = load_accounts()
    except FileNotFoundError:
        print(f"Config introuvable ({config_path()}) : secret enregistré sans vérifier le nom.", file=sys.stderr)
    else:
        if name not in accounts:
            print(f"Compte inconnu '{name}'. Comptes : {sorted(accounts)}", file=sys.stderr)
            return 2
    secret = getpass.getpass(f"Mot de passe pour '{name}' : ")
    if not secret:
        print("Mot de passe vide : rien n'a été enregistré.", file=sys.stderr)
        return 2
    if getpass.getpass("Confirmer : ") != secret:
        print("Les deux saisies diffèrent : rien n'a été enregistré.", file=sys.stderr)
        return 2
    try:
        keyring.set_password(KEYRING_SERVICE, name, secret)
    except keyring.errors.KeyringError as e:
        print(f"Trousseau indisponible : {e}", file=sys.stderr)
        return 1
    print(f"Secret enregistré pour '{name}' (service '{KEYRING_SERVICE}').")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mail-mcp", description="Serveur MCP mail multi-comptes")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="lance le serveur MCP sur stdio (par défaut)")
    p = sub.add_parser("set-secret", help="enregistre le mot de passe d'un compte dans le trousseau")
    p.add_argument("account")
    args = parser.parse_args(argv)
    if args.command == "set-secret":
        return set_secret(args.account)
    from .server import create_server

    create_server(load_accounts()).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
