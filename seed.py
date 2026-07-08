import os
import django
import random
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'billing_project.settings')
django.setup()

from billing.models import Product, Customer, Bill, BillItem, CompanySetting

def seed():
    print("Seeding database...")
    
    # 1. Company Setting
    settings = CompanySetting.get_settings()
    settings.company_name = "ABC SUPER MART"
    settings.address = "Main Road, Kolhapur, Maharashtra"
    settings.phone = "9876543210"
    settings.gst_number = "27ABCDE1234F1Z5"
    settings.footer_text = "Thank You! Visit Again."
    settings.terms = "Goods once sold cannot be returned."
    settings.bill_prefix = "INV-"
    settings.default_discount = 10.00
    settings.upi_id = "abcsuper@upi"
    settings.save()
    print("Company settings updated.")

    # 2. Customers
    cust_data = [
        ("Rahul Sharma", "9999999999", 250.00),
        ("Priya Patel", "9888888888", 0.00),
        ("Amit Kumar", "9777777777", 1020.50),
        ("Sneha Patil", "9666666666", 0.00),
    ]
    customers = []
    for name, phone, bal in cust_data:
        c, created = Customer.objects.get_or_create(phone=phone, defaults={'name': name, 'balance': bal})
        if not created:
            c.name = name
            c.balance = bal
            c.save()
        customers.append(c)
    print(f"Seeded {len(customers)} customers.")

    # 3. Products
    products_data = [
        ("10", "Fresh Banana", 40.00, "Fruits", "Dozen", "8901001"),
        ("20", "Organic Apple", 120.00, "Fruits", "Kg", "8901002"),
        ("30", "Alphonso Mango", 250.00, "Fruits", "Kg", "8901003"),
        ("40", "Full Cream Milk", 30.00, "Dairy", "Packet", "8901004"),
        ("50", "Brown Bread", 45.00, "Bakery", "Pcs", "8901005"),
        ("60", "Basmati Rice", 110.00, "Groceries", "Kg", "8901006"),
        ("70", "Refined Sunflower Oil", 140.00, "Groceries", "Litre", "8901007"),
        ("80", "Dishwashing Soap", 25.00, "Household", "Pcs", "8901008"),
        ("90", "Salt Iodized", 20.00, "Groceries", "Kg", "8901009"),
        ("100", "Sugar Refined", 48.00, "Groceries", "Kg", "8901010"),
    ]
    
    products = []
    for code, name, rate, cat, unit, bar in products_data:
        p, created = Product.objects.get_or_create(code=code, defaults={
            'name': name, 'rate': rate, 'category': cat, 'unit': unit, 'barcode': bar, 'is_active': True
        })
        if not created:
            p.name = name
            p.rate = rate
            p.category = cat
            p.unit = unit
            p.barcode = bar
            p.is_active = True
            p.save()
        products.append(p)
    print(f"Seeded {len(products)} products.")

    # 4. Mock Bills for Dashboard Analytics (Last 30 Days)
    if Bill.objects.exists():
        print("Bills already exist. Skipping bills generation.")
        return
        
    today = date.today()
    bill_count = 0
    
    for i in range(30):
        bill_date = today - timedelta(days=i)
        num_bills = random.randint(1, 3)
        for b in range(num_bills):
            num_items = random.randint(1, 4)
            items_to_add = random.sample(products, num_items)
            
            gross = 0
            bill_items_list = []
            
            for prod in items_to_add:
                qty = random.randint(1, 5)
                rate = prod.rate
                total = qty * rate
                gross += total
                bill_items_list.append((prod, qty, rate, total))
                
            discount = random.choice([0.00, 10.00, 20.00, 50.00])
            net = max(0.00, float(gross) - discount)
            
            cust = random.choice([None, *customers])
            if cust:
                paid = random.choice([net, net - 100.00, 0.00])
                paid = max(0.00, paid)
                pending = net - paid
                old_bal = float(cust.balance)
                final_bal = old_bal + pending
            else:
                paid = net
                pending = 0.00
                old_bal = 0.00
                final_bal = 0.00
                
            bill_number = f"INV-{1000 + bill_count + 1}"
            
            bill = Bill.objects.create(
                bill_number=bill_number,
                date=bill_date,
                customer=cust,
                gross_total=gross,
                discount=discount,
                net_total=net,
                amount_paid=paid,
                pending_amount=pending,
                old_balance=old_bal,
                final_balance=final_bal
            )
            
            for prod, qty, rate, total in bill_items_list:
                BillItem.objects.create(
                    bill=bill,
                    product=prod,
                    quantity=qty,
                    rate=rate,
                    line_total=total
                )
            bill_count += 1
            
    print(f"Generated {bill_count} historical bills across 30 days.")

if __name__ == '__main__':
    seed()
