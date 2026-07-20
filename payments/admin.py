from django.contrib import admin

from .models import MpesaPayment


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'order', 'phone', 'amount', 'status', 'mpesa_receipt',
        'result_code', 'created',
    ]
    list_filter = ['status', 'created']
    search_fields = ['order__id', 'phone', 'mpesa_receipt', 'checkout_request_id']
    # These mirror Daraja; editing them here would only desync us from them.
    readonly_fields = [
        'order', 'phone', 'amount', 'merchant_request_id', 'checkout_request_id',
        'mpesa_receipt', 'result_code', 'result_desc', 'status',
        'raw_callback', 'created', 'updated',
    ]

    def has_add_permission(self, request):
        return False
