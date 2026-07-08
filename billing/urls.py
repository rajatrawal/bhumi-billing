from django.urls import path
from . import views

urlpatterns = [
    # Main billing interface
    path('', views.billing_screen, name='billing_screen'),
    path('billing/save/', views.save_bill, name='save_bill'),
    path('billing/print/<int:bill_id>/', views.print_bill, name='print_bill'),
    path('billing/details/<int:bill_id>/', views.bill_details, name='bill_details'),
    path('billing/duplicate/<int:bill_id>/', views.duplicate_bill, name='duplicate_bill'),
    path('billing/delete/<int:bill_id>/', views.delete_bill, name='delete_bill'),
    
    # Autocomplete JSON API lists
    path('api/products/', views.api_products, name='api_products'),
    path('api/customers/', views.api_customers, name='api_customers'),
    
    # Product CRUD Master
    path('products/', views.product_list, name='product_list'),
    path('products/save/', views.save_product, name='save_product'),
    path('products/delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('products/import/', views.import_products, name='import_products'),
    path('products/export/', views.export_products, name='export_products'),
    
    # History logs
    path('history/', views.billing_history, name='billing_history'),
    path('history/export/', views.export_history, name='export_history'),
    
    # Dashboard stats
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Settings Configuration
    path('settings/', views.settings_panel, name='settings'),
]
