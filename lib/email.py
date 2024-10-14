import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .config import config

smtp_port = config["SMTP_PORT"]
email_address = config["EMAIL_ADDRESS"]
smtp_address = config["SMTP_ADDRESS"]
email_password = config["EMAIL_PASSWORD"]


def send_email(text_message, html_message, receiver_email):

    context = ssl.create_default_context()

    server = smtplib.SMTP_SSL(smtp_address, smtp_port, context=context)
    server.login(email_address, email_password)

    message = MIMEMultipart("alternative")
    message["Subject"] = "Confirm your account"
    message["From"] = email_address
    message["To"] = receiver_email

    part1 = MIMEText(text_message, "plain")
    part2 = MIMEText(html_message, "html")

    message.attach(part1)
    message.attach(part2)

    server.sendmail(
        email_address, receiver_email, message.as_string()
    )

    server.close()
