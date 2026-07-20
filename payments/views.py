import json
import logging

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from cart.cart import Cart
from catalog.models import Product
from orders.models import Order

from .daraja import DarajaError, query_stk_status, stk_push
from .models import MpesaPayment

logger = logging.getLogger(__name__)

# Safaricom's reply is fixed: anything other than a zero ResultCode makes it
# retry the callback, so we always accept and sort out the meaning ourselves.
ACK = {'ResultCode': 0, 'ResultDesc': 'Accepted'}


def _owns_order(request, order):
    """A member's order is tied to the user, a guest's to their session.

    Guest claims are written by the checkout view when the order is created,
    never here — otherwise walking order ids would hand out other people's
    delivery details.
    """
    if order.user_id:
        return request.user.is_authenticated and order.user_id == request.user.id
    return order.pk in request.session.get('guest_orders', [])


def start(request, order_id):
    """Fire the STK push and send the shopper to the waiting page."""
    order = get_object_or_404(Order, pk=order_id)

    if not _owns_order(request, order):
        raise Http404

    if order.paid:
        return redirect('payments:success', order_id=order.pk)

    try:
        response = stk_push(
            phone=order.phone,
            amount=order.get_mpesa_amount(),
            account_reference=f'ORDER{order.pk}',
            description=f'Order {order.pk}',
        )
    except DarajaError as exc:
        logger.error('STK push failed for order %s: %s', order.pk, exc)
        messages.error(request, f'Could not reach M-Pesa: {exc}')
        return redirect('payments:failed', order_id=order.pk)

    payment, _ = MpesaPayment.objects.update_or_create(
        checkout_request_id=response['CheckoutRequestID'],
        defaults={
            'order': order,
            'phone': order.phone,
            'amount': order.get_mpesa_amount(),
            'merchant_request_id': response.get('MerchantRequestID', ''),
            'status': MpesaPayment.Status.PENDING,
        },
    )

    return redirect('payments:waiting', order_id=order.pk)


def waiting(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not _owns_order(request, order):
        raise Http404

    return render(request, 'payments/waiting.html', {
        'order': order,
        'payment': getattr(order, 'payment', None),
    })


def status(request, order_id):
    """Polled by the waiting page every few seconds."""
    order = get_object_or_404(Order, pk=order_id)
    if not _owns_order(request, order):
        raise Http404

    payment = getattr(order, 'payment', None)

    # If the callback has not landed, ask Daraja directly. Tunnels drop,
    # callbacks get lost, and the shopper should not be stuck watching a
    # spinner because of it.
    if payment and payment.status == MpesaPayment.Status.PENDING:
        result = query_stk_status(payment.checkout_request_id)
        code = str(result.get('ResultCode', '')) if result else ''

        # While the prompt is still on the handset Daraja answers with
        # errorCode 500.001.1001 and no ResultCode. Only a ResultCode is a
        # verdict; anything else means keep waiting.
        if code:
            if code == '0':
                _mark_paid(payment, receipt='', result_desc=result.get('ResultDesc', ''))
            else:
                # Every non-zero code is terminal (1032 is the user cancelling).
                _mark_failed(payment, code, result.get('ResultDesc', ''))
            payment.refresh_from_db()
            order.refresh_from_db()

    return JsonResponse({
        'paid': order.paid,
        'status': payment.status if payment else 'pending',
        'message': payment.result_desc if payment else '',
        'redirect': (
            _url('payments:success', order.pk) if order.paid
            else _url('payments:failed', order.pk)
            if payment and payment.status == MpesaPayment.Status.FAILED
            else None
        ),
    })


def _url(name, order_id):
    from django.urls import reverse
    return reverse(name, args=[order_id])


@transaction.atomic
def _mark_paid(payment, receipt, result_desc=''):
    """Confirm a payment and take the stock. Safe to call more than once."""
    payment = MpesaPayment.objects.select_for_update().get(pk=payment.pk)
    order = Order.objects.select_for_update().get(pk=payment.order_id)

    if order.paid and order.stock_applied:
        return

    payment.status = MpesaPayment.Status.SUCCESS
    payment.result_code = '0'
    if receipt:
        payment.mpesa_receipt = receipt
    if result_desc:
        payment.result_desc = result_desc
    payment.save()

    order.paid = True
    order.status = Order.Status.PAID

    # stock_applied is the guard that makes a replayed callback harmless.
    if not order.stock_applied:
        for item in order.items.select_related('product'):
            product = Product.objects.select_for_update().get(pk=item.product_id)
            product.stock = max(0, product.stock - item.quantity)
            product.save(update_fields=['stock'])
        order.stock_applied = True

    order.save()


def _mark_failed(payment, code, desc):
    payment.status = MpesaPayment.Status.FAILED
    payment.result_code = str(code)
    payment.result_desc = desc or 'Payment was not completed.'
    payment.save()


@csrf_exempt
@require_POST
def callback(request, token):
    """Safaricom posts the payment result here.

    Unauthenticated by design on their side, so the defences are: an
    unguessable url, lookup strictly by CheckoutRequestID, and idempotency.
    """
    if token != settings.MPESA_CALLBACK_TOKEN:
        logger.warning('M-Pesa callback hit with a bad token')
        raise Http404

    try:
        body = json.loads(request.body.decode() or '{}')
    except (ValueError, UnicodeDecodeError):
        logger.error('Un-parseable M-Pesa callback: %r', request.body[:500])
        return JsonResponse(ACK)

    stk = body.get('Body', {}).get('stkCallback', {})
    checkout_request_id = stk.get('CheckoutRequestID')

    if not checkout_request_id:
        logger.error('M-Pesa callback with no CheckoutRequestID: %s', body)
        return JsonResponse(ACK)

    # Look the payment up by Daraja's id only. Nothing in the body that
    # identifies an order is trusted.
    payment = MpesaPayment.objects.filter(
        checkout_request_id=checkout_request_id
    ).first()

    if payment is None:
        logger.warning('M-Pesa callback for unknown request %s', checkout_request_id)
        return JsonResponse(ACK)

    # Store the raw body before interpreting any of it.
    payment.raw_callback = body
    payment.save(update_fields=['raw_callback'])

    if payment.status == MpesaPayment.Status.SUCCESS:
        # Already settled; Safaricom is retrying. Nothing to do.
        return JsonResponse(ACK)

    result_code = str(stk.get('ResultCode', ''))
    result_desc = stk.get('ResultDesc', '')

    if result_code == '0':
        receipt = ''
        for entry in stk.get('CallbackMetadata', {}).get('Item', []):
            if entry.get('Name') == 'MpesaReceiptNumber':
                receipt = str(entry.get('Value', ''))
                break
        _mark_paid(payment, receipt=receipt, result_desc=result_desc)
        logger.info('Order %s paid, receipt %s', payment.order_id, receipt)
    else:
        _mark_failed(payment, result_code, result_desc)
        logger.info(
            'Order %s payment failed (%s): %s',
            payment.order_id, result_code, result_desc,
        )

    return JsonResponse(ACK)


def success(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not _owns_order(request, order):
        raise Http404

    # The cart has served its purpose once the order is paid for.
    if order.paid:
        Cart(request).clear()
        request.session.pop('coupon_id', None)

    return render(request, 'payments/success.html', {
        'order': order,
        'payment': getattr(order, 'payment', None),
    })


def failed(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not _owns_order(request, order):
        raise Http404

    return render(request, 'payments/failed.html', {
        'order': order,
        'payment': getattr(order, 'payment', None),
    })


@require_POST
def retry(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not _owns_order(request, order):
        raise Http404
    return redirect('payments:start', order_id=order.pk)
