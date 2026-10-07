# TASK-NOTIFY-BACKEND

Django REST API for task management with role-based access control, event-driven in-app notifications, and audit logging. It is the backend foundation for a multi-tenant task-notification SaaS product (work in progress, see [Project Status](#project-status)).

---

## Tech Stack

| Layer        | Technology                                                  |
|--------------|-------------------------------------------------------------|
| Framework    | Django 4.2 + Django REST Framework                          |
| Auth         | JWT (SimpleJWT) with refresh-token blacklist                |
| Database     | MySQL (`mysqlclient`)                                       |
| Cache        | Redis 7 (`django-redis`), separate DB from the Celery broker |
| Background   | Celery 5 + Celery Beat (`django-celery-beat`, `django-celery-results`) |
| API tooling  | `django-filter`, `django-cors-headers`                      |
| Config       | `python-decouple` (environment variables / `.env`)          |
| Testing      | Django test runner (`manage.py test`); pytest dependencies are installed but not configured yet |
| Code quality | `black`, `flake8`                                           |

---

## Project Structure

```
task-notify-backend/
├── config/            # settings, root urls, celery app, wsgi/asgi
├── users/             # custom User, Role/Permission/UserRole (RBAC), auth views,
│                      # signals (default notification preferences), seed_roles command
├── tasks/             # Task + TaskWatcher models, core.py (business logic),
│                      # views, serializers, permission helpers, signals
├── notifications/     # Notification, TaskEvent, NotificationPreference,
│                      # NotificationDelivery; fan-out services; Celery tasks; tests/
├── logs/              # ActivityLog model, log_activity() helper, admin endpoint
├── services/          # dashboard summary + reporting
├── middleware/        # RequestLoggingMiddleware
├── utils/             # JSON log formatter, pagination, exception handler, health check
├── logs_dir/          # runtime log files (generated, must not be committed)
├── manage.py
└── requirement.txt
```

Views are kept thin. Business logic lives in `core.py` / `services.py` modules next to each app's views.

---

## Quick Start (Local)

**Prerequisites:** Python 3.10+, MySQL 8, Redis 7.

```bash
# 1. Clone and create a virtual environment
git clone <repo-url>
cd task-notify-backend
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirement.txt

# 3. Create the database (MySQL)
#    CREATE DATABASE task_notify_db CHARACTER SET utf8mb4;

# 4. Configure environment: create a .env file in the project root (see below)

# 5. Migrate and seed roles/permissions
python manage.py migrate
python manage.py seed_roles

# 6. Create an admin user
python manage.py createsuperuser

# 7. Run the API
python manage.py runserver
```

Run these in separate terminals:

```bash
# Celery worker  (on Windows add: -P solo)
celery -A config worker -l info

# Celery Beat (periodic tasks)
celery -A config beat -l info
```

---

## Environment Variables

Create a `.env` file in the project root. `python-decouple` reads it automatically. **Never commit `.env`.**

| Variable               | Default                                         | Description                                |
|------------------------|-------------------------------------------------|--------------------------------------------|
| `SECRET_KEY`           | `change-me-in-production`                       | Django secret key. **Must be set in production.** |
| `DEBUG`                | `True`                                          | Set to `False` in production               |
| `ALLOWED_HOSTS`        | `localhost,127.0.0.1`                           | Comma-separated hosts                      |
| `DB_NAME`              | `task_notify_db`                                | MySQL database name                        |
| `DB_USER`              | `root`                                          | MySQL user                                 |
| `DB_PASSWORD`          | `root`                                          | MySQL password. **Must be set in production.** |
| `DB_HOST`              | `localhost`                                     | MySQL host                                 |
| `DB_PORT`              | `3306`                                          | MySQL port                                 |
| `REDIS_URL`            | `redis://localhost:6379/0`                      | Celery broker                              |
| `REDIS_CACHE_URL`      | `redis://localhost:6379/1`                      | Cache backend                              |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000`                         | Comma-separated allowed origins            |
| `EMAIL_BACKEND`        | `django.core.mail.backends.console.EmailBackend` | Console backend by default (see [Notifications](#notifications)) |
| `EMAIL_HOST`           | `smtp.gmail.com`                                | SMTP host                                  |
| `EMAIL_PORT`           | `587`                                           | SMTP port                                  |
| `EMAIL_USE_TLS`        | `True`                                          | Use TLS                                    |
| `EMAIL_HOST_USER`      | (empty)                                         | SMTP user                                  |
| `EMAIL_HOST_PASSWORD`  | (empty)                                         | SMTP password / app password               |
| `DEFAULT_FROM_EMAIL`   | `TASK-NOTIFY <noreply@tasknotify.com>`          | Sender address                             |

Minimal local `.env`:

```env
SECRET_KEY=replace-with-a-long-random-string
DEBUG=True
DB_NAME=task_notify_db
DB_USER=root
DB_PASSWORD=your-mysql-password
DB_HOST=localhost
```

---

## Roles and Permissions

Seeded by `python manage.py seed_roles`. Permissions are stored in the database and cached in Redis per user.

| Permission            | admin | manager | member | viewer |
|-----------------------|:-----:|:-------:|:------:|:------:|
| `task:create`         | ✓ | ✓ | ✓ |   |
| `task:read`           | ✓ | ✓ | ✓ | ✓ |
| `task:update`         | ✓ | ✓ | ✓ |   |
| `task:delete`         | ✓ |   |   |   |
| `task:assign`         | ✓ | ✓ |   |   |
| `user:manage`         | ✓ |   |   |   |
| `user:read`           | ✓ | ✓ |   |   |
| `report:view`         | ✓ | ✓ | ✓ | ✓ |
| `report:export`       | ✓ |   |   |   |
| `notification:manage` | ✓ | ✓ |   |   |
| `notification:read`   |   |   | ✓ | ✓ |
| `audit:view`          | ✓ |   |   |   |

---

## API Endpoints

All endpoints are under the same host. Authenticated endpoints expect `Authorization: Bearer <access_token>`. Lists are paginated (`?page=1&page_size=20`, max page size 100). Access tokens last 60 minutes, refresh tokens 7 days.

### Auth and Users
| Method | Endpoint                          | Access      | Description                              |
|--------|-----------------------------------|-------------|------------------------------------------|
| POST   | `/api/auth/register/`             | Public      | Register (`email`, `name`, `password`, `confirm_password`) |
| POST   | `/api/auth/login/`                | Public      | Obtain access and refresh tokens         |
| POST   | `/api/auth/refresh/`              | Public      | Refresh access token                     |
| POST   | `/api/auth/logout/`               | Auth        | Blacklist the refresh token              |
| GET    | `/api/auth/me/`                   | Auth        | Current user profile                     |
| PUT    | `/api/auth/me/`                   | Auth        | Update profile                           |
| GET    | `/api/users/my-permissions/`      | Auth        | Roles and permissions of the current user |
| GET    | `/api/users/check-role/<role_id>/`| Auth        | Check whether the current user has a role |

### Role Administration
| Method | Endpoint                    | Access          | Description                                     |
|--------|-----------------------------|-----------------|-------------------------------------------------|
| GET    | `/api/admin/roles/`         | Admin role      | List roles                                      |
| POST   | `/api/admin/assign-role/`   | Permission-based | Body: `{"user_id": "<uuid>", "role_id": <int>}` |
| DELETE | `/api/admin/remove-role/`   | Permission-based | Body: `{"user_id": "<uuid>", "role_id": <int>}` |

### Tasks
| Method | Endpoint                       | Description                                   |
|--------|--------------------------------|-----------------------------------------------|
| GET    | `/api/tasks/`                  | List tasks (filter, search, order, paginate)  |
| POST   | `/api/tasks/`                  | Create a task (supports an `idempotency_key`) |
| GET    | `/api/tasks/<uuid>/`           | Task detail                                   |
| PUT    | `/api/tasks/<uuid>/`           | Full update                                   |
| PATCH  | `/api/tasks/<uuid>/`           | Partial update                                |
| DELETE | `/api/tasks/<uuid>/`           | Delete                                        |
| PATCH  | `/api/tasks/<uuid>/assign/`    | Assign. Body: `{"assigned_to": "<user_uuid>"}` |

**Query parameters for `GET /api/tasks/`:**

```
?status=pending|in_progress|completed|overdue
?priority=low|medium|high
?assigned_to=<user_uuid>
?due_date__gte=YYYY-MM-DD&due_date__lte=YYYY-MM-DD&due_date__date=YYYY-MM-DD
?search=<text>                       # title and description
?ordering=created_at|due_date|priority   # prefix with - for descending
?page=1&page_size=20
```

### Notifications
| Method | Endpoint                             | Description              |
|--------|--------------------------------------|--------------------------|
| GET    | `/api/notifications/`                | List my notifications    |
| PUT    | `/api/notifications/<uuid>/read/`    | Mark one as read         |
| POST   | `/api/notifications/read-all/`       | Mark all as read         |
| GET    | `/api/notifications/unread-count/`   | Unread count             |

### Dashboard and Reports
| Method | Endpoint                    | Description                                              |
|--------|-----------------------------|----------------------------------------------------------|
| GET    | `/api/dashboard/summary/`   | Task counts and completion rate                          |
| GET    | `/api/reports/`             | Task report. Params: `start_date`, `end_date`, `user_id` |

### Audit Logs
| Method | Endpoint               | Access | Description                                                        |
|--------|------------------------|--------|--------------------------------------------------------------------|
| GET    | `/api/activity-logs/`  | Admin  | Params: `user`, `action`, `resource_type`, `start`, `end`, `search`, `ordering` |

### System
| Method | Endpoint        | Description                                        |
|--------|-----------------|----------------------------------------------------|
| GET    | `/api/health/`  | Database and Redis check (200 healthy, 503 degraded) |

---

## Notifications

Notifications are generated by an event-driven pipeline:

1. A task event (for example `CREATED`) is recorded as a `TaskEvent`.
2. `notifications/services.py` resolves the recipients: assignee, creator, and task watchers.
3. Each recipient's `NotificationPreference` (per event type and channel) decides whether a `Notification` is created. Default preferences are created automatically for every new user (`users/signals.py`).
4. `deliver_notification` processes each notification and records a `NotificationDelivery` attempt.

**Idempotency:** duplicate `Notification` rows are prevented with a unique `event_id`. Delivery uses a Redis lock plus a database status check inside `select_for_update()` so a notification is not processed twice.

**Channels:** `IN_APP` is the active channel. Real email sending is **not implemented yet**; with the default console email backend, emails are only printed to the console.

---

## Celery Periodic Tasks

Beat uses the database scheduler. Create these in Django Admin under **Periodic Tasks**:

| Task name                                  | Suggested schedule | Purpose                                  |
|--------------------------------------------|--------------------|------------------------------------------|
| `notifications.deadline_reminder`          | Every 1 hour       | Remind users of tasks due within 24 hours |
| `notifications.mark_overdue_tasks`         | Every 30 minutes   | Mark past-due tasks as overdue           |
| `notifications.cleanup_old_notifications`  | Daily at 00:00     | Delete read notifications older than 30 days |

---

## Caching

| Data               | Key                          | TTL    | Invalidated by                    |
|--------------------|------------------------------|--------|-----------------------------------|
| Dashboard summary  | `tnb:dashboard_summary`      | 5 min  | Task save/delete                  |
| Task detail        | `tnb:task_detail:<pk>`       | 15 min | Task save/delete/update/assign    |
| Notification list  | per user                     | 2 min  | Mark read                         |
| Unread count       | per user                     | 1 min  | Mark read                         |
| Report data        | per query parameters         | 10 min | Expiry                            |

Redis is also used for permission lookups (cached per user, invalidated on role assignment/removal) and for sessions.

---

## Logging

JSON logs are written to `logs_dir/`:

| File         | Content                         | Rotation            |
|--------------|---------------------------------|---------------------|
| `app.log`    | Application events (INFO+)      | 10 MB x 5 backups   |
| `errors.log` | ERROR and above                 | 5 MB x 3 backups    |
| `audit.log`  | User action audit trail         | Daily x 90 days     |
| `celery.log` | Celery task lifecycle           | 10 MB x 3 backups   |

```python
import logging
logger = logging.getLogger("app")        # general
audit_logger = logging.getLogger("audit")
celery_logger = logging.getLogger("celery")

logger.info("event_name", extra={"key": "value"})
```

Audit helper:

```python
from logs.utils import log_activity

log_activity(
    user=request.user,
    action="task.created",        # ActivityLog.Action choices
    resource_type="Task",
    resource_id=task.pk,
    metadata={"title": task.title},
    request=request,              # extracts IP and user agent
)
```

> Add `logs_dir/` to `.gitignore`. Log files can contain request metadata and must not be committed.

---

## Running Tests

Tests run against the configured MySQL database (Django creates and destroys a separate `test_<DB_NAME>` database). Requirements:

- MySQL and Redis must be running.
- The MySQL user needs permission to create databases:
  ```sql
  GRANT ALL PRIVILEGES ON `test_%`.* TO 'your_user'@'localhost';
  FLUSH PRIVILEGES;
  ```

```bash
# Notifications app (fan-out, idempotency, permissions, regression)
python manage.py test notifications

# Whole project
python manage.py test

# A single module, verbose
python manage.py test notifications.tests.test_fan_out -v 2
```

Test coverage currently exists for the notifications app only. Tests for `users`, `tasks`, `logs` and API-level flows are planned.

---

## Project Status

**Working**
- JWT auth with refresh blacklist, custom user, DB-driven RBAC with Redis-cached permission lookups
- Task CRUD, assignment, filtering/search/ordering, idempotent task creation
- Event-driven in-app notifications with per-user preferences and idempotent delivery
- Audit logging, request logging, dashboard summary, reports, health check
- Celery + Beat jobs for reminders, overdue marking, and cleanup

**In progress / planned**
- Enforce role permissions and ownership checks on every task endpoint
- Multi-tenancy (organization/tenant scoping) for the SaaS model
- Real email delivery (currently console backend only)
- API-level test suite and pytest configuration
- Docker and Docker Compose setup, `.env.example`
- Notification pipeline consolidation (single event path for create, assign, complete, reminder, overdue)