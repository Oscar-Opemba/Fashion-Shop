from django.contrib import admin

from .models import Coupon, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'full_name', 'phone', 'total_display', 'status', 'created',
    ]
    list_filter = ['status', 'created']
    search_fields = ['id', 'full_name', 'phone', 'email']
    inlines = [OrderItemInline]
    date_hierarchy = 'created'
    readonly_fields = ['created', 'updated']

    @admin.display(description='total')
    def total_display(self, obj):
        return f'KES {obj.get_total():,.2f}'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'discount_percent', 'uses_display',
        'valid_from', 'valid_to', 'active',
    ]
    list_filter = ['active', 'categories']
    search_fields = ['code']
    filter_horizontal = ['categories']
    readonly_fields = ['times_used']

    @admin.display(description='uses')
    def uses_display(self, obj):
        return f'{obj.times_used} / {obj.max_uses}'
