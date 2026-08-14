import logging


logger = logging.getLogger("app")

def send_welcome_notification(user_id):
    try:
        from notifications.tasks import send_welcome_notification
        send_welcome_notification.delay(str(user_id))
    except Exception as e:
        logger.error(f"welcome notification failed {e}", exc_info=True)