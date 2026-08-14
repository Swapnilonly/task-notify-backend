"""
users/models.py — Custom User model with UUID pk + DB-based RBAC.
Old flat role=CharField is kept as legacy field (do not remove until
migration is stable). New Role/Permission/UserRole models added below.
"""

import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.db import models


# ─────────────────────────────────────────────
# Permission & Role Models
# ─────────────────────────────────────────────

class Permission(models.Model):
    """
    Granular permission unit.
    codename format → "resource:action"  e.g. "task:delete", "report:export"
    """
    codename    = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name        = "Permission"
        verbose_name_plural = "Permissions"
        ordering            = ["codename"]

    def __str__(self):
        return self.codename


class Role(models.Model):
    """
    Named role that groups permissions.
    e.g. admin, manager, member, viewer
    """
    name        = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles"
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Role"
        verbose_name_plural = "Roles"
        ordering            = ["name"]

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
# Custom User Manager
# ─────────────────────────────────────────────

class UserManager(BaseUserManager):

    def create_user(self, email, name, password=None, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user  = self.model(email=email, name=name, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    # users/models.py — inside UserManager

    def create_superuser(self, email, name, password, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        user = self.create_user(email, name, password, **extra)

        # Auto-assign admin role after creation
        try:
            from users.models import Role, UserRole
            admin_role, _ = Role.objects.get_or_create(name="admin")
            UserRole.objects.get_or_create(user=user, role=admin_role)
        except Exception as e:
            import logging
            logging.getLogger("app").warning(
                f"Could not assign admin role to superuser: {e}"
            )
            # Silently pass — role can be assigned manually via shell
            # This happens if seed_roles hasn't run yet

        return user


# ─────────────────────────────────────────────
# Custom User Model
# ─────────────────────────────────────────────

class User(AbstractBaseUser, PermissionsMixin):
    """
    NOTE: legacy `role` CharField is intentionally removed.
    Role is now fully managed via UserRole table.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name       = models.CharField(max_length=150)
    email      = models.EmailField(unique=True, db_index=True)
    is_active  = models.BooleanField(default=True)
    is_staff   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    class Meta:
        verbose_name        = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.name} <{self.email}>"

    # ── Convenience helpers ──────────────────

    def get_roles(self):
        """Return queryset of Role objects assigned to this user."""
        return Role.objects.filter(user_roles__user=self)

    def get_role_names(self):
        """Return list of role name strings."""
        return list(self.get_roles().values_list("name", flat=True))

    def has_role(self, role_name: str) -> bool:
        return self.get_roles().filter(name=role_name).exists()

    def has_role_id(self, role_id: int) -> bool:
        return UserRole.objects.filter(user=self, role__id=role_id).exists()

    @property
    def is_admin(self):
        return self.has_role("admin")


# ─────────────────────────────────────────────
# UserRole — Join table with audit fields
# ─────────────────────────────────────────────

class UserRole(models.Model):
    """
    Links a user to a role.
    assigned_by = None means system-assigned (e.g. on registration).
    """
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_roles"
    )
    role        = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="user_roles"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="roles_assigned"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together     = ("user", "role")
        verbose_name        = "User Role"
        verbose_name_plural = "User Roles"

    def __str__(self):
        return f"{self.user.email} → {self.role.name}"