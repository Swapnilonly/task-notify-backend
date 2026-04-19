from django.db import models

# Create your models here.


# class AuthUser(models.Model):
#     id = models.BigAutoField(primary_key=True)
#     password = models.CharField(max_length=128)
#     last_login = models.DateTimeField(null=True)
#     is_superuser = models.BooleanField()
#     username = models.CharField(max_length=150)
#     first_name = models.CharField(max_length=150)
#     last_name = models.CharField(max_length=150)
#     email = models.CharField(max_length=254)
#     is_staff = models.BooleanField()
#     is_active = models.BooleanField()
#     date_joined = models.DateTimeField()
#
#     class Meta:
#         managed = False
#         db_table = 'auth_user'
#
#
# class AuthGroup(models.Model):
#     id = models.BigAutoField(primary_key=True)
#     name = models.CharField(max_length=150)
#
#     class Meta:
#         managed = False
#         db_table = 'auth_group'
#
#
# class AuthPermission(models.Model):
#     id = models.BigAutoField(primary_key=True)
#     name = models.CharField(max_length=255)
#     content_type_id = models.BigIntegerField()
#     codename = models.CharField(max_length=100)
#
#     class Meta:
#         managed = False
#         db_table = 'auth_permission'
#
#
# class AuthUserGroup(models.Model):
#     id = models.BigAutoField(primary_key=True)
#     user_id = models.BigIntegerField()
#     group_id = models.BigIntegerField()
#
#     class Meta:
#         managed = False
#         db_table = 'auth_user_groups'
#
#
# class AuthUserPermission(models.Model):
#     id = models.BigAutoField(primary_key=True)
#     user_id = models.BigIntegerField()
#     permission_id = models.BigIntegerField()
#
#     class Meta:
#         managed = False
#         db_table = 'auth_user_user_permissions'
#
# class DjangoContentType(models.Model):
#     id = models.BigAutoField(primary_key=True)
#     app_label = models.CharField(max_length=100)
#     model = models.CharField(max_length=100)
#
#     class Meta:
#         managed = False
#         db_table = 'django_content_type'
#
#
# class DjangoAdminLog(models.Model):
#     id = models.BigAutoField(primary_key=True)
#     action_time = models.DateTimeField()
#     object_id = models.TextField(null=True)
#     object_repr = models.CharField(max_length=200)
#     action_flag = models.PositiveSmallIntegerField()
#     change_message = models.TextField()
#     content_type_id = models.BigIntegerField(null=True)
#     user_id = models.BigIntegerField()
#
#     class Meta:
#         managed = False
#         db_table = 'django_admin_log'
#
#
# class DjangoSession(models.Model):
#     session_key = models.CharField(primary_key=True, max_length=40)
#     session_data = models.TextField()
#     expire_date = models.DateTimeField()
#
#     class Meta:
#         managed = False
#         db_table = 'django_session'
#
#
#
# class DjangoMigration(models.Model):
#     id = models.BigAutoField(primary_key=True)
#     app = models.CharField(max_length=255)
#     name = models.CharField(max_length=255)
#     applied = models.DateTimeField()
#
#     class Meta:
#         managed = False
#         db_table = 'django_migrations'



class Task(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(max_length=20)
    status = models.CharField(max_length=30)
    created_by = models.BigIntegerField()
    created_at = models.DateTimeField()

    class Meta:
        managed = True
        db_table = 'tasks'



class Notification(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_id = models.BigIntegerField()
    task_id = models.BigIntegerField(null=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=50)
    is_sent = models.BooleanField()
    scheduled_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = True
        db_table = 'notifications'



class NotificationLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    notification_id = models.BigIntegerField()
    channel = models.CharField(max_length=30)
    status = models.CharField(max_length=30)
    response = models.TextField()
    sent_at = models.DateTimeField()

    class Meta:
        managed = True
        db_table = 'notification_logs'

