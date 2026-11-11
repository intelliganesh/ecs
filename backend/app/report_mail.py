from email.headerregistry import Address
from email.message import EmailMessage
import logging
import smtplib
import ssl

from app.core.config import Settings
from app.retirement_results import ReportFile


logger = logging.getLogger(__name__)


def open_smtp(settings: Settings) -> smtplib.SMTP:
    context = ssl.create_default_context()
    if settings.mail_encryption == "ssl":
        return smtplib.SMTP_SSL(settings.mail_host, settings.mail_port, timeout=10, context=context)

    client = smtplib.SMTP(settings.mail_host, settings.mail_port, timeout=10)
    try:
        client.starttls(context=context)
    except Exception:
        client.close()
        raise
    return client


def login_smtp(client: smtplib.SMTP, settings: Settings) -> None:
    password = settings.mail_password.get_secret_value()
    if settings.mail_host.casefold() == "smtp.gmail.com":
        password = password.replace(" ", "")
    client.login(settings.mail_username, password)


def send_report_email(settings: Settings, attachments: dict[str, list[ReportFile]], job_id: int) -> None:
    if not settings.mail_enabled or not attachments:
        return

    try:
        sender = Address(display_name=settings.mail_from_name, addr_spec=settings.mail_from_address)
        with open_smtp(settings) as client:
            login_smtp(client, settings)
            for recipient, reports in attachments.items():
                message = EmailMessage()
                message["From"] = sender
                message["To"] = recipient
                message["Subject"] = "Your Retirement Builder report is ready"
                report_label = "report is" if len(reports) == 1 else "reports are"
                message.set_content(f"Hello,\n\nYour Retirement Builder {report_label} attached.\n\nThank you.\n")
                for report in reports:
                    message.add_attachment(
                        report.csv.encode("utf-8"), maintype="text", subtype="csv",
                        params={"charset": "utf-8"}, filename=report.file_name,
                    )
                try:
                    client.send_message(message)
                except (smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError) as exc:
                    logger.warning("SMTP rejected a message for retirement job %s (%s).", job_id, type(exc).__name__)
    except (OSError, ValueError) as exc:
        logger.warning("Mail delivery for retirement job %s failed (%s).", job_id, type(exc).__name__)
