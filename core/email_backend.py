from email.utils import formataddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from django.utils.module_loading import import_string

from .models import EmailServerSettings


class DatabaseConfiguredEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        email_settings = EmailServerSettings.objects.filter(
            pk=1,
            is_enabled=True,
        ).first()

        if email_settings is None:
            backend_class = import_string(settings.EMAIL_ENV_BACKEND)
            self.backend = backend_class(
                fail_silently=fail_silently,
                **kwargs,
            )
            self.from_email = None
        else:
            smtp_options = {
                **kwargs,
                "host": email_settings.host,
                "port": email_settings.port,
                "username": email_settings.username,
                "password": email_settings.get_password(),
                "use_tls": email_settings.use_tls,
                "use_ssl": email_settings.use_ssl,
                "timeout": settings.EMAIL_TIMEOUT,
                "ssl_keyfile": settings.EMAIL_SSL_KEYFILE,
                "ssl_certfile": settings.EMAIL_SSL_CERTFILE,
                "fail_silently": fail_silently,
            }
            self.backend = SMTPEmailBackend(**smtp_options)
            self.from_email = email_settings.from_email or settings.EMAIL_FROM_ADDRESS
            self.from_name = email_settings.from_name

    def open(self):
        return self.backend.open()

    def close(self):
        return self.backend.close()

    def send_messages(self, email_messages):
        if self.from_email:
            sender = (
                formataddr((self.from_name, self.from_email), charset="utf-8")
                if self.from_name
                else self.from_email
            )
            for message in email_messages:
                message.from_email = sender
        return self.backend.send_messages(email_messages)
