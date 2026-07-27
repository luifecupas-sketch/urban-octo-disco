"""Send the daily deal digest by email via SMTP.

Configured entirely through environment variables so no credentials ever
live in the repo:

  SMTP_HOST   - e.g. smtp.gmail.com
  SMTP_PORT   - e.g. 587
  SMTP_USER   - login/sender account
  SMTP_PASS   - app password / API key
  EMAIL_TO    - recipient address
  EMAIL_FROM  - optional, defaults to SMTP_USER
"""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText


class EmailConfigError(RuntimeError):
    pass


def send_digest(subject: str, body_markdown: str) -> None:
    host = os.environ.get("SMTP_HOST")
    port = os.environ.get("SMTP_PORT")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    to_addr = os.environ.get("EMAIL_TO")
    from_addr = os.environ.get("EMAIL_FROM", user)

    missing = [
        name
        for name, val in [
            ("SMTP_HOST", host),
            ("SMTP_PORT", port),
            ("SMTP_USER", user),
            ("SMTP_PASS", password),
            ("EMAIL_TO", to_addr),
        ]
        if not val
    ]
    if missing:
        raise EmailConfigError(
            f"missing required environment variable(s): {', '.join(missing)}"
        )

    message = MIMEText(body_markdown, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = from_addr
    message["To"] = to_addr

    with smtplib.SMTP(host, int(port)) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, [to_addr], message.as_string())
