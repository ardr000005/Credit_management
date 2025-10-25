# api/apps.py
from django.apps import AppConfig
import os

class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        if os.environ.get('RUN_MAIN') or 'celery' in os.environ.get('CMD', ''):
            return

        from django.db import connection
        if 'api_loan' in connection.introspection.table_names():
            return

        from .tasks import ingest_customer_data, ingest_loan_data, update_current_debts
        ingest_customer_data.delay('customer_data.xlsx')
        ingest_loan_data.delay('loan_data.xlsx')
        update_current_debts.delay()