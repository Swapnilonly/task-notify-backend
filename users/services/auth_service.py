import logging
from users.models import Role, UserRole, User
from django.db import transaction
from users.permissions import invalidate_user_permission_cache
from users.core import send_welcome_notification
from users.constant import DEFAULT_ROLE
logger = logging.getLogger("app")

@transaction.atomic
def register_user(email: str, name: str, password: str) -> tuple[User, Role]:
    """Create a user with the default role.

    Raises Role.DoesNotExist if roles have not been seeded.
    """
    # Looked up first so a misconfigured system fails before any user is created.
    default_role = Role.objects.get(name=DEFAULT_ROLE)
    user = User.objects.create_user(email=email, name=name, password=password)
    UserRole.objects.create(user=user, role=default_role, assigned_by=None)
    invalidate_user_permission_cache(user.id)
    transaction.on_commit(
        lambda: send_welcome_notification(user.id), robust=True
    )
    logger.info("New user registered: id=%s role=%s", user.id, default_role.name)
    return user, default_role