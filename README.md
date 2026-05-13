# TASK-NOTIFY-BACKEND

Production-ready Django REST API for task management, notifications, and audit logging.

---

## Tech Stack

| Layer          | Technology                          |
|----------------|-------------------------------------|
| Framework      | Django 4.2 + DRF                    |
| Auth           | JWT (SimpleJWT) + Token Blacklist   |
| Database       | PostgreSQL 15                       |
| Cache          | Redis 7 (django-redis)              |
| Background     | Celery 5 + Celery Beat              |
| Containerise   | Docker + Docker Compose             |
| Testing        | Pytest + pytest-django + coverage   |

---

## Project Structure

```
task-notify-backend/
├── config/             # Django settings, urls, celery, wsgi
├── users/              # Custom User model, register, login, profile
├── tasks/              # Task CRUD + signals (audit + cache + notifications)
├── notifications/      # Notification model + Celery tasks
├── logs/               # ActivityLog model + audit helper + admin endpoint
├── services/           # Dashboard summary + reporting
├── middleware/         # RequestLoggingMiddleware
├── utils/              # JsonFormatter, pagination, exception handler, health
├── tests/              # All pytest tests
├── logs_dir/           # Runtime log files (gitignored)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Quick Start (Local)

```bash
# 1. Clone & create virtualenv
git clone <repo>
cd task-notify-backend
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your DB and Redis details

# 4. Run migrations
python manage.py migrate

# 5. Create superuser
python manage.py createsuperuser

# 6. Start server
python manage.py runserver

# 7. Start Celery worker (separate terminal)
celery -A config worker -l info

# 8. Start Celery Beat (separate terminal)
celery -A config beat -l info
```

---

## Docker Compose (Recommended)

```bash
cp .env.example .env
docker compose up --build
```

Services started: `web` (8000), `db` (postgres), `redis`, `celery_worker`, `celery_beat`

---

## Environment Variables

| Variable              | Default                         | Description                  |
|-----------------------|---------------------------------|------------------------------|
| `SECRET_KEY`          | change-me                       | Django secret key            |
| `DEBUG`               | True                            | Debug mode                   |
| `DB_NAME`             | task_notify_db                  | PostgreSQL database name     |
| `DB_USER`             | postgres                        | PostgreSQL user              |
| `DB_PASSWORD`         | postgres                        | PostgreSQL password          |
| `DB_HOST`             | localhost                       | PostgreSQL host              |
| `REDIS_URL`           | redis://localhost:6379/0        | Celery broker URL            |
| `REDIS_CACHE_URL`     | redis://localhost:6379/1        | Cache backend URL            |
| `EMAIL_HOST_USER`     | —                               | SMTP email address           |
| `EMAIL_HOST_PASSWORD` | —                               | SMTP password / app password |

---

## API Endpoints

### Auth
| Method | Endpoint              | Access  | Description          |
|--------|-----------------------|---------|----------------------|
| POST   | /api/auth/register    | Public  | Register new user    |
| POST   | /api/auth/login       | Public  | Get JWT tokens       |
| POST   | /api/auth/refresh     | Public  | Refresh access token |
| POST   | /api/auth/logout      | Auth    | Blacklist refresh    |
| GET    | /api/auth/me          | Auth    | Get profile          |
| PUT    | /api/auth/me          | Auth    | Update profile       |

### Tasks
| Method | Endpoint                    | Access      | Description           |
|--------|-----------------------------|-------------|-----------------------|
| GET    | /api/tasks/                 | Auth        | List tasks (filtered) |
| POST   | /api/tasks/                 | Auth        | Create task           |
| GET    | /api/tasks/{id}/            | Auth        | Get single task       |
| PUT    | /api/tasks/{id}/            | Auth        | Update task           |
| PATCH  | /api/tasks/{id}/            | Auth        | Partial update        |
| DELETE | /api/tasks/{id}/            | Auth        | Delete task           |
| PATCH  | /api/tasks/{id}/assign/     | Auth        | Assign to user        |

### Task Query Params
```
?status=pending|in_progress|completed|overdue
?priority=low|medium|high
?assigned_to=<user_id>
?search=<text>
?ordering=created_at|due_date
?page=1&page_size=20
```

### Notifications
| Method | Endpoint                              | Description          |
|--------|---------------------------------------|----------------------|
| GET    | /api/notifications/                   | List notifications   |
| PUT    | /api/notifications/{id}/read/         | Mark single as read  |
| POST   | /api/notifications/read-all/          | Mark all as read     |
| GET    | /api/notifications/unread-count/      | Get unread count     |

### Dashboard & Reports
| Method | Endpoint                              | Access | Description              |
|--------|---------------------------------------|--------|--------------------------|
| GET    | /api/dashboard/summary/               | Auth   | Task counts + completion |
| GET    | /api/reports/?start_date=&end_date=   | Auth   | Filtered task report     |

### Audit Logs
| Method | Endpoint                              | Access | Description               |
|--------|---------------------------------------|--------|---------------------------|
| GET    | /api/activity-logs/                   | Admin  | All audit log entries     |

Query params: `?action=task.created&user=<id>&start=YYYY-MM-DD&end=YYYY-MM-DD`

### System
| Method | Endpoint   | Description                |
|--------|------------|----------------------------|
| GET    | /health/   | DB + Redis health check    |

---

## Logging

Four log files written to `logs_dir/`:

| File         | Content                              | Rotation          |
|--------------|--------------------------------------|-------------------|
| `app.log`    | All INFO+ application events         | 10 MB × 5 backups |
| `errors.log` | ERROR+ only                          | 5 MB × 3 backups  |
| `audit.log`  | Every user action (audit trail)      | Daily × 90 days   |
| `celery.log` | Celery task lifecycle                | 10 MB × 3 backups |

All files use JSON format — compatible with Datadog, Loki, CloudWatch, ELK.

**Using the loggers in your code:**
```python
import logging
logger       = logging.getLogger("app")    # general app logs
audit_logger = logging.getLogger("audit")  # audit trail
celery_logger= logging.getLogger("celery") # task logs

logger.info("event_name", extra={"key": "value"})
```

**Using the audit helper:**
```python
from logs.utils import log_activity

log_activity(
    user          = request.user,
    action        = "task.created",     # use ActivityLog.Action choices
    resource_type = "Task",
    resource_id   = task.pk,
    metadata      = {"title": task.title},
    request       = request,            # auto-extracts IP + user-agent
)
```

---

## Celery Periodic Tasks

Set up in Django Admin → **Periodic Tasks**:

| Task Name                              | Schedule      | Purpose                        |
|----------------------------------------|---------------|--------------------------------|
| `notifications.deadline_reminder`      | Every 1 hour  | Remind users of tasks due <24h |
| `notifications.mark_overdue_tasks`     | Every 30 min  | Mark past-due tasks overdue    |
| `notifications.cleanup_old_notifications` | Daily 00:00| Delete read notifs >30 days   |

---

## Running Tests

```bash
# All tests with coverage
pytest

# Specific file
pytest tests/test_tasks.py -v

# With coverage report
pytest --cov=. --cov-report=html
open htmlcov/index.html
```

---

## Cache Strategy

| Data                    | Cache Key Pattern            | TTL       | Invalidated by       |
|-------------------------|------------------------------|-----------|----------------------|
| Dashboard summary       | `tnb:dashboard_summary`      | 5 min     | Task post_save       |
| Task detail             | `tnb:task_detail:{pk}`       | 15 min    | Task post_save       |
| Notification list       | `tnb:notif_list:{user_id}`   | 2 min     | Mark read            |
| Unread count            | `tnb:unread_count:{user_id}` | 1 min     | Mark read            |
| Report data             | `tnb:report:{params}`        | 10 min    | Manually expired     |