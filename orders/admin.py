from django.contrib import admin

from .models import Coupon, Order, OrderItem, OrderStatusEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0


class OrderStatusEventInline(admin.TabularInline):
    """The order's history, read-only.

    Shown rather than edited: the timeline is a record of what happened, and a
    record you can retype is not one. Staff change an order's status with the
    `status` field or the actions below, and an event is written for them.
    """

    model = OrderStatusEvent
    extra = 0
    readonly_fields = ['status', 'note', 'created']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'full_name', 'phone', 'total_display', 'status', 'created',
    ]
    list_filter = ['status', 'created']
    search_fields = ['id', 'full_name', 'phone', 'email']
    inlines = [OrderItemInline, OrderStatusEventInline]
    date_hierarchy = 'created'
    readonly_fields = ['created', 'updated']
    actions = ['mark_processing', 'mark_shipped', 'mark_delivered']

    @admin.display(description='total')
    def total_display(self, obj):
        return f'KES {obj.get_total():,.2f}'

    def save_model(self, request, obj, form, change):
        """Route a status edit through record_status so it lands on the timeline.

        Editing the dropdown on this page is how an order actually becomes
        "shipped" in day-to-day use. Without this the column would change and
        the shopper's tracker would not, which is worse than having no tracker
        — it would be confidently out of date.
        """
        if change and 'status' in form.changed_data:
            # record_status saves the row itself; let it, then write whatever
            # else the form changed.
            new_status = obj.status
            obj.status = form.initial.get('status', obj.status)
            super().save_model(request, obj, form, change)
            obj.record_status(new_status, f'Updated by {request.user}.')
            return
        super().save_model(request, obj, form, change)

    def _bulk_mark(self, request, queryset, status, label):
        changed = sum(
            1 for order in queryset
            if order.record_status(status, f'Updated by {request.user}.')
        )
        self.message_user(request, f'{changed} order(s) marked {label}.')

    @admin.action(description='Mark selected orders as packing')
    def mark_processing(self, request, queryset):
        self._bulk_mark(request, queryset, Order.Status.PROCESSING, 'packing')

    @admin.action(description='Mark selected orders as shipped')
    def mark_shipped(self, request, queryset):
        self._bulk_mark(request, queryset, Order.Status.SHIPPED, 'shipped')

    @admin.action(description='Mark selected orders as delivered')
    def mark_delivered(self, request, queryset):
        self._bulk_mark(request, queryset, Order.Status.DELIVERED, 'delivered')


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
