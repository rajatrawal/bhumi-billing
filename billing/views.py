from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.db import transaction, IntegrityError
from django.db.models import Sum, Avg, Q, F
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils import timezone
from datetime import date, timedelta
import json
import csv
import io

from .models import Product, Customer, Bill, BillItem, CompanySetting, generate_next_bill_number

# 1. Billing Screen
def billing_screen(request):
    settings = CompanySetting.get_settings()
    next_bill = generate_next_bill_number()
    today = date.today().strftime('%Y-%m-%d')
    
    # Check if there are duplicated items stored in session
    duplicate_items = request.session.pop('duplicate_bill_items', None)
    duplicate_cust = request.session.pop('duplicate_customer', None)
    
    context = {
        'next_bill_number': next_bill,
        'today_date': today,
        'settings': settings,
        'duplicate_items_json': json.dumps(duplicate_items) if duplicate_items else 'null',
        'duplicate_cust_json': json.dumps(duplicate_cust) if duplicate_cust else 'null',
    }
    return render(request, 'billing/billing_screen.html', context)

# 2. Save Bill API (POST JSON)
@transaction.atomic
def save_bill(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests allowed.'}, status=400)
    
    try:
        data = json.loads(request.body)
        
        customer_name = data.get('customer_name', '').strip()
        customer_phone = data.get('customer_phone', '').strip()
        gross_total = float(data.get('gross_total', 0))
        discount = float(data.get('discount', 0))
        net_total = float(data.get('net_total', 0))
        amount_paid = float(data.get('amount_paid', 0))
        pending_amount = float(data.get('pending_amount', 0))
        old_balance = float(data.get('old_balance', 0))
        final_balance = float(data.get('final_balance', 0))
        items_data = data.get('items', [])
        
        if not items_data:
            return JsonResponse({'status': 'error', 'message': 'Cannot save bill with no items.'}, status=400)
        
        # Link or create customer
        customer = None
        if customer_name or customer_phone:
            # If phone is provided, check if customer already exists, otherwise create
            if customer_phone:
                customer, created = Customer.objects.get_or_create(
                    phone=customer_phone,
                    defaults={'name': customer_name, 'balance': 0.00}
                )
                if not created and customer_name and customer.name != customer_name:
                    customer.name = customer_name
            else:
                # Phone empty, name provided
                customer = Customer.objects.create(name=customer_name, balance=0.00)
            
            # Update customer balance
            customer.balance = final_balance
            customer.save()
        
        # Create Bill
        bill_number = generate_next_bill_number()
        
        bill = Bill.objects.create(
            bill_number=bill_number,
            date=date.today(),
            customer=customer,
            gross_total=gross_total,
            discount=discount,
            tax_total=0.00,
            net_total=net_total,
            amount_paid=amount_paid,
            pending_amount=pending_amount,
            old_balance=old_balance,
            final_balance=final_balance
        )
        
        # Create BillItems in bulk
        bill_items = []
        for item in items_data:
            product = get_object_or_404(Product, id=item['product_id'])
            bill_items.append(
                BillItem(
                    bill=bill,
                    product=product,
                    quantity=item['quantity'],
                    rate=item['rate'],
                    line_total=item['line_total'],
                    sr_no=item.get('sr_no', 0)
                )
            )
        BillItem.objects.bulk_create(bill_items)
        
        # Get next bill number for stay-on-page refresh view
        next_bill = generate_next_bill_number()
        
        return JsonResponse({
            'status': 'success',
            'bill_id': bill.id,
            'bill_number': bill.bill_number,
            'next_bill_number': next_bill
        })
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# 3. Product autocomplete list API
def api_products(request):
    products = Product.objects.filter(is_active=True).values('id', 'code', 'name', 'rate', 'barcode')
    return JsonResponse(list(products), safe=False)

# 4. Customer autocomplete list API
def api_customers(request):
    customers = Customer.objects.all().values('id', 'name', 'phone', 'balance')
    return JsonResponse(list(customers), safe=False)

# 5. Printable Invoice
def print_bill(request, bill_id):
    bill = get_object_or_404(Bill.objects.select_related('customer'), id=bill_id)
    items = BillItem.objects.filter(bill=bill).order_by('sr_no').select_related('product')
    settings = CompanySetting.get_settings()
    
    context = {
        'bill': bill,
        'items': items,
        'settings': settings
    }
    return render(request, 'print/invoice_a5.html', context)

# 6. Product Master CRUD
def product_list(request):
    q = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'name').strip()
    
    products_query = Product.objects.all()
    if q:
        products_query = products_query.filter(
            Q(code__icontains=q) | 
            Q(name__icontains=q) | 
            Q(barcode__icontains=q) |
            Q(category__icontains=q)
        )
        
    if sort in ['name', '-name', 'code', 'rate', '-rate']:
        products_query = products_query.order_by(sort)
        
    # Count stats
    total_count = Product.objects.count()
    active_count = Product.objects.filter(is_active=True).count()
    inactive_count = total_count - active_count
    
    paginator = Paginator(products_query, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'products': page_obj,
        'total_count': total_count,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'q': q,
        'sort': sort
    }
    return render(request, 'billing/product_list.html', context)

def save_product(request):
    if request.method == 'POST':
        prod_id = request.POST.get('id')
        code = request.POST.get('code').strip()
        name = request.POST.get('name').strip()
        rate = request.POST.get('rate')
        category = request.POST.get('category').strip()
        unit = request.POST.get('unit', 'Pcs').strip()
        barcode = request.POST.get('barcode').strip()
        gst_percentage = request.POST.get('gst_percentage', 0)
        is_active = request.POST.get('is_active') == 'true'
        
        try:
            if prod_id:
                # Edit Mode
                product = get_object_or_404(Product, id=prod_id)
                product.code = code
                product.name = name
                product.rate = rate
                product.category = category
                product.unit = unit
                product.barcode = barcode
                product.gst_percentage = gst_percentage
                product.is_active = is_active
                product.save()
                messages.success(request, f"Product '{name}' updated successfully.")
            else:
                # Add Mode
                Product.objects.create(
                    code=code,
                    name=name,
                    rate=rate,
                    category=category,
                    unit=unit,
                    barcode=barcode,
                    gst_percentage=gst_percentage,
                    is_active=is_active
                )
                messages.success(request, f"Product '{name}' added successfully.")
        except IntegrityError:
            messages.error(request, f"Error: Product code '{code}' already exists.")
        except Exception as e:
            messages.error(request, f"Error saving product: {str(e)}")
            
    return redirect('product_list')

def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        name = product.name
        product.delete()
        messages.success(request, f"Product '{name}' deleted successfully.")
    except Exception:
        # Product is referenced in past bills, cannot delete because of PROTECT foreign key
        product.is_active = False
        product.save()
        messages.warning(request, f"Product '{product.name}' is referenced in past transactions. Marked as Inactive instead.")
    return redirect('product_list')

# 7. CSV Import / Export
def import_products(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "File is not CSV type.")
            return redirect('product_list')
            
        try:
            file_data = csv_file.read().decode("utf-8")
            io_string = io.StringIO(file_data)
            reader = csv.reader(io_string)
            
            # Read header
            header = next(reader, None)
            
            count = 0
            skipped = 0
            products_to_create = []
            
            for row in reader:
                if not row or len(row) < 3:
                    continue
                code = row[0].strip()
                name = row[1].strip()
                rate = float(row[2].strip() or 0)
                category = row[3].strip() if len(row) > 3 else ""
                unit = row[4].strip() if len(row) > 4 else "Pcs"
                barcode = row[5].strip() if len(row) > 5 else ""
                gst = float(row[6].strip() or 0) if len(row) > 6 else 0.0
                
                # Avoid duplicates
                if Product.objects.filter(code=code).exists():
                    skipped += 1
                    continue
                    
                products_to_create.append(
                    Product(
                        code=code,
                        name=name,
                        rate=rate,
                        category=category,
                        unit=unit,
                        barcode=barcode,
                        gst_percentage=gst,
                        is_active=True
                    )
                )
                count += 1
                
            if products_to_create:
                Product.objects.bulk_create(products_to_create)
                messages.success(request, f"Successfully imported {count} products. (Skipped {skipped} duplicates)")
            else:
                messages.warning(request, f"No new products imported. (Skipped {skipped} duplicates)")
                
        except Exception as e:
            messages.error(request, f"CSV parsing error: {str(e)}")
            
    return redirect('product_list')

def export_products(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['code', 'name', 'rate', 'category', 'unit', 'barcode', 'gst_percentage'])
    
    products = Product.objects.all().values_list('code', 'name', 'rate', 'category', 'unit', 'barcode', 'gst_percentage')
    for p in products:
        writer.writerow(p)
        
    return response

# 8. Billing History
def billing_history(request):
    q = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    bills_query = Bill.objects.all().select_related('customer').order_by('-id')
    
    if q:
        bills_query = bills_query.filter(
            Q(bill_number__icontains=q) |
            Q(customer__name__icontains=q) |
            Q(customer__phone__icontains=q)
        )
    if start_date:
        bills_query = bills_query.filter(date__gte=start_date)
    if end_date:
        bills_query = bills_query.filter(date__lte=end_date)
        
    paginator = Paginator(bills_query, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'bills': page_obj,
        'q': q,
        'start_date': start_date,
        'end_date': end_date
    }
    return render(request, 'billing/billing_history.html', context)

def bill_details(request, bill_id):
    try:
        bill = Bill.objects.select_related('customer').get(id=bill_id)
        items = BillItem.objects.filter(bill=bill).select_related('product')
        
        bill_data = {
            'bill_number': bill.bill_number,
            'date': bill.date.strftime('%d-%m-%Y'),
            'customer_name': bill.customer.name if bill.customer else 'Walk-in Customer',
            'customer_phone': bill.customer.phone if bill.customer else '',
            'gross_total': float(bill.gross_total),
            'discount': float(bill.discount),
            'net_total': float(bill.net_total),
            'amount_paid': float(bill.amount_paid),
            'pending_amount': float(bill.pending_amount),
            'items': [{
                'product_name': item.product.name,
                'quantity': float(item.quantity),
                'rate': float(item.rate),
                'line_total': float(item.line_total)
            } for item in items]
        }
        return JsonResponse({'status': 'success', 'bill': bill_data})
    except Bill.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Bill not found.'}, status=404)

def duplicate_bill(request, bill_id):
    bill = get_object_or_404(Bill.objects.select_related('customer'), id=bill_id)
    items = BillItem.objects.filter(bill=bill).select_related('product')
    
    # Store billing info in session for retrieval by billing_screen load triggers
    duplicate_items = []
    for item in items:
        duplicate_items.append({
            'product_id': item.product.id,
            'code': item.product.code,
            'name': item.product.name,
            'qty': float(item.quantity),
            'rate': float(item.rate),
            'line_total': float(item.line_total)
        })
        
    request.session['duplicate_bill_items'] = duplicate_items
    if bill.customer:
        request.session['duplicate_customer'] = {
            'name': bill.customer.name,
            'phone': bill.customer.phone,
            'balance': float(bill.customer.balance)
        }
        
    messages.success(request, f"Loaded items from Bill {bill.bill_number} into active billing workspace.")
    return redirect('billing_screen')

@transaction.atomic
def delete_bill(request, bill_id):
    bill = get_object_or_404(Bill.objects.select_related('customer'), id=bill_id)
    bill_number = bill.bill_number
    customer = bill.customer
    
    # Revert customer outstanding balances
    if customer:
        customer.balance = F('balance') - bill.pending_amount
        customer.save()
        
    bill.delete()
    messages.success(request, f"Bill {bill_number} deleted successfully.")
    return redirect('billing_history')

def export_history(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="billing_history.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Bill Number', 'Date', 'Customer Name', 'Customer Phone', 'Gross Total', 'Discount', 'Net Total', 'Paid', 'Pending'])
    
    q = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    bills = Bill.objects.all().select_related('customer').order_by('-id')
    if q:
        bills = bills.filter(
            Q(bill_number__icontains=q) |
            Q(customer__name__icontains=q) |
            Q(customer__phone__icontains=q)
        )
    if start_date:
        bills = bills.filter(date__gte=start_date)
    if end_date:
        bills = bills.filter(date__lte=end_date)
        
    for b in bills:
        writer.writerow([
            b.bill_number,
            b.date.strftime('%Y-%m-%d'),
            b.customer.name if b.customer else 'Walk-in',
            b.customer.phone if b.customer else '',
            b.gross_total,
            b.discount,
            b.net_total,
            b.amount_paid,
            b.pending_amount
        ])
        
    return response

# 9. Analytics Dashboard
def dashboard(request):
    today = date.today()
    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)
    
    # 30 days daily trend dates range
    trend_start = today - timedelta(days=29)
    
    # Fetch core aggregates (optimized)
    stats = {}
    
    # Today stats
    today_stats = Bill.objects.filter(date=today).aggregate(revenue=Sum('net_total'), count=Sum(1))
    stats['today_sales'] = today_stats['revenue'] or 0.00
    stats['today_bills'] = Bill.objects.filter(date=today).count()
    
    # Yesterday stats
    yesterday_stats = Bill.objects.filter(date=yesterday).aggregate(revenue=Sum('net_total'))
    stats['yesterday_sales'] = yesterday_stats['revenue'] or 0.00
    stats['yesterday_bills'] = Bill.objects.filter(date=yesterday).count()
    
    # Monthly stats
    monthly_stats = Bill.objects.filter(date__gte=month_start).aggregate(revenue=Sum('net_total'))
    stats['monthly_sales'] = monthly_stats['revenue'] or 0.00
    
    # Customer receivables outstanding
    stats['total_receivables'] = Customer.objects.aggregate(total=Sum('balance'))['total'] or 0.00
    
    # Global aggregates
    global_stats = Bill.objects.aggregate(
        total_bills=Sum(1),
        avg_bill=Avg('net_total'),
        total_discount=Sum('discount'),
        total_paid=Sum('amount_paid')
    )
    
    stats['total_bills'] = Bill.objects.count()
    stats['avg_bill_value'] = global_stats['avg_bill'] or 0.00
    stats['total_discounts'] = global_stats['total_discount'] or 0.00
    stats['total_collected'] = global_stats['total_paid'] or 0.00
    
    # Top 5 debtors
    stats['top_debtors'] = Customer.objects.filter(balance__gt=0).order_by('-balance')[:10]
    
    # Top 5 selling products
    stats['top_products'] = BillItem.objects.values(
        'product__code', 'product__name'
    ).annotate(
        total_qty=Sum('quantity'),
        total_rev=Sum('line_total')
    ).order_by('-total_qty')[:10]
    
    # Least selling products
    stats['least_products'] = BillItem.objects.values(
        'product__code', 'product__name'
    ).annotate(
        total_qty=Sum('quantity'),
        total_rev=Sum('line_total')
    ).order_by('total_qty')[:10]
    
    # Daily trend dates last 30 days
    daily_sales = Bill.objects.filter(date__gte=trend_start).values('date').annotate(revenue=Sum('net_total')).order_by('date')
    
    # Build complete list of 30 days with 0.00 placeholders to handle gap dates
    daily_sales_dict = {item['date']: float(item['revenue']) for item in daily_sales}
    daily_trend = []
    for i in range(30):
        d = trend_start + timedelta(days=i)
        daily_trend.append({
            'date': d,
            'revenue': daily_sales_dict.get(d, 0.00)
        })
        
    stats['daily_trend'] = daily_trend
    
    return render(request, 'billing/dashboard.html', {'stats': stats})

# 10. Store Settings Panel
def settings_panel(request):
    settings = CompanySetting.get_settings()
    
    if request.method == 'POST':
        settings.company_name = request.POST.get('company_name', '').strip()
        settings.phone = request.POST.get('phone', '').strip()
        settings.gst_number = request.POST.get('gst_number', '').strip()
        settings.address = request.POST.get('address', '').strip()
        settings.bill_prefix = request.POST.get('bill_prefix', '').strip()
        settings.default_discount = float(request.POST.get('default_discount', 0))
        settings.upi_id = request.POST.get('upi_id', '').strip()
        settings.footer_text = request.POST.get('footer_text', '').strip()
        settings.terms = request.POST.get('terms', '').strip()
        settings.save()
        messages.success(request, "Store settings saved successfully.")
        return redirect('settings')
        
    return render(request, 'billing/settings.html', {'settings': settings})
