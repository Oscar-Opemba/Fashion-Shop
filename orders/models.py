from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from shop.models import Product


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)

    # Scope the discount to products in these categories. Left empty, the
    # coupon applies to the whole cart (the original behaviour).
    categories = models.ManyToManyField(
        'shop.Category', blank=True, related_name='coupons',
        help_text='Only discount products in these categories. '
                  'Leave empty to apply to the whole cart.',
    )

    # How many times the coupon may be redeemed in total, and how many times it
    # already has been. A redemption is counted when an order is actually paid
    # (see payments._mark_paid), not when the code is applied at checkout.
    max_uses = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text='Total number of times this coupon can be redeemed.',
    )
    times_used = models.PositiveIntegerField(default=0, editable=False)

    def __str__(self):
        return f'{self.code} ({self.discount_percent}%)'

    @property
    def is_valid(self):
        now = timezone.now()
        return (
            self.active
            and self.valid_from <= now <= self.valid_to
            and self.times_used < self.max_uses
        )

    def discount_for(self, lines):
        """Discount (Decimal) this coupon gives on an iterable of cart/order lines.

        `lines` is an iterable of ``(product, line_cost)`` pairs. Only lines
        whose product sits in one of the coupon's categories count toward the
        discount; with no categories set, every line qualifies. Returns whole
        cents, rounded to two places.
        """
        category_ids = set(self.categories.values_list('id', flat=True))
        qualifying = sum(
            (
                cost for product, cost in lines
                if not category_ids or product.category_id in category_ids
            ),
            Decimal('0'),
        )
        return (qualifying * self.discount_percent / Decimal('100')).quantize(
            Decimal('0.01')
        )


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending payment'
        PAID = 'paid', 'Paid'
        # Kept from the period when checkout completed without a payment step,
        # so orders placed then still render a label instead of a blank.
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    # Orders survive their user being deleted, so history stays auditable.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders',
    )

    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, help_text='M-Pesa number, e.g. 0712345678')
    email = models.EmailField(blank=True)

    county = models.CharField(max_length=100)
    town = models.CharField(max_length=100)
    street = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    coupon = models.ForeignKey(
        Coupon, on_delete=models.SET_NULL, null=True, blank=True
    )
    discount_percent = models.PositiveIntegerField(default=0)
    # The discount in shillings, frozen at checkout. Because a coupon can now
    # be scoped to categories, the percentage alone no longer determines the
    # amount, so the computed figure is captured the same way item prices are.
    # NULL means "never had a coupon" (or a legacy order) — distinct from a
    # coupon that qualified for 0 off because nothing in the cart matched.
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    paid = models.BooleanField(default=False)
    # Set when stock is decremented, so a replayed callback cannot do it twice.
    stock_applied = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        indexes = [models.Index(fields=['-created']), models.Index(fields=['status'])]

    def __str__(self):
        return f'Order #{self.pk}'

    def get_subtotal(self):
        return sum((item.get_cost() for item in self.items.all()), Decimal('0'))

    def get_discount(self):
        # Prefer the amount frozen at checkout (it already accounts for any
        # category scoping). Fall back to the percentage for orders created
        # before discounts were snapshotted.
        if self.discount_amount is not None:
            return self.discount_amount
        if not self.discount_percent:
            return Decimal('0')
        return (self.get_subtotal() * self.discount_percent / Decimal('100')).quantize(
            Decimal('0.01')
        )

    def get_total(self):
        return self.get_subtotal() - self.get_discount()

    def get_mpesa_amount(self):
        """Daraja rejects decimals, so the charge is rounded up to whole shillings."""
        total = self.get_total()
        return max(1, int(total.to_integral_value(rounding='ROUND_CEILING')))

    # ---- Tracking -------------------------------------------------------
    #
    # The stages a parcel actually moves through, in order. CANCELLED is not
    # among them: it is an exit from the sequence, not a step along it, and the
    # timeline renders it as one.
    TIMELINE = [
        (Status.PENDING, 'Order placed', 'We have your order and are waiting for payment.'),
        (Status.PAID, 'Payment received', 'M-Pesa confirmed your payment.'),
        (Status.PROCESSING, 'Packing', 'We are picking and packing your items.'),
        (Status.SHIPPED, 'On the way', 'Your parcel is with the courier.'),
        (Status.DELIVERED, 'Delivered', 'Signed for. Enjoy it.'),
    ]

    def record_status(self, status, note=''):
        """Move the order to `status` and log it, unless it is already there.

        Every status change in the codebase goes through here so the timeline
        is a record rather than a guess. Returns the event, or None when
        nothing changed — callers use that to avoid sending a duplicate
        notification.
        """
        if self.status == status and self.events.filter(status=status).exists():
            return None

        self.status = status
        self.save(update_fields=['status', 'updated'])
        return self.events.create(status=status, note=note)

    def timeline(self):
        """The five stages, each marked done / current / upcoming.

        Read off the recorded events rather than off `status` alone, so an
        order that jumped straight from pending to shipped does not show
        "Payment received" as though it never happened.
        """
        reached = {event.status: event for event in self.events.all()}
        order_of = [status for status, _, _ in self.TIMELINE]

        try:
            current_index = order_of.index(self.status)
        except ValueError:
            # CANCELLED, or a status not in the sequence.
            current_index = -1

        steps = []
        for index, (status, label, blurb) in enumerate(self.TIMELINE):
            event = reached.get(status)
            steps.append({
                'status': status,
                'label': label,
                'blurb': blurb,
                'done': event is not None or (0 <= current_index and index < current_index),
                'current': index == current_index,
                'at': event.created if event else None,
            })
        return steps

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    def matches_phone(self, phone):
        """Is `phone` the number this order was placed with?

        Compared on the last nine digits, which is the part that identifies a
        Kenyan subscriber: 0712345678, +254712345678 and 254712345678 are the
        same person, and a shopper tracking a parcel should not have to
        remember which form they typed at checkout.
        """
        mine = ''.join(c for c in self.phone if c.isdigit())[-9:]
        theirs = ''.join(c for c in str(phone) if c.isdigit())[-9:]
        return bool(mine) and mine == theirs


class OrderStatusEvent(models.Model):
    """One entry in an order's history.

    Append-only. The order's own `status` column is the current state; this is
    how it got there, which is what the tracking page and the mobile app show
    and what makes "shipped on Tuesday" answerable at all.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='events')
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created']
        indexes = [models.Index(fields=['order', 'created'])]

    def __str__(self):
        return f'{self.order} -> {self.status}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    # Products are kept, not cascaded, so an order line never loses its history.
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    # Price is captured at purchase time and never re-read from the product.
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f'{self.quantity} x {self.product}'

    def get_cost(self):
        return self.price * self.quantity
