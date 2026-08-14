"""
users/management/commands/seed_roles.py

Run once per environment:
    python manage.py seed_roles

Safe to re-run — uses get_or_create (idempotent).
"""

from django.core.management.base import BaseCommand
from users.models import Role, Permission

ROLES_PERMISSIONS = {
    "admin": [
        "task:create", "task:read", "task:update", "task:delete", "task:assign",
        "user:manage", "user:read",
        "report:view", "report:export",
        "notification:manage",
        "audit:view",
    ],
    "manager": [
        "task:create", "task:read", "task:update", "task:assign",
        "user:read",
        "report:view",
        "notification:manage",
    ],
    "member": [
        "task:create", "task:read", "task:update",
        "notification:read",
        "report:view",
    ],
    "viewer": [
        "task:read",
        "notification:read",
        "report:view",
    ],
}


class Command(BaseCommand):
    help = "Seed default roles and permissions into the database."

    def handle(self, *args, **kwargs):
        self.stdout.write("\n── Seeding Roles & Permissions ──\n")

        for role_name, codenames in ROLES_PERMISSIONS.items():
            role, role_created = Role.objects.get_or_create(name=role_name)
            tag = "created" if role_created else "exists "

            for codename in codenames:
                perm, _ = Permission.objects.get_or_create(codename=codename)
                role.permissions.add(perm)

            self.stdout.write(
                self.style.SUCCESS(f"  [{tag}] Role: {role_name:<10} | {len(codenames)} permissions")
            )

        self.stdout.write(self.style.SUCCESS("\n✔ seed_roles completed.\n"))