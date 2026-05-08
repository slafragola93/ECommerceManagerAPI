#!/usr/bin/env python3
"""
One-shot: ricalcola bcrypt per righe users la cui colonna password non è un hash bcrypt.

USO: eseguire DOPO il fix del POST /api/v1/users/ che salvava password in chiaro.

ATTENZIONE SICUREZZA:
  Le password erano memorizzate in plaintext nel DB: chi aveva accesso al dump
  le ha viste. Per utenti reali conviene forzare un reset password; questo
  script serve soprattutto a riabilitare il login su account di test senza
  doverli ricreare.

Esempi:
  python scripts/fix_plaintext_user_passwords.py          # applica
  python scripts/fix_plaintext_user_passwords.py --dry-run
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models.user import User
from src.services.routers.auth_service import bcrypt_context


def _looks_like_bcrypt(value: str | None) -> bool:
    if not value or not isinstance(value, str):
        return False
    return value.startswith("$2") and len(value) >= 50


def fix_plaintext_passwords(db: Session, dry_run: bool = False) -> int:
    users = db.query(User).all()
    n = 0
    for u in users:
        if _looks_like_bcrypt(u.password):
            continue
        n += 1
        print(f"  Fix id_user={u.id_user} username={u.username!r}")
        if not dry_run:
            u.password = bcrypt_context.hash(u.password)
    if not dry_run and n:
        db.commit()
    elif dry_run and n:
        db.rollback()
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Hash bcrypt per password non ancora hashate.")
    parser.add_argument("--dry-run", action="store_true", help="Solo elenco, nessuna scrittura.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        fixed = fix_plaintext_passwords(db, dry_run=args.dry_run)
        if args.dry_run:
            print(f"Dry-run: avrebbero aggiornati {fixed} utenti.")
        else:
            print(f"Utenti aggiornati: {fixed}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
