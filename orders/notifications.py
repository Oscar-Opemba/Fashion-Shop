"""Emails the shop sends about an order.

There is exactly one right now — the receipt when M-Pesa confirms a payment —
but it lives in its own module rather than inside the payments view, because
the payment path is the one place in this codebase that must not grow side
effects that can fail. `send_mail` reaches out over the network; a shop that
stops recording a paid order because a mail server timed out would be much
worse than one that occasionally misses a receipt.

So everything here swallows its own errors and logs. The order is already
saved by the time any of it runs.

Under the default settings EMAIL_BACKEND is the console backend, so in
development the receipt prints to the runserver output instead of being sent.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_receipt(order):
    """Email the shopper their receipt. Returns True if it was handed off.

    Silent no-op when the order carries no email address — checkout marks that
    field optional, because an M-Pesa shopper is reachable on their phone and
    forcing an address to buy a t-shirt loses sales.
    """
    if not order.email:
        return False

    context = {
        'order': order,
        'items': order.items.select_related('product'),
        'site_name': getattr(settings, 'SITE_NAME', 'Fashion Shop'),
    }

    try:
        send_mail(
            subject=f'Your order #{order.pk} is confirmed',
            message=render_to_string('orders/email/receipt.txt', context),
            html_message=render_to_string('orders/email/receipt.html', context),
            from_email=None,  # DEFAULT_FROM_EMAIL
            recipient_list=[order.email],
            fail_silently=False,
        )
    except Exception:
        # Bad address, refused relay, DNS, timeout — none of which should
        # unwind a payment that has already been confirmed and banked.
        logger.exception('Could not send the receipt for order %s', order.pk)
        return False

    logger.info('Receipt for order %s sent to %s', order.pk, order.email)
    return True
