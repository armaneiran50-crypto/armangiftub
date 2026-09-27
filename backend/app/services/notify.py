"""Outbound notifications behind a small adapter (masterplan §9: every integration behind an adapter).

Email is sent over SMTP when configured; otherwise the message is only logged. Delivery runs in a
FastAPI background task so a slow mail server never blocks an API response.
"""
import logging
import smtplib
from email.message import EmailMessage

from ..config import get_settings

log = logging.getLogger("logirad.notify")
outbox: list[dict] = []  # last messages, for tests and debugging


def send_email(to: str | None, subject: str, body: str) -> None:
    if not to:
        return
    msg = {"to": to, "subject": subject, "body": body}
    outbox.append(msg)
    del outbox[:-100]
    s = get_settings()
    if not s.smtp_host:
        log.info("email (not sent, SMTP not configured) to=%s subject=%s", to, subject)
        return
    em = EmailMessage()
    em["From"], em["To"], em["Subject"] = s.smtp_from, to, subject
    em.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(em)
    except (smtplib.SMTPException, OSError):
        log.exception("email delivery failed to=%s subject=%s", to, subject)


def rfq_dispatched(to: str | None, reference: str, lane: str, mode: str | None) -> tuple:
    url = get_settings().public_url.rstrip("/")
    return (send_email, to, f"New freight RFQ {reference} ({lane})",
            f"A new RFQ matching your lanes is waiting for your quote.\n\n"
            f"Reference: {reference}\nLane: {lane}\nMode: {mode or '-'}\n\n"
            f"Submit or decline it in the provider portal: {url}/portal\n")


def quote_won(to: str | None, reference: str) -> tuple:
    url = get_settings().public_url.rstrip("/")
    return (send_email, to, f"Your quote for {reference} was accepted",
            f"The customer booked your quote for RFQ {reference}.\n"
            f"Our operations desk will contact you with the booking details.\n\n{url}/portal\n")


def rfq_received(to: str | None, reference: str) -> tuple:
    url = get_settings().public_url.rstrip("/")
    return (send_email, to, f"درخواست {reference} ثبت شد / RFQ {reference} received",
            f"درخواست حمل شما با کد {reference} ثبت شد. وضعیت: {url}/#track\n\n"
            f"Your freight request {reference} has been received. Track it at {url}/#track\n")
