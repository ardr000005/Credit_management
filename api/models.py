# api/models.py
from django.db import models

class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    age = models.IntegerField()
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2)
    phone_number = models.CharField(max_length=15)
    approved_limit = models.DecimalField(max_digits=12, decimal_places=2)
    current_debt = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'api_customer'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.customer_id})"


class Loan(models.Model):
    loan_id = models.AutoField(primary_key=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, db_column='customer_id')
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tenure = models.IntegerField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    monthly_repayment = models.DecimalField(max_digits=12, decimal_places=2)
    emIs_paid_on_time = models.IntegerField(db_column='"emIs_paid_on_time"')
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = 'api_loan'

    def __str__(self):
        return f"Loan {self.loan_id} - Customer {self.customer_id}"