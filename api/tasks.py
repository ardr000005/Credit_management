# api/tasks.py
import pandas as pd
from django.db import connection, transaction
from celery import shared_task, chain
import logging

logger = logging.getLogger(__name__)


@shared_task
def ingest_customer_data(file_path: str):
    """
    Ingest customer_data.xlsx → api_customer
    Headers: customer_id, first_name, last_name, age, phone_number, monthly_salary, approved_limit
    """
    try:
        df = pd.read_excel(file_path)
        logger.info(f"Customer columns: {df.columns.tolist()}")
        logger.info(f"Processing {len(df)} customer records")

        with transaction.atomic():
            with connection.cursor() as cursor:
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT INTO api_customer 
                        (customer_id, first_name, last_name, age, phone_number, monthly_salary, approved_limit, current_debt)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (customer_id) DO UPDATE SET
                            first_name = EXCLUDED.first_name,
                            last_name = EXCLUDED.last_name,
                            age = EXCLUDED.age,
                            phone_number = EXCLUDED.phone_number,
                            monthly_salary = EXCLUDED.monthly_salary,
                            approved_limit = EXCLUDED.approved_limit,
                            current_debt = EXCLUDED.current_debt
                    """, [
                        int(row['customer_id']),
                        str(row['first_name']).strip(),
                        str(row['last_name']).strip(),
                        int(row['age']),
                        str(row['phone_number']).strip(),
                        float(row['monthly_salary']),
                        float(row['approved_limit']),
                        0.0  # Initialize current_debt
                    ])
        
        logger.info("Customer data ingested successfully.")
        return f"Processed {len(df)} customer records"
    except Exception as e:
        logger.error(f"Customer ingestion failed: {e}")
        raise


@shared_task
def ingest_loan_data(file_path: str):
    """
    Ingest loan_data.xlsx → api_loan
    Headers: customer id, loan id, loan amount, tenure, interest rate,
             monthly repayment (emi), EMIs paid on time, start date, end date
    """
    try:
        df = pd.read_excel(file_path)
        logger.info(f"Loan columns: {df.columns.tolist()}")
        logger.info(f"Processing {len(df)} loan records")

        # Use transaction to ensure we get consistent customer data
        with transaction.atomic():
            # Get ALL customer IDs from database in a single transaction
            with connection.cursor() as cursor:
                cursor.execute("SELECT customer_id FROM api_customer")
                valid_customers = {row[0] for row in cursor.fetchall()}
            
            logger.info(f"Found {len(valid_customers)} valid customers in database")

            inserted_count = 0
            error_count = 0
            
            # Process loans in the same transaction
            with connection.cursor() as cursor:
                for _, row in df.iterrows():
                    try:
                        customer_id = int(row['customer id'])
                        loan_id = int(row['loan id'])
                        
                        # Verify customer exists
                        if customer_id not in valid_customers:
                            logger.error(f"Customer {customer_id} not found for loan {loan_id}")
                            error_count += 1
                            continue
                        
                        # Convert dates properly
                        start_date = pd.to_datetime(row['start date']).strftime('%Y-%m-%d')
                        end_date = pd.to_datetime(row['end date']).strftime('%Y-%m-%d')
                        
                        cursor.execute("""
                            INSERT INTO api_loan 
                            (loan_id, customer_id, loan_amount, tenure, interest_rate, monthly_repayment, 
                             "emIs_paid_on_time", start_date, end_date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (loan_id) DO UPDATE SET
                                customer_id = EXCLUDED.customer_id,
                                loan_amount = EXCLUDED.loan_amount,
                                tenure = EXCLUDED.tenure,
                                interest_rate = EXCLUDED.interest_rate,
                                monthly_repayment = EXCLUDED.monthly_repayment,
                                "emIs_paid_on_time" = EXCLUDED."emIs_paid_on_time",
                                start_date = EXCLUDED.start_date,
                                end_date = EXCLUDED.end_date
                        """, [
                            loan_id,
                            customer_id,
                            float(row['loan amount']),
                            int(row['tenure']),
                            float(row['interest rate']),
                            float(row['monthly repayment (emi)']),
                            int(row['EMIs paid on time']),
                            start_date,
                            end_date
                        ])
                        inserted_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error inserting loan {row['loan id']}: {e}")
                        error_count += 1
                        continue

        logger.info(f"Loan ingestion completed: {inserted_count} inserted, {error_count} errors")
        return f"Processed {inserted_count} loans, {error_count} errors"
    except Exception as e:
        logger.error(f"Loan ingestion failed: {e}")
        raise


@shared_task
def update_current_debts():
    """
    Update current_debt = SUM(monthly_repayment * remaining_emis)
    remaining_emis = tenure - emIs_paid_on_time
    """
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE api_customer 
                    SET current_debt = (
                        SELECT COALESCE(SUM(
                            l.monthly_repayment * GREATEST(0, l.tenure - l."emIs_paid_on_time")
                        ), 0)
                        FROM api_loan l
                        WHERE l.customer_id = api_customer.customer_id
                    )
                """)
                updated_count = cursor.rowcount
                
        logger.info(f"Current debts updated for {updated_count} customers.")
        return f"Updated debts for {updated_count} customers"
    except Exception as e:
        logger.error(f"Debt update failed: {e}")
        raise


@shared_task
def import_all_data():
    """
    Master task: Customers → Loans → Update Debts (SEQUENTIAL)
    This ensures proper ordering and prevents concurrent execution
    """
    try:
        logger.info("=== STARTING COMPLETE DATA IMPORT ===")
        
        # Define file paths (adjust as needed)
        customer_file = '/app/data/customer_data.xlsx'
        loan_file = '/app/data/loan_data.xlsx'
        
        # Step 1: Import Customers
        logger.info("STEP 1: Importing customers...")
        customer_result = ingest_customer_data(customer_file)
        logger.info(f"CUSTOMER IMPORT: {customer_result}")
        
        # Step 2: Import Loans  
        logger.info("STEP 2: Importing loans...")
        loan_result = ingest_loan_data(loan_file)
        logger.info(f"LOAN IMPORT: {loan_result}")
        
        # Step 3: Update Debts
        logger.info("STEP 3: Updating current debts...")
        debt_result = update_current_debts()
        logger.info(f"DEBT UPDATE: {debt_result}")
        
        logger.info("=== DATA IMPORT COMPLETED SUCCESSFULLY ===")
        return {
            "customers": customer_result,
            "loans": loan_result, 
            "debts": debt_result
        }
        
    except Exception as e:
        logger.error(f"Complete data import failed: {e}")
        raise