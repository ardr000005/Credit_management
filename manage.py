#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import time
from django.db import connection


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'credit_system.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    # Custom command: python manage.py wait_for_db
    if 'wait_for_db' in sys.argv:
        while True:
            try:
                connection.ensure_connection()
                print("Database is ready!")
                break
            except Exception as e:
                print("Waiting for database...", e)
                time.sleep(2)
        sys.exit(0)

    main()