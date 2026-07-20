import json
from decimal import Decimal

from django.test import TestCase, override_settings

from catalog.models import Category, Product
from orders.models import Order, OrderItem

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
