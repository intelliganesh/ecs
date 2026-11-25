from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage
import logging
import re
import smtplib
import ssl
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.retirement_results import ReportFile, merge_report_files, report_mime_subtype

if TYPE_CHECKING:
    from app.routers.retirement_builder import RetirementBuilderJob, SubscriptionsForm


logger = logging.getLogger(__name__)
EMAIL_PATTERN = re.compile(
    r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*",
    re.IGNORECASE | re.ASCII,
)


@dataclass(frozen=True)
class ReportEmailDelivery:
    enabled: bool
    matched: int = 0
    accepted: int = 0


def _client_id(value: str) -> str | None:
    value = value.strip()
    if value.isascii() and value.isdecimal():
        return value.lstrip("0") or "0"
    return None


def _subscription_attachments(subscriptions: "SubscriptionsForm", reports: list[ReportFile]) -> dict[str, list[ReportFile]]:
    clients_by_recipient: dict[str, set[tuple[str, str]]] = {}
    for subscription in subscriptions.rows:
        if subscription.companyId is not None:
            target = ("company", str(subscription.companyId))
        else:
            client = _client_id(subscription.client)
            if client is None:
                continue
            target = ("client", client)
        for address in re.split(r"[,;\n]", subscription.email):
            address = address.strip().lower()
            if EMAIL_PATTERN.fullmatch(address):
                clients_by_recipient.setdefault(address, set()).add(target)

    report_clients = []
    for report in reports:
        if report.payroll_company_ids:
            report_clients.append((report, {("company", company) for company in report.payroll_company_ids}))
        elif report.client_ids:
            report_clients.append((report, {("client", _client_id(client)) for client in report.client_ids}))
    attachments = {}
    for address, clients in clients_by_recipient.items():
        eligible = [report for report, required in report_clients if required <= clients]
        if eligible:
            attachments[address] = eligible
    return attachments


def send_subscribed_reports(
    settings: Settings, job: "RetirementBuilderJob", reports: list[ReportFile],
    *, builder_name: str = "Retirement Builder",
) -> ReportEmailDelivery:
    if not settings.mail_enabled or not reports or not job.subscriptions.rows:
        return ReportEmailDelivery(enabled=settings.mail_enabled)
    attachments = _subscription_attachments(job.subscriptions, reports)
    if not attachments:
        logger.warning("No generated files matched the subscriptions for %s job %s.", builder_name, job.id)
        return ReportEmailDelivery(enabled=True)
    if job.subscriptions.mergeFiles:
        attachments = {
            recipient: [merge_report_files(job, files)] if len(files) > 1 else files
            for recipient, files in attachments.items()
        }
    accepted = send_report_email(settings, attachments, job.id, builder_name=builder_name)
    return ReportEmailDelivery(enabled=True, matched=len(attachments), accepted=accepted)


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


def send_report_email(
    settings: Settings, attachments: dict[str, list[ReportFile]], job_id: int,
    *, builder_name: str = "Retirement Builder",
) -> int:
    if not settings.mail_enabled or not attachments:
        return 0

    accepted = 0
    try:
        sender = Address(display_name=settings.mail_from_name, addr_spec=settings.mail_from_address)
        with open_smtp(settings) as client:
            login_smtp(client, settings)
            for recipient, reports in attachments.items():
                message = EmailMessage()
                message["From"] = sender
                message["To"] = recipient
                message["Subject"] = f"Your {builder_name} report is ready"
                report_label = "report is" if len(reports) == 1 else "reports are"
                message.set_content(f"Hello,\n\nYour {builder_name} {report_label} attached.\n\nThank you.\n")
                for report in reports:
                    message.add_attachment(
                        report.csv.encode("utf-8"), maintype="text", subtype="plain" if report.excel_rows is not None else report_mime_subtype(report.file_name),
                        params={"charset": "utf-8"}, filename=report.file_name,
                    )
                try:
                    client.send_message(message)
                except (smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError) as exc:
                    logger.exception(
                        "SMTP rejected a message for %s job %s.", builder_name, job_id,
                        extra={"job_id": job_id, **_smtp_error_details(exc)},
                    )
                else:
                    accepted += 1
    except (OSError, ValueError) as exc:
        logger.exception(
            "Mail delivery for %s job %s failed.", builder_name, job_id,
            extra={"job_id": job_id, **_smtp_error_details(exc)},
        )
    return accepted


def _smtp_error_details(error: Exception) -> dict:
    details = {}
    if isinstance(error, smtplib.SMTPResponseException):
        details["smtp_code"] = error.smtp_code
        response = error.smtp_error
        details["smtp_response"] = response.decode("utf-8", errors="replace") if isinstance(response, bytes) else str(response)
    return details
