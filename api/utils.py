from datetime import date
from .models import Loan

def calculate_credit_score(customer):
    loans = customer.loans.all()
    if not loans:
        return 100  # New customer, high score

    # Factor i: Past loans paid on time (e.g., avg % on-time)
    total_emis = sum(loan.tenure for loan in loans)
    on_time = sum(loan.emIs_paid_on_time for loan in loans)
    on_time_score = (on_time / total_emis) * 30 if total_emis > 0 else 30

    # Factor ii: No of loans (penalize many loans)
    num_loans = len(loans)
    num_loans_score = max(20 - num_loans * 2, 0)

    # Factor iii: Loan activity current year
    current_year = date.today().year
    current_year_loans = [loan for loan in loans if loan.start_date.year == current_year]
    activity_score = 20 if len(current_year_loans) > 0 else 10  # Bonus for activity

    # Factor iv: Loan approved volume (total loan amount, normalize)
    total_volume = sum(loan.loan_amount for loan in loans)
    volume_score = min(total_volume / customer.approved_limit * 20, 20) if customer.approved_limit > 0 else 0

    # Factor v: Sum current loans > approved limit -> 0
    current_loans_sum = sum(loan.loan_amount for loan in loans if loan.end_date >= date.today())  # Assume active if end_date future
    if current_loans_sum > customer.approved_limit:
        return 0

    return int(on_time_score + num_loans_score + activity_score + volume_score)  # Out of ~100