# api/serializers.py
from rest_framework import serializers
from .models import Customer, Loan


class RegisterSerializer(serializers.ModelSerializer):
    monthly_income = serializers.IntegerField(source='monthly_salary')

    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'age', 'monthly_income', 'phone_number']

    def create(self, validated_data):
        monthly_salary = validated_data.pop('monthly_salary')
        approved_limit = round(36 * monthly_salary / 100000) * 100000
        return Customer.objects.create(
            **validated_data,
            monthly_salary=monthly_salary,
            approved_limit=approved_limit,
            current_debt=0
        )


class CustomerResponseSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    monthly_income = serializers.IntegerField(source='monthly_salary')

    class Meta:
        model = Customer
        fields = ['customer_id', 'name', 'age', 'monthly_income', 'approved_limit', 'phone_number']

    def get_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class CheckEligibilityRequestSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    loan_amount = serializers.FloatField(min_value=0.01)
    interest_rate = serializers.FloatField(min_value=0)
    tenure = serializers.IntegerField(min_value=1)


class CreateLoanRequestSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    loan_amount = serializers.FloatField(min_value=0.01)
    interest_rate = serializers.FloatField(min_value=0)
    tenure = serializers.IntegerField(min_value=1)


class LoanDetailSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    monthly_installment = serializers.FloatField(source='monthly_repayment')

    class Meta:
        model = Loan
        fields = ['loan_id', 'customer', 'loan_amount', 'interest_rate', 'monthly_installment', 'tenure']

    def get_customer(self, obj):
        c = obj.customer
        return {
            "id": c.customer_id,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "phone_number": c.phone_number,
            "age": c.age
        }


class CustomerLoanSerializer(serializers.ModelSerializer):
    monthly_installment = serializers.FloatField(source='monthly_repayment')
    repayments_left = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = ['loan_id', 'loan_amount', 'interest_rate', 'monthly_installment', 'repayments_left']

    def get_repayments_left(self, obj):
        return obj.tenure - obj.emIs_paid_on_time