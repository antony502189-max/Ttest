import ssl
from types import SimpleNamespace

from app.services import mail


def test_smtp_uses_configured_sender_display_name(monkeypatch):
    sent: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, *args, **kwargs) -> None:
            sent["connection"] = args

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def starttls(self, *, context=None) -> None:
            sent["starttls"] = True
            sent["tls_context"] = context

        def login(self, username: str, password: str) -> None:
            sent["login"] = (username, password)

        def send_message(self, message) -> None:
            sent["message"] = message

    monkeypatch.setattr(mail.smtplib, "SMTP", FakeSMTP)
    item = SimpleNamespace(recipient="recipient@example.test", subject="Subject", body="Body")
    settings = SimpleNamespace(
        smtp_host="smtp.example.test",
        smtp_port=587,
        smtp_starttls=True,
        smtp_username="sender@example.test",
        smtp_password="password",
        smtp_from="sender@example.test",
        smtp_from_name="112233.es",
    )

    mail.send_smtp(item, settings)

    from_header = sent["message"]["From"]
    assert from_header.addresses[0].display_name == "112233.es"
    assert from_header.addresses[0].addr_spec == "sender@example.test"
    assert sent["starttls"] is True
    assert isinstance(sent["tls_context"], ssl.SSLContext)
    assert sent["tls_context"].verify_mode == ssl.CERT_REQUIRED
    assert sent["tls_context"].check_hostname is True
