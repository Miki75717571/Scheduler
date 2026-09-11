import logging

from app.core.config import settings

logger = logging.getLogger("app.email")


class EmailService:
    def send_invitation_email(self, *, to: str, accept_url: str) -> None:
        subject = "You're invited to the Cafeteria Scheduler"
        body = (
            f"Click the link to set up your account: {accept_url}\n\n"
            f"This link expires in {settings.invitation_token_expire_hours} hours."
        )
        if settings.email_provider == "resend" and settings.resend_api_key:
            self._send_via_resend(to=to, subject=subject, body=body)
        else:
            logger.info("EMAIL (console provider) to=%s subject=%s\n%s", to, subject, body)

    def _send_via_resend(self, *, to: str, subject: str, body: str) -> None:
        import resend

        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": settings.email_from,
                "to": [to],
                "subject": subject,
                "text": body,
            }
        )
