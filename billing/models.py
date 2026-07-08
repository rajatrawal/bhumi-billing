from django.db import models
from django.db.models import Max
import re

class Product(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255, db_index=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    category = models.CharField(max_length=100, blank=True, default="")
    unit = models.CharField(max_length=50, default="Pcs")
    barcode = models.CharField(max_length=100, blank=True, default="", db_index=True)
    gst_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True, db_index=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Customer(models.Model):
    name = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=15, blank=True, default="", db_index=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name or self.phone or "Walk-in Customer"


class Bill(models.Model):
    bill_number = models.CharField(max_length=50, unique=True, db_index=True)
    date = models.DateField(db_index=True)
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.SET_NULL, related_name="bills")
    gross_total = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_total = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    pending_amount = models.DecimalField(max_digits=12, decimal_places=2)
    old_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    final_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.bill_number


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    sr_no = models.IntegerField(default=0, db_index=True)

    class Meta:
        ordering = ['sr_no']

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class CompanySetting(models.Model):
    company_name = models.CharField(max_length=255, default="My Retail Store")
    address = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    gst_number = models.CharField(max_length=50, blank=True, default="")
    footer_text = models.TextField(blank=True, default="Thank you! Visit again.")
    terms = models.TextField(blank=True, default="Goods once sold cannot be returned.")
    bill_prefix = models.CharField(max_length=10, default="INV-")
    default_discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    upi_id = models.CharField(max_length=100, blank=True, default="")

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj


def generate_next_bill_number():
    settings = CompanySetting.get_settings()
    prefix = settings.bill_prefix
    last_bill = Bill.objects.filter(bill_number__startswith=prefix).order_by('-id').first()
    if not last_bill:
        return f"{prefix}1001"
    
    bill_num_str = last_bill.bill_number
    # Search for trailing digits in the bill number
    match = re.search(r'(\d+)$', bill_num_str)
    if match:
        num_str = match.group(1)
        num = int(num_str)
        next_num = num + 1
        length = len(num_str)
        # Pad with zeros to maintain length
        next_num_str = str(next_num).zfill(length)
        # Replace only the trailing match
        return bill_num_str[:match.start()] + next_num_str
    else:
        return f"{prefix}{last_bill.id + 1001}"
