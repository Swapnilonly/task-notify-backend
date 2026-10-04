# tasks/permissions.py
from users.permissions import user_has_permission

def can_manage_watchers(user, task):
    if not user_has_permission(user, 'task:watcher:manage'):   # colon, docstring convention ke hisaab se
        return False
    return task.assignee_id == user.id or task.created_by_id == user.id


def can_view_notification(user, notification):
    return notification.user_id == user.id   # role se independent, sirf ownership