from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Product


class Coupon(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.code} ({self.discount_percent}%)'

    @property
    def is_valid(self):
        now = timezone.now()
        return self.active and self.valid_from <= now <= self.valid_to


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
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
    phone = models.CharField(max_length=20, help_text='e.g. 0712345678')
    email = models.EmailField(blank=True)

    county = models.CharField(max_length=100)
    town = models.CharField(max_length=100)
    street = models.CharField(max_length=255)
    notes = models.TextField(blank=True)

    coupon = models.ForeignKey(
        Coupon, on_delete=models.SET_NULL, null=True, blank=True
    )
    discount_percent = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

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
        if not self.discount_percent:
            return Decimal('0')
        return (self.get_subtotal() * self.discount_percent / Decimal('100')).quantize(
            Decimal('0.01')
        )

    def get_total(self):
        return self.get_subtotal() - self.get_discount()


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
