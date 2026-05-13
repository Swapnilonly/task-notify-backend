"""
config/__init__.py
Make Celery available as soon as Django loads.
This ensures the @shared_task decorator works in all apps.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)