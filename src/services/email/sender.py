from __future__ import annotations

import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional, Sequence, Tuple

import aiosmtplib

from src.services.email.settings import get_setting

logger = logging.getLogger(__name__)

EmailAttachment = Tuple[str, bytes, str]


class EmailSendError(Exception):
    pass


class EmailSender:
    def __init__(self, settings: Dict[str, str]):
        self._settings = settings

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        attachments: Optional[Sequence[EmailAttachment]] = None,
    ) -> None:
        if not to or "@" not in to:
            raise EmailSendError("Destinatario email non valido")

        host = get_setting(self._settings, "smtp_server")
        sender_email = get_setting(self._settings, "sender_email")
        if not host or not sender_email:
            raise EmailSendError("SMTP non configurato (smtp_server / sender_email)")

        sender_name = get_setting(self._settings, "sender_name") or sender_email
        password = get_setting(self._settings, "password") or ""
        ccn = get_setting(self._settings, "ccn")
        port = int(get_setting(self._settings, "smtp_port") or "587")
        security = (get_setting(self._settings, "security") or "tls").lower()

        message = MIMEMultipart("mixed")
        message["Subject"] = subject
        message["From"] = f"{sender_name} <{sender_email}>"
        message["To"] = to
        bcc: List[str] = []
        if ccn:
            message["Bcc"] = ccn
            bcc = [addr.strip() for addr in ccn.split(",") if addr.strip()]

        alternative = MIMEMultipart("alternative")
        if body_text:
            alternative.attach(MIMEText(body_text, "plain", "utf-8"))
        alternative.attach(MIMEText(body_html or "", "html", "utf-8"))
        message.attach(alternative)

        for filename, content, mime in attachments or []:
            part = MIMEApplication(content, _subtype=mime.split("/")[-1] if "/" in mime else "octet-stream")
            part.add_header("Content-Disposition", "attachment", filename=filename)
            message.attach(part)

        use_tls = security in {"ssl", "smtps"}
        start_tls = security in {"tls", "starttls", ""}
        recipients = [to, *bcc]

        try:
            await aiosmtplib.send(
                message,
                hostname=host,
                port=port,
                username=sender_email if password else None,
                password=password or None,
                use_tls=use_tls,
                start_tls=start_tls and not use_tls,
                sender=sender_email,
                recipients=recipients,
            )
        except Exception as exc:
            logger.error("Invio SMTP fallito: %s", exc, exc_info=True)
            raise EmailSendError(str(exc)) from exc
