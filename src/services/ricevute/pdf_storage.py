"""Persistenza file PDF ricevute."""
import hashlib
import os
from datetime import datetime

from src.models.ricevuta import Ricevuta


def ricevuta_pdf_relative_path(ricevuta: Ricevuta) -> str:
    return (
        f"media/ricevute/{ricevuta.anno}/"
        f"Ricevuta-{ricevuta.numero}-{ricevuta.anno}.pdf"
    )


def save_ricevuta_pdf(ricevuta: Ricevuta, pdf_bytes: bytes) -> tuple[str, str]:
    relative_path = ricevuta_pdf_relative_path(ricevuta)
    absolute_path = relative_path.replace("/", os.sep)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "wb") as handle:
        handle.write(pdf_bytes)
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    return relative_path, pdf_hash


def update_ricevuta_pdf_metadata(ricevuta: Ricevuta, pdf_bytes: bytes) -> None:
    relative_path, pdf_hash = save_ricevuta_pdf(ricevuta, pdf_bytes)
    ricevuta.pdf_path = relative_path
    ricevuta.pdf_hash = pdf_hash
    ricevuta.pdf_generated_at = datetime.utcnow()


def read_ricevuta_pdf_bytes(ricevuta: Ricevuta) -> bytes:
    if not ricevuta.pdf_path:
        raise FileNotFoundError("PDF non generato")
    path = ricevuta.pdf_path.replace("/", os.sep)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File PDF non trovato: {ricevuta.pdf_path}")
    with open(path, "rb") as handle:
        return handle.read()
