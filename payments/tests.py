import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from shop.models import Category, Product
from orders.models import Coupon, Order, OrderItem

from .daraja import normalise_phone
from .models import MpesaPayment

CALLBACK_TOKEN = 'test-token'


class PhoneNormalisationTests(TestCase):
    def test_accepts_the_formats_people_actually_type(self):
        for raw in ('0712345678', '+254712345678', '254712345678',
                    '712345678', '0712 345 678'):
            with self.subTest(raw=raw):
                self.assertEqual(normalise_phone(raw), '254712345678')

    def test_accepts_the_011x_range(self):
        self.assertEqual(normalise_phone('0112345678'), '254112345678')

    def test_rejects_anything_that_is_not_a_kenyan_mobile(self):
        for raw in ('07123', '0812345678', 'abc', '', None):
            with self.subTest(raw=raw):
                self.assertIsNone(normalise_phone(raw))


@override_settings(ALLOWED_HOSTS=['testserver'], MPESA_CALLBACK_TOKEN=CALLBACK_TOKEN)
class CallbackTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            category=category, name='Test Shirt', price=Decimal('1500.00'), stock=10
        )
        self.order = Order.objects.create(
            full_name='Buyer', phone='254712345678',
            county='Nairobi', town='T', street='S',
        )
        OrderItem.objects.create(
            order=self.order, product=self.product,
            price=self.product.price, quantity=2,
        )
        self.payment = MpesaPayment.objects.create(
            order=self.order, phone=self.order.phone,
            amount=self.order.get_mpesa_amount(),
            checkout_request_id='ws_CO_TEST',
        )

    def post_callback(self, result_code=0, checkout_id='ws_CO_TEST'):
        body = {'Body': {'stkCallback': {
            'MerchantRequestID': '1-2',
            'CheckoutRequestID': checkout_id,
            'ResultCode': result_code,
            'ResultDesc': 'ok' if result_code == 0 else 'Request cancelled by user',
        }}}
        if result_code == 0:
            body['Body']['stkCallback']['CallbackMetadata'] = {'Item': [
                {'Name': 'Amount', 'Value': 3000},
                {'Name': 'MpesaReceiptNumber', 'Value': 'SFG4TESTXY'},
            ]}
        return self.client.post(
            f'/payments/callback/{CALLBACK_TOKEN}/',
            data=json.dumps(body), content_type='application/json',
        )

    def test_successful_callback_marks_paid_and_takes_stock(self):
        self.post_callback()

        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(self.order.paid)
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(self.order.payment.mpesa_receipt, 'SFG4TESTXY')

    def test_replayed_callback_does_not_decrement_stock_twice(self):
        """Safaricom retries until it gets a zero ResultCode, so the handler
        has to be safe to run repeatedly."""
        self.post_callback()
        self.post_callback()
        self.post_callback()

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_failed_callback_leaves_the_order_alone(self):
        self.post_callback(result_code=1032)

        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertFalse(self.order.paid)
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(self.order.payment.status, MpesaPayment.Status.FAILED)

    def test_callback_always_acknowledges_so_safaricom_stops_retrying(self):
        for response in (self.post_callback(),
                         self.post_callback(checkout_id='unknown-id')):
            self.assertEqual(response.json()['ResultCode'], 0)

    def test_wrong_token_is_not_found(self):
        response = self.client.post(
            '/payments/callback/wrong-token/',
            data='{}', content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_malformed_body_is_acknowledged_not_crashed(self):
        response = self.client.post(
            f'/payments/callback/{CALLBACK_TOKEN}/',
            data='not json', content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)


@override_settings(ALLOWED_HOSTS=['testserver'], MPESA_CALLBACK_TOKEN=CALLBACK_TOKEN)
class CouponRedemptionTests(TestCase):
    """A coupon use is counted when an order is paid, exactly once."""

    def setUp(self):
        now = timezone.now()
        category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            category=category, name='Test Shirt', price=Decimal('1500.00'), stock=10
        )
        self.coupon = Coupon.objects.create(
            code='SAVE10', discount_percent=10, max_uses=1,
            valid_from=now - timedelta(days=1), valid_to=now + timedelta(days=1),
        )
        self.order = Order.objects.create(
            full_name='Buyer', phone='254712345678',
            county='Nairobi', town='T', street='S',
            coupon=self.coupon, discount_percent=10,
            discount_amount=Decimal('300.00'),
        )
        OrderItem.objects.create(
            order=self.order, product=self.product,
            price=self.product.price, quantity=2,
        )
        MpesaPayment.objects.create(
            order=self.order, phone=self.order.phone,
            amount=self.order.get_mpesa_amount(), checkout_request_id='ws_CO_C',
        )

    def post_callback(self):
        body = {'Body': {'stkCallback': {
            'MerchantRequestID': '1-2', 'CheckoutRequestID': 'ws_CO_C',
            'ResultCode': 0, 'ResultDesc': 'ok',
            'CallbackMetadata': {'Item': [
                {'Name': 'MpesaReceiptNumber', 'Value': 'SFG4TESTXY'},
            ]},
        }}}
        return self.client.post(
            f'/payments/callback/{CALLBACK_TOKEN}/',
            data=json.dumps(body), content_type='application/json',
        )

    def test_paying_counts_one_redemption(self):
        self.post_callback()
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.times_used, 1)
        self.assertFalse(self.coupon.is_valid)   # spent

    def test_replayed_callback_counts_the_redemption_once(self):
        self.post_callback()
        self.post_callback()
        self.post_callback()
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.times_used, 1)

    def test_a_failed_payment_does_not_burn_a_use(self):
        body = {'Body': {'stkCallback': {
            'MerchantRequestID': '1-2', 'CheckoutRequestID': 'ws_CO_C',
            'ResultCode': 1032, 'ResultDesc': 'Request cancelled by user',
        }}}
        self.client.post(
            f'/payments/callback/{CALLBACK_TOKEN}/',
            data=json.dumps(body), content_type='application/json',
        )
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.times_used, 0)


@override_settings(ALLOWED_HOSTS=['testserver'])
class GuestOrderAccessTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            category=category, name='Test Shirt', price=Decimal('1500.00'), stock=10
        )

    def checkout(self, client, name='Guest'):
        client.post(f'/cart/add/{self.product.id}/', {'quantity': 1})
        response = client.post('/orders/checkout/', {
            'full_name': name, 'phone': '0722000111',
            'county': 'Nairobi', 'town': 'T', 'street': 'S',
        })
        order_id = int(response['Location'].rstrip('/').split('/')[-1])
        MpesaPayment.objects.create(
            order=Order.objects.get(pk=order_id), phone='254722000111',
            amount=1500, checkout_request_id=f'ws_{order_id}',
        )
        return order_id

    def test_guest_can_reach_their_own_order(self):
        order_id = self.checkout(self.client)
        self.assertEqual(
            self.client.get(f'/payments/waiting/{order_id}/').status_code, 200
        )

    def test_another_guest_cannot_reach_it(self):
        order_id = self.checkout(self.client)

        other = self.client_class()
        self.assertEqual(
            other.get(f'/payments/waiting/{order_id}/').status_code, 404
        )

    def test_visiting_start_does_not_let_a_stranger_claim_the_order(self):
        """Regression: ownership used to be claimed in the payment start view,
        so walking order ids handed out other buyers' delivery details."""
        order_id = self.checkout(self.client)

        attacker = self.client_class()
        attacker.get(f'/payments/start/{order_id}/')
        self.assertEqual(
            attacker.get(f'/payments/waiting/{order_id}/').status_code, 404
        )

    def test_status_poll_returns_json_when_daraja_is_unconfigured(self):
        """Regression: an unconfigured Daraja raised out of the status view,
        so the waiting page polled a 500 instead of being told to keep
        waiting."""
        order_id = self.checkout(self.client)

        response = self.client.get(f'/payments/status/{order_id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['paid'], False)
        self.assertIsNone(response.json()['redirect'])

    def test_a_guest_can_place_more_than_one_order(self):
        first = self.checkout(self.client, 'First')
        second = self.checkout(self.client, 'Second')

        self.assertNotEqual(first, second)
        for order_id in (first, second):
            with self.subTest(order_id=order_id):
                self.assertEqual(
                    self.client.get(f'/payments/waiting/{order_id}/').status_code, 200
                )


@override_settings(ALLOWED_HOSTS=['testserver'])
class OutcomePageRenderTests(TestCase):
    """Every payment outcome page must actually render.

    Regression: success.html reversed a 'catalog:' url that no app declares,
    so the page a paying customer lands on raised NoReverseMatch. Nothing
    caught it because the sandbox cannot complete a payment without a human
    entering a PIN, so this template was never rendered in a test or by hand.
    """

    def setUp(self):
        category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            category=category, name='Test Shirt', price=Decimal('1500.00'), stock=10
        )

    def order_at(self, status, paid):
        self.client.post(f'/cart/add/{self.product.id}/', {'quantity': 1})
        response = self.client.post('/orders/checkout/', {
            'full_name': 'Guest', 'phone': '0722000111',
            'county': 'Nairobi', 'town': 'T', 'street': 'S',
        })
        order_id = int(response['Location'].rstrip('/').split('/')[-1])

        order = Order.objects.get(pk=order_id)
        order.paid = paid
        order.save(update_fields=['paid'])

        MpesaPayment.objects.create(
            order=order, phone='254722000111', amount=1500,
            checkout_request_id=f'ws_{order_id}', status=status,
            mpesa_receipt='TEST12345' if paid else '',
        )
        return order_id

    def test_success_page_renders_for_a_paid_order(self):
        order_id = self.order_at('success', paid=True)
        self.assertEqual(
            self.client.get(f'/payments/success/{order_id}/').status_code, 200
        )

    def test_failed_page_renders(self):
        order_id = self.order_at('failed', paid=False)
        self.assertEqual(
            self.client.get(f'/payments/failed/{order_id}/').status_code, 200
        )


@override_settings(ALLOWED_HOSTS=['testserver'])
class PaymentRetryTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            category=category, name='Test Shirt', price=Decimal('1500.00'), stock=10,
        )

    def place_order(self):
        self.client.post(f'/cart/add/{self.product.id}/', {'quantity': 1})
        response = self.client.post('/orders/checkout/', {
            'full_name': 'Guest', 'phone': '0722000111',
            'county': 'Nairobi', 'town': 'T', 'street': 'S',
        })
        return int(response['Location'].rstrip('/').split('/')[-1])

    def test_retrying_a_payment_reuses_the_row_instead_of_crashing(self):
        """Regression: start() keyed update_or_create on CheckoutRequestID, but
        order is OneToOne. A retry gets a fresh CheckoutRequestID, so the lookup
        missed and it tried to INSERT a second payment for the same order —
        `UNIQUE constraint failed: payments_mpesapayment.order_id` (a 500)."""
        order_id = self.place_order()

        # First attempt lands, then fails (user cancels, or a non-zero callback).
        with patch('payments.views.stk_push', return_value={
            'CheckoutRequestID': 'ws_CO_FIRST', 'MerchantRequestID': 'm-1',
        }):
            self.client.get(f'/payments/start/{order_id}/')
        MpesaPayment.objects.filter(order_id=order_id).update(
            status=MpesaPayment.Status.FAILED,
            result_code='1032', result_desc='Request cancelled by user',
        )

        # Retry: a fresh CheckoutRequestID must UPDATE the same row, not insert.
        with patch('payments.views.stk_push', return_value={
            'CheckoutRequestID': 'ws_CO_SECOND', 'MerchantRequestID': 'm-2',
        }):
            response = self.client.get(f'/payments/start/{order_id}/')

        self.assertEqual(response.status_code, 302)
        payments = MpesaPayment.objects.filter(order_id=order_id)
        self.assertEqual(payments.count(), 1)

        payment = payments.get()
        self.assertEqual(payment.checkout_request_id, 'ws_CO_SECOND')
        # Stale result of the failed attempt is cleared back to a clean PENDING.
        self.assertEqual(payment.status, MpesaPayment.Status.PENDING)
        self.assertEqual(payment.result_code, '')
        self.assertEqual(payment.result_desc, '')


@override_settings(ALLOWED_HOSTS=['testserver'])
class StatusPollTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            category=category, name='Test Shirt', price=Decimal('1500.00'), stock=10,
        )

    def place_pending_order(self):
        self.client.post(f'/cart/add/{self.product.id}/', {'quantity': 1})
        response = self.client.post('/orders/checkout/', {
            'full_name': 'Guest', 'phone': '0704018188',
            'county': 'Nairobi', 'town': 'T', 'street': 'S',
        })
        order_id = int(response['Location'].rstrip('/').split('/')[-1])
        MpesaPayment.objects.create(
            order=Order.objects.get(pk=order_id), phone='254704018188',
            amount=1500, checkout_request_id='ws_CO_POLL',
            status=MpesaPayment.Status.PENDING,
        )
        return order_id

    def poll(self, order_id):
        return self.client.get(f'/payments/status/{order_id}/')

    def test_transient_query_code_does_not_fail_the_order(self):
        """Regression: a real KES 1 payment succeeded, but the status poll saw
        Daraja's transient query code 4999 and marked the order failed before
        the authoritative callback (ResultCode 0) could land."""
        order_id = self.place_pending_order()

        with patch('payments.views.query_stk_status',
                   return_value={'ResultCode': '4999', 'ResultDesc': 'still processing'}):
            data = self.poll(order_id).json()

        self.assertEqual(data['paid'], False)
        self.assertIsNone(data['redirect'])  # keep waiting, do not send to /failed/
        self.assertEqual(
            MpesaPayment.objects.get(order_id=order_id).status,
            MpesaPayment.Status.PENDING,
        )

    def test_genuine_terminal_code_still_fails_the_order(self):
        """A real terminal outcome — 1032, the user cancelling — must still fail
        the order rather than spin forever."""
        order_id = self.place_pending_order()

        with patch('payments.views.query_stk_status',
                   return_value={'ResultCode': '1032', 'ResultDesc': 'Cancelled by user'}):
            data = self.poll(order_id).json()

        self.assertEqual(data['paid'], False)
        self.assertTrue(data['redirect'].endswith(f'/payments/failed/{order_id}/'))
        self.assertEqual(
            MpesaPayment.objects.get(order_id=order_id).status,
            MpesaPayment.Status.FAILED,
        )

    def test_success_code_marks_paid(self):
        order_id = self.place_pending_order()

        with patch('payments.views.query_stk_status',
                   return_value={'ResultCode': '0', 'ResultDesc': 'ok'}):
            data = self.poll(order_id).json()

        self.assertEqual(data['paid'], True)
        self.assertTrue(data['redirect'].endswith(f'/payments/success/{order_id}/'))
