from django.test import TestCase
from rest_framework.test import APIClient
from .models import Customer

class CustomerTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "age": 30,
            "monthly_income": 5000,
            "phone_number": "1234567890"
        }
        response = self.client.post('/register/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Customer.objects.count(), 1)
        self.assertEqual(Customer.objects.first().approved_limit, 200000)  # 36*5000=180000, round to 200000?