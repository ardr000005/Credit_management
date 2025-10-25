# api/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import date
from decimal import Decimal
import math

from .models import Customer, Loan
from .serializers import (
    RegisterSerializer, CustomerResponseSerializer,
    CheckEligibilityRequestSerializer, CreateLoanRequestSerializer,
    LoanDetailSerializer, CustomerLoanSerializer
)
from .utils import calculate_credit_score


def calculate_emi(loan_amount, interest_rate, tenure):
    """Calculate EMI using compound interest formula."""
    if loan_amount <= 0 or tenure <= 0:
        return 0.0
    r = interest_rate / 12 / 100
    if r == 0:
        return loan_amount / tenure
    return loan_amount * r * (1 + r)**tenure / ((1 + r)**tenure - 1)


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        customer = serializer.save()
        return Response(CustomerResponseSerializer(customer).data, status=status.HTTP_201_CREATED)


class CheckEligibilityView(APIView):
    def post(self, request):
        serializer = CheckEligibilityRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        customer = get_object_or_404(Customer, customer_id=data['customer_id'])

        credit_score = calculate_credit_score(customer)

        # Current EMI sum from active loans
        active_loans = customer.loans.filter(end_date__gte=date.today())
        current_emi_sum = sum(loan.monthly_repayment for loan in active_loans)

        # Check EMI > 50% of salary
        if current_emi_sum > 0.5 * customer.monthly_salary:
            return Response({
                "customer_id": customer.customer_id,
                "approval": False,
                "interest_rate": data['interest_rate'],
                "corrected_interest_rate": None,
                "tenure": data['tenure'],
                "monthly_installment": 0
            }, status=status.HTTP_200_OK)

        # Determine approval and corrected rate
        approval = True
        corrected_rate = data['interest_rate']

        if credit_score > 50:
            pass  # Any rate allowed
        elif credit_score > 30:
            if data['interest_rate'] < 12:
                corrected_rate = 12.0
        elif credit_score > 10:
            if data['interest_rate'] < 16:
                corrected_rate = 16.0
        else:
            approval = False

        if not approval:
            return Response({
                "customer_id": customer.customer_id,
                "approval": False,
                "interest_rate": data['interest_rate'],
                "corrected_interest_rate": None,
                "tenure": data['tenure'],
                "monthly_installment": 0
            }, status=status.HTTP_200_OK)

        # Calculate EMI
        emi = calculate_emi(data['loan_amount'], corrected_rate, data['tenure'])

        return Response({
            "customer_id": customer.customer_id,
            "approval": True,
            "interest_rate": data['interest_rate'],
            "corrected_interest_rate": corrected_rate,
            "tenure": data['tenure'],
            "monthly_installment": round(emi, 2)
        }, status=status.HTTP_200_OK)


class CreateLoanView(APIView):
    def post(self, request):
        serializer = CreateLoanRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        customer = get_object_or_404(Customer, customer_id=data['customer_id'])

        # Reuse eligibility logic
        eligibility_data = {
            "customer_id": data['customer_id'],
            "loan_amount": data['loan_amount'],
            "interest_rate": data['interest_rate'],
            "tenure": data['tenure']
        }
        eligibility_check = CheckEligibilityView()
        eligibility_check.request = request
        eligibility_response = eligibility_check.post(request).data

        if not eligibility_response.get("approval", False):
            return Response({
                "loan_id": None,
                "customer_id": customer.customer_id,
                "loan_approved": False,
                "message": "Loan not approved based on credit score or EMI limit",
                "monthly_installment": 0
            }, status=status.HTTP_200_OK)

        # Create loan
        corrected_rate = eligibility_response['corrected_interest_rate']
        emi = eligibility_response['monthly_installment']
        start_date = date.today()
        # Approximate end date (30 days per month)
        end_date = start_date + timezone.timedelta(days=30 * data['tenure'])

        loan = Loan.objects.create(
            customer=customer,
            loan_amount=data['loan_amount'],
            tenure=data['tenure'],
            interest_rate=corrected_rate,
            monthly_repayment=emi,
            emIs_paid_on_time=0,
            start_date=start_date,
            end_date=end_date
        )

        # Update current debt
        customer.current_debt += Decimal(str(data['loan_amount']))
        customer.save()

        return Response({
            "loan_id": loan.loan_id,
            "customer_id": customer.customer_id,
            "loan_approved": True,
            "message": "Loan approved",
            "monthly_installment": emi
        }, status=status.HTTP_201_CREATED)


class ViewLoanView(APIView):
    def get(self, request, loan_id):
        loan = get_object_or_404(Loan, loan_id=loan_id, customer__isnull=False)
        customer = loan.customer

        return Response({
            "loan_id": loan.loan_id,
            "customer": {
                "id": customer.customer_id,
                "first_name": customer.first_name,
                "last_name": customer.last_name,
                "phone_number": customer.phone_number,
                "age": customer.age
            },
            "loan_amount": loan.loan_amount,
            "interest_rate": loan.interest_rate,
            "monthly_installment": loan.monthly_repayment,
            "tenure": loan.tenure
        }, status=status.HTTP_200_OK)


class ViewLoansByCustomerView(APIView):
    def get(self, request, customer_id):
        customer = get_object_or_404(Customer, customer_id=customer_id)
        active_loans = customer.loans.filter(end_date__gte=date.today())

        response_data = []
        for loan in active_loans:
            repayments_left = loan.tenure - loan.emIs_paid_on_time
            response_data.append({
                "loan_id": loan.loan_id,
                "loan_amount": loan.loan_amount,
                "interest_rate": loan.interest_rate,
                "monthly_installment": loan.monthly_repayment,
                "repayments_left": repayments_left
            })

        return Response(response_data, status=status.HTTP_200_OK)