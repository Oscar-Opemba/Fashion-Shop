from django.db import models

from orders.models import Order


class MpesaPayment(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Awaiting confirmation'
        SUCCESS = 'success', 'Paid'
        FAILED = 'failed', 'Failed'

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name='payment'
    )

    phone = models.CharField(max_length=15)
    amount = models.PositiveIntegerField(help_text='Whole shillings, as sent to Daraja')

    # Daraja's two handles on the transaction. CheckoutRequestID is the one the
    # callback arrives with, so it is the lookup key and must be unique.
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, unique=True)

    mpesa_receipt = models.CharField(max_length=50, blank=True)
    result_code = models.CharField(max_length=10, blank=True)
    result_desc = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    # The untouched callback body, stored before parsing so a malformed or
    # unexpected payload is still debuggable after the fact.
    raw_callback = models.JSONField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        indexes = [models.Index(fields=['checkout_request_id'])]

    def __str__(self):
        return f'M-Pesa {self.status} for order #{self.order_id}'
