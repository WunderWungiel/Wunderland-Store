import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from . import config

smtp_address = config['email']['smtp']['address']
smtp_port = config['email']['smtp']['port']
email_address = config['email']['address']
email_password = config['email']['password']


def send_email(subject, text_message, html_message, receiver_email):

    context = ssl.create_default_context()

    server = smtplib.SMTP_SSL(smtp_address, smtp_port, context=context)
    server.login(email_address, email_password)

    message = MIMEMultipart("alternative")
    message['Subject'] = subject
    message['From'] = email_address
    message['To'] = receiver_email

    part1 = MIMEText(text_message, "plain")
    part2 = MIMEText(html_message, "html")

    message.attach(part1)
    message.attach(part2)

    server.sendmail(
        email_address, receiver_email, message.as_string()
    )

    server.close()
