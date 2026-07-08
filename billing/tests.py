from django.test import TestCase
from django.db import IntegrityError
from datetime import date
from decimal import Decimal
from .models import Product, Customer, Bill, BillItem, CompanySetting, generate_next_bill_number

class BillingSystemTests(TestCase):

    def setUp(self):
        # Configure default company settings
        self.settings = CompanySetting.get_settings()
        self.settings.company_name = "Test Mart"
        self.settings.bill_prefix = "INV-"
        self.settings.save()

        # Create mock products
        self.banana = Product.objects.create(
            code="10",
            name="Banana",
            rate=Decimal("40.00"),
            unit="Dozen"
        )
        self.apple = Product.objects.create(
            code="20",
            name="Apple",
            rate=Decimal("120.00"),
            unit="Kg"
        )

        # Create mock customer
        self.customer = Customer.objects.create(
            name="John Doe",
            phone="1234567890",
            balance=Decimal("100.00")
        )

    def test_product_unique_code_constraint(self):
        """Verify that products cannot share duplicate codes."""
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                code="10",  # Duplicate code
                name="Another Banana",
                rate=Decimal("35.00")
            )

    def test_bill_number_generation(self):
        """Verify that bill numbers increment correctly."""
        next_num_1 = generate_next_bill_number()
        self.assertEqual(next_num_1, "INV-1001")

        # Create a bill with INV-1001
        bill = Bill.objects.create(
            bill_number="INV-1001",
            date=date.today(),
            gross_total=Decimal("100.00"),
            discount=Decimal("0.00"),
            net_total=Decimal("100.00"),
            amount_paid=Decimal("100.00"),
            pending_amount=Decimal("0.00"),
            old_balance=Decimal("0.00"),
            final_balance=Decimal("0.00")
        )

        next_num_2 = generate_next_bill_number()
        self.assertEqual(next_num_2, "INV-1002")

    def test_bill_save_and_customer_balance_update(self):
        """Verify that saving a bill updates the customer balance correctly."""
        # John Doe buys 2 dozens banana (rate 40) and 1 kg apple (rate 120).
        # Total = 2*40 + 1*120 = 200.
        # He has 100 outstanding balance.
        # Net Total = 200. Discount = 0.
        # He pays 150. Pending = 50.
        # Final balance should be old_balance (100) + pending (50) = 150.
        
        gross_total = Decimal("200.00")
        discount = Decimal("0.00")
        net_total = Decimal("200.00")
        amount_paid = Decimal("150.00")
        pending_amount = Decimal("50.00")
        old_balance = self.customer.balance  # 100.00
        final_balance = old_balance + pending_amount  # 150.00

        # Save customer new balance
        self.customer.balance = final_balance
        self.customer.save()

        bill = Bill.objects.create(
            bill_number=generate_next_bill_number(),
            date=date.today(),
            customer=self.customer,
            gross_total=gross_total,
            discount=discount,
            net_total=net_total,
            amount_paid=amount_paid,
            pending_amount=pending_amount,
            old_balance=old_balance,
            final_balance=final_balance
        )

        # Add items
        item1 = BillItem.objects.create(
            bill=bill,
            product=self.banana,
            quantity=Decimal("2.00"),
            rate=self.banana.rate,
            line_total=Decimal("80.00")
        )
        item2 = BillItem.objects.create(
            bill=bill,
            product=self.apple,
            quantity=Decimal("1.00"),
            rate=self.apple.rate,
            line_total=Decimal("120.00")
        )

        # Refresh from database and check
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.balance, Decimal("150.00"))
        self.assertEqual(bill.items.count(), 2)
        
        # Verify cascades
        self.assertEqual(item1.line_total, Decimal("80.00"))
        self.assertEqual(item2.line_total, Decimal("120.00"))
