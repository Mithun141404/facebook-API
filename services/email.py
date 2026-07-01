import logging
import smtplib
from email.message import EmailMessage
from config import settings

_logger = logging.getLogger(__name__)

def alert_admin_error(error_message: str):
    """
    Sends an email alert to the authority/admin about a critical internal error.
    """
    if not settings.smtp_server or not settings.admin_email:
        _logger.warning("SMTP not configured. Skipping email alert for error: %s", error_message)
        return

    try:
        msg = EmailMessage()
        msg.set_content(f"The Facebook CRM API encountered an internal error:\n\n{error_message}")
        msg["Subject"] = "CRITICAL: Facebook CRM API Error"
        msg["From"] = settings.smtp_username or "api@example.com"
        msg["To"] = settings.admin_email

        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        
        _logger.info("Admin email alert sent successfully.")
    except Exception as e:
        _logger.error("Failed to send admin email alert: %s", e)
