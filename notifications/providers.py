# notifications/providers.py — NAYI FILE, yahan banao

import logging

logger = logging.getLogger("app")


def send_via_provider(notif, idempotency_key: str):
    """
    Placeholder provider wrapper.
    Abhi ke liye: sirf log karta hai, actual email/push nahi bhejta.
    Real provider (SendGrid/SES/FCM) integrate hote hi yahan replace karo.
    """
    logger.info(
        "notification_send_attempted",
        extra={
            "notification_id": notif.id,
            "channel": notif.channel,
            "idempotency_key": idempotency_key,
        },
    )
    # : yahan actual provider call aayega, jaise:
    # if notif.channel == 'EMAIL':
    #     send_mail(..., headers={'Idempotency-Key': idempotency_key})
    return True