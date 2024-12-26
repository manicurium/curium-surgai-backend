from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings

import smtplib

import logging

from .s3Utils import S3Utils


logger = logging.getLogger(__name__)


from typing import List, Tuple

# Default configuration
DEFAULT_EMAILS = ["reports@curium.life"]
DEFAULT_APP_LINK = "http://hiacuriumendpoint.curium.life:7051/"


def load_institution_config():
    s3_client = S3Utils(
        access_key=settings.AWS_ACCESS_KEY_ID,
        secret_key=settings.AWS_SECRET_ACCESS_KEY,
        bucket_name=settings.CONFIG_BUCKET_NAME,
        region=settings.AWS_REGION,
    )
    mappings_dict = s3_client.get_s3_object(
        file_location="hernia/notification_config.json"
    )
    return mappings_dict


def get_institution_details(institution: str) -> Tuple[List[str], str]:
    """Get radiologist emails and app link for a given institution"""
    config = load_institution_config()

    for inst_config in config:
        if institution in inst_config.get("institutionNames", []):
            return (
                inst_config.get("radiologist", []),
                inst_config.get("appLink", DEFAULT_APP_LINK),
            )

    logger.warning(
        f"No matching institution found for {institution}, using default configuration"
    )
    return DEFAULT_EMAILS, DEFAULT_APP_LINK


def send_email(subject: str, body: str, message: MIMEMultipart, users: List[str]):
    """Send email to specified users"""
    smtp_server = settings.SMTP_SERVER_NAME
    smtp_port = int(settings.SMTP_PORT)  # Port for TLS
    sender_email = settings.SMTP_USERNAME
    sender_password = settings.SMTP_PASSWORD

    message["From"] = sender_email
    message["To"] = ", ".join(users)
    message["Subject"] = subject

    message.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(
                from_addr=sender_email,
                to_addrs=users,
                msg=message.as_string(),
            )
        logger.info(f"Successfully sent email to {users}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


def send_new_volume_upload_notification(institution: str):
    """Send notification for new volume upload"""
    logger.info(
        f"Sending new volume upload notification to radiologist of institution {institution}"
    )

    # Get recipient emails and app link based on institution

    recipient_emails, base_app_link = get_institution_details(institution.lower())

    # Construct the full volume URL
    volume_url = f"{base_app_link}listing"

    message = MIMEMultipart()

    body = f"""
    <p>You have a new Volume uploaded</p>
    <p>Click <a href="{volume_url}">here</a> to view the volume, or copy and paste the following link:</p>
    <p>{volume_url}</p>
    """

    subject = "New Volume upload"
    send_email(subject, body, message, recipient_emails)
