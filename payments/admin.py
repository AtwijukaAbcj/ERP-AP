from django.contrib import admin
from .models import Invoice


@admin.register(Invoice)
class PaymentInvoiceAdmin(admin.ModelAdmin):
    list_display = ('user', 'invoice_code', 'total', 'amount', 'payment_complete')
    list_filter = ('payment_complete',)
    search_fields = ('user__username', 'invoice_code')

