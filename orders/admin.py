from django.contrib import admin

from payments.models import MpesaPayment

from .models import Coupon, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0


class MpesaPaymentInline(admin.StackedInline):
    model = MpesaPayment
    extra = 0
    can_delete = False
    # Payment records mirror what Safaricom told us; editing them by hand
    # would only ever desync the two.
    readonly_fields = [
        'phone', 'amount', 'merchant_request_id', 'checkout_request_id',
        'mpesa_receipt', 'result_code', 'result_desc', 'status',
        'raw_callback', 'created', 'updated',
    ]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'full_name', 'phone', 'total_display',
        'status', 'paid', 'receipt', 'created',
    ]
    list_filter = ['paid', 'status', 'created']
    search_fields = ['id', 'full_name', 'phone', 'email']
    inlines = [OrderItemInline, MpesaPaymentInline]
    date_hierarchy = 'created'
    readonly_fields = ['stock_applied', 'created', 'updated']

    @admin.display(description='total')
    def total_display(self, obj):
        return f'KES {obj.get_total():,.2f}'

    @admin.display(description='M-Pesa receipt')
    def receipt(self, obj):
        payment = getattr(obj, 'payment', None)
        return payment.mpesa_receipt if payment else '—'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_percent', 'valid_from', 'valid_to', 'active']
    list_filter = ['active']
    search_fields = ['code']
