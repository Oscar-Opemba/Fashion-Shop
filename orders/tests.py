from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from shop.models import Category, Product

from .forms import OrderCreateForm
from .models import Coupon, Order, OrderItem

User = get_user_model()

DETAILS = {
    'full_name': 'Wanjiku Kamau',
    'phone': '0712345678',
    'email': 'wanjiku@example.com',
    'county': 'Nairobi',
    'town': 'Westlands',
    'street': '12 Rhapta Road',
}


@override_settings(ALLOWED_HOSTS=['testserver'])
class CheckoutTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            category=self.category, name='Tee', price=Decimal('1500.00'), stock=10
        )

    def add_to_cart(self, quantity=2):
        self.client.post(f'/cart/add/{self.product.id}/', {'quantity': quantity})

    def test_empty_cart_is_bounced_to_the_shop(self):
        response = self.client.get(reverse('orders:checkout'))
        self.assertRedirects(response, reverse('shop:product_list'))

    def test_checkout_creates_the_order_and_its_lines(self):
        self.add_to_cart()
        self.client.post(reverse('orders:checkout'), DETAILS)

        order = Order.objects.get()
        self.assertEqual(order.full_name, 'Wanjiku Kamau')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 2)

    def test_line_price_is_captured_not_re_read_from_the_product(self):
        self.add_to_cart(quantity=1)
        self.client.post(reverse('orders:checkout'), DETAILS)

        self.product.price = Decimal('9999.00')
        self.product.save()

        self.assertEqual(OrderItem.objects.get().price, Decimal('1500.00'))

    def test_stock_is_not_taken_until_payment_confirms(self):
        """An abandoned STK prompt must not hold inventory."""
        self.add_to_cart(quantity=3)
        self.client.post(reverse('orders:checkout'), DETAILS)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertFalse(Order.objects.get().stock_applied)

    def test_checkout_hands_off_to_the_payment_flow(self):
        self.add_to_cart()
        response = self.client.post(reverse('orders:checkout'), DETAILS)

        order = Order.objects.get()
        self.assertRedirects(
            response,
            reverse('payments:start', args=[order.pk]),
            fetch_redirect_response=False,
        )

    def test_cart_survives_checkout_so_a_failed_payment_can_be_retried(self):
        self.add_to_cart()
        self.client.post(reverse('orders:checkout'), DETAILS)
        self.assertIn(str(self.product.id), self.client.session.get('cart', {}))

    def test_guest_order_is_claimed_in_the_session(self):
        self.add_to_cart()
        self.client.post(reverse('orders:checkout'), DETAILS)

        order = Order.objects.get()
        self.assertIn(order.pk, self.client.session['guest_orders'])
        self.assertIsNone(order.user_id)

    def test_signed_in_order_is_attached_to_the_user(self):
        user = User.objects.create_user('wanjiku', password='sekret123')
        self.client.force_login(user)
        self.add_to_cart()
        self.client.post(reverse('orders:checkout'), DETAILS)

        self.assertEqual(Order.objects.get().user, user)

    def test_a_cart_over_stock_is_sent_back_to_the_cart(self):
        self.add_to_cart(quantity=5)
        self.product.stock = 1
        self.product.save()

        response = self.client.get(reverse('orders:checkout'))
        self.assertRedirects(response, reverse('cart:detail'))


class OrderTotalsTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            category=category, name='Tee', price=Decimal('1000.00'), stock=10
        )
        self.order = Order.objects.create(**DETAILS)
        OrderItem.objects.create(
            order=self.order, product=self.product,
            price=Decimal('1000.00'), quantity=3,
        )

    def test_subtotal_sums_the_lines(self):
        self.assertEqual(self.order.get_subtotal(), Decimal('3000.00'))

    def test_discount_is_zero_without_a_coupon(self):
        self.assertEqual(self.order.get_discount(), Decimal('0'))
        self.assertEqual(self.order.get_total(), Decimal('3000.00'))

    def test_discount_applies_a_percentage(self):
        self.order.discount_percent = 10
        self.assertEqual(self.order.get_discount(), Decimal('300.00'))
        self.assertEqual(self.order.get_total(), Decimal('2700.00'))

    def test_mpesa_amount_rounds_up_to_whole_shillings(self):
        """Daraja rejects decimals, and rounding down would undercharge."""
        self.order.discount_percent = 33      # 3000 - 990 = 2010.00
        self.assertEqual(self.order.get_mpesa_amount(), 2010)

        self.order.items.update(price=Decimal('333.33'))   # 999.99 -> 1000
        self.order.discount_percent = 0
        self.assertEqual(self.order.get_mpesa_amount(), 1000)

    def test_mpesa_amount_is_never_below_one(self):
        self.order.items.update(price=Decimal('0'))
        self.assertEqual(self.order.get_mpesa_amount(), 1)


class CouponTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.coupon = Coupon.objects.create(
            code='SAVE10', discount_percent=10,
            valid_from=now - timedelta(days=1), valid_to=now + timedelta(days=1),
        )

    def test_a_current_coupon_is_valid(self):
        self.assertTrue(self.coupon.is_valid)

    def test_an_expired_coupon_is_not_valid(self):
        self.coupon.valid_to = timezone.now() - timedelta(hours=1)
        self.assertFalse(self.coupon.is_valid)

    def test_a_deactivated_coupon_is_not_valid(self):
        self.coupon.active = False
        self.assertFalse(self.coupon.is_valid)

    def test_a_used_up_coupon_is_not_valid(self):
        self.coupon.max_uses = 2
        self.coupon.times_used = 2
        self.assertFalse(self.coupon.is_valid)
        self.coupon.times_used = 1
        self.assertTrue(self.coupon.is_valid)


class CouponScopeTests(TestCase):
    """A coupon can discount the whole cart or only certain categories."""

    def setUp(self):
        now = timezone.now()
        self.shirts = Category.objects.create(name='Shirts')
        self.shoes = Category.objects.create(name='Shoes')
        self.shirt = Product.objects.create(
            category=self.shirts, name='Tee', price=Decimal('1000.00'), stock=10
        )
        self.shoe = Product.objects.create(
            category=self.shoes, name='Sneaker', price=Decimal('2000.00'), stock=10
        )
        self.coupon = Coupon.objects.create(
            code='SAVE20', discount_percent=20,
            valid_from=now - timedelta(days=1), valid_to=now + timedelta(days=1),
        )
        # (product, line_cost) pairs, the shape discount_for expects.
        self.lines = [
            (self.shirt, Decimal('1000.00')),
            (self.shoe, Decimal('2000.00')),
        ]

    def test_no_categories_discounts_the_whole_cart(self):
        # 20% of 3000 = 600
        self.assertEqual(self.coupon.discount_for(self.lines), Decimal('600.00'))

    def test_scoped_coupon_discounts_only_qualifying_lines(self):
        self.coupon.categories.add(self.shoes)
        # 20% of the 2000 shoe line only = 400; the shirt is untouched.
        self.assertEqual(self.coupon.discount_for(self.lines), Decimal('400.00'))

    def test_scoped_coupon_with_no_match_gives_zero(self):
        empty = Category.objects.create(name='Hats')
        self.coupon.categories.add(empty)
        self.assertEqual(self.coupon.discount_for(self.lines), Decimal('0.00'))

    def test_frozen_amount_is_used_over_the_percentage(self):
        order = Order.objects.create(
            **DETAILS, discount_percent=20, discount_amount=Decimal('400.00')
        )
        OrderItem.objects.create(
            order=order, product=self.shirt,
            price=Decimal('1000.00'), quantity=3,
        )
        # Percentage would say 600 off 3000; the frozen amount wins.
        self.assertEqual(order.get_discount(), Decimal('400.00'))


class PhoneCleaningTests(TestCase):
    """Kenyan numbers get typed every which way; all of them must normalise."""

    def cleaned(self, phone):
        form = OrderCreateForm(data={**DETAILS, 'phone': phone})
        self.assertTrue(form.is_valid(), form.errors)
        return form.cleaned_data['phone']

    def test_accepted_shapes_all_normalise_to_the_local_form(self):
        for raw in ['0712345678', '+254712345678', '254712345678', '712345678',
                    '0712 345 678', '0712-345-678']:
            with self.subTest(raw=raw):
                self.assertEqual(self.cleaned(raw), '0712345678')

    def test_the_011_range_is_accepted(self):
        self.assertEqual(self.cleaned('0110000000'), '0110000000')

    def test_rubbish_is_rejected(self):
        for raw in ['12345', 'not a phone', '0812345678', '07123456789']:
            with self.subTest(raw=raw):
                form = OrderCreateForm(data={**DETAILS, 'phone': raw})
                self.assertFalse(form.is_valid(), raw)


@override_settings(ALLOWED_HOSTS=['testserver'])
class OrderAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', password='sekret123')
        self.other = User.objects.create_user('other', password='sekret123')
        self.order = Order.objects.create(user=self.owner, **DETAILS)

    def test_history_requires_signing_in(self):
        response = self.client.get(reverse('orders:history'))
        self.assertEqual(response.status_code, 302)

    def test_owner_sees_their_order(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('orders:detail', args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)

    def test_another_user_cannot_read_the_order(self):
        """Delivery name, phone and address hang off this page."""
        self.client.force_login(self.other)
        response = self.client.get(reverse('orders:detail', args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_history_only_lists_your_own_orders(self):
        Order.objects.create(user=self.other, **DETAILS)
        self.client.force_login(self.owner)
        response = self.client.get(reverse('orders:history'))
        self.assertEqual(list(response.context['orders']), [self.order])


@override_settings(ALLOWED_HOSTS=['testserver'])
class OrderTimelineTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Bags')
        self.product = Product.objects.create(
            category=self.category, name='Tote', price=Decimal('6500'), stock=5
        )
        self.order = Order.objects.create(**DETAILS)
        OrderItem.objects.create(
            order=self.order, product=self.product, price=Decimal('6500'), quantity=2
        )

    def test_record_status_writes_an_event(self):
        event = self.order.record_status(Order.Status.PAID, 'Paid up')

        self.assertIsNotNone(event)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.order.events.count(), 1)
        self.assertEqual(event.note, 'Paid up')

    def test_recording_the_same_status_twice_is_a_no_op(self):
        self.order.record_status(Order.Status.PAID)
        second = self.order.record_status(Order.Status.PAID)

        self.assertIsNone(second)
        self.assertEqual(self.order.events.count(), 1)

    def test_the_timeline_has_a_step_for_every_stage(self):
        steps = self.order.timeline()
        self.assertEqual(len(steps), len(Order.TIMELINE))
        self.assertEqual(steps[0]['label'], 'Order placed')
        self.assertEqual(steps[-1]['label'], 'Delivered')

    def test_earlier_stages_are_marked_done(self):
        self.order.record_status(Order.Status.SHIPPED)

        steps = {step['status']: step for step in self.order.timeline()}
        self.assertTrue(steps[Order.Status.PENDING]['done'])
        self.assertTrue(steps[Order.Status.PAID]['done'])
        self.assertTrue(steps[Order.Status.SHIPPED]['current'])
        self.assertFalse(steps[Order.Status.DELIVERED]['done'])

    def test_a_recorded_stage_carries_its_timestamp(self):
        self.order.record_status(Order.Status.PAID)

        paid = next(s for s in self.order.timeline() if s['status'] == Order.Status.PAID)
        self.assertIsNotNone(paid['at'])

    def test_a_cancelled_order_reports_itself(self):
        self.order.record_status(Order.Status.CANCELLED)
        self.assertTrue(self.order.is_cancelled)
        # Nothing is "current" once the order has left the sequence.
        self.assertFalse(any(step['current'] for step in self.order.timeline()))


class PhoneMatchingTests(TestCase):
    def setUp(self):
        self.order = Order.objects.create(**{**DETAILS, 'phone': '0712345678'})

    def test_the_same_number_in_any_common_shape_matches(self):
        for shape in ['0712345678', '+254712345678', '254712345678', '712345678']:
            with self.subTest(shape=shape):
                self.assertTrue(self.order.matches_phone(shape))

    def test_a_different_number_does_not_match(self):
        self.assertFalse(self.order.matches_phone('0787654321'))

    def test_an_empty_phone_does_not_match(self):
        self.assertFalse(self.order.matches_phone(''))


@override_settings(ALLOWED_HOSTS=['testserver'])
class OrderTrackingTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Bags')
        self.product = Product.objects.create(
            category=self.category, name='Tote', price=Decimal('6500'), stock=5
        )
        self.order = Order.objects.create(**DETAILS)
        OrderItem.objects.create(
            order=self.order, product=self.product, price=Decimal('6500'), quantity=2
        )
        self.order.record_status(Order.Status.PENDING, 'Order placed.')

    def track(self, **params):
        return self.client.get(reverse('orders:track'), params)

    def api(self, **params):
        return self.client.get(reverse('orders:track_api'), params)

    def test_the_bare_page_just_shows_the_form(self):
        response = self.client.get(reverse('orders:track'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['order'])
        self.assertFalse(response.context['searched'])

    def test_the_right_pair_finds_the_order(self):
        response = self.track(order_number=self.order.pk, phone=DETAILS['phone'])
        self.assertEqual(response.context['order'], self.order)
        self.assertContains(response, 'Order placed')

    def test_a_wrong_phone_finds_nothing(self):
        response = self.track(order_number=self.order.pk, phone='0787654321')
        self.assertIsNone(response.context['order'])

    def test_an_unknown_order_number_finds_nothing(self):
        response = self.track(order_number=999999, phone=DETAILS['phone'])
        self.assertIsNone(response.context['order'])

    def test_the_page_never_leaks_the_delivery_address(self):
        """The lookup pair is a phone number, not a password, so what it opens
        is limited to progress."""
        response = self.track(order_number=self.order.pk, phone=DETAILS['phone'])
        self.assertNotContains(response, DETAILS['street'])
        self.assertNotContains(response, DETAILS['email'])

    def test_the_api_returns_the_timeline(self):
        response = self.api(order_number=self.order.pk, phone=DETAILS['phone'])
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data['found'])
        self.assertEqual(data['order_number'], self.order.pk)
        self.assertEqual(data['status'], Order.Status.PENDING)
        self.assertEqual(data['item_count'], 2)
        self.assertEqual(len(data['timeline']), len(Order.TIMELINE))

    def test_the_api_404s_on_a_wrong_phone(self):
        response = self.api(order_number=self.order.pk, phone='0787654321')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['found'])

    def test_the_api_400s_on_a_malformed_request(self):
        response = self.api(order_number='abc', phone='nope')
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json())

    def test_the_api_never_returns_the_address(self):
        response = self.api(order_number=self.order.pk, phone=DETAILS['phone'])
        body = response.content.decode()
        self.assertNotIn(DETAILS['street'], body)
        self.assertNotIn(DETAILS['email'], body)
        self.assertNotIn(DETAILS['full_name'], body)


@override_settings(ALLOWED_HOSTS=['testserver'])
class ReceiptEmailTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Bags')
        self.product = Product.objects.create(
            category=self.category, name='Tote', price=Decimal('6500'), stock=5
        )
        self.order = Order.objects.create(**DETAILS)
        OrderItem.objects.create(
            order=self.order, product=self.product, price=Decimal('6500'), quantity=2
        )

    def test_the_receipt_is_sent_and_names_the_order(self):
        from django.core import mail

        from .notifications import send_receipt

        self.assertTrue(send_receipt(self.order))
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]
        self.assertEqual(message.to, [DETAILS['email']])
        self.assertIn(str(self.order.pk), message.subject)
        self.assertIn('Tote', message.body)
        self.assertIn('13000.00', message.body)  # 2 x 6500

    def test_an_order_without_an_email_sends_nothing(self):
        from django.core import mail

        from .notifications import send_receipt

        self.order.email = ''
        self.order.save()

        self.assertFalse(send_receipt(self.order))
        self.assertEqual(len(mail.outbox), 0)

    def test_a_broken_mail_server_does_not_raise(self):
        """The receipt must never be able to unwind a confirmed payment."""
        from unittest.mock import patch

        from .notifications import send_receipt

        with patch('orders.notifications.send_mail', side_effect=OSError('no relay')):
            self.assertFalse(send_receipt(self.order))


class EmailConfigurationTests(TestCase):
    """The contract between .env and how mail actually goes out.

    Settings are read once at import, so these assert the resolved values and
    the behaviour that hangs off them rather than re-importing the module.
    """

    def test_the_send_is_bounded_by_a_timeout(self):
        """Django defaults to no timeout at all. `send_receipt` runs on the
        M-Pesa callback path, so an unresponsive mail server must not be able
        to hold that request open indefinitely."""
        from django.conf import settings

        self.assertIsNotNone(settings.EMAIL_TIMEOUT)
        self.assertLessEqual(settings.EMAIL_TIMEOUT, 30)

    def test_credentials_decide_the_backend(self):
        """Absent credentials mean console, present ones mean SMTP. This is the
        rule that lets a fresh clone run with no mail server."""
        from django.core.mail import get_connection

        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
        ):
            self.assertIn('console', get_connection().__class__.__module__)

        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
        ):
            self.assertIn('smtp', get_connection().__class__.__module__)

    def test_the_receipt_uses_the_configured_sender(self):
        from django.core import mail

        from .notifications import send_receipt

        category = Category.objects.create(name='Bags')
        product = Product.objects.create(
            category=category, name='Tote', price=Decimal('6500'), stock=5
        )
        order = Order.objects.create(**DETAILS)
        OrderItem.objects.create(
            order=order, product=product, price=Decimal('6500'), quantity=1
        )

        with self.settings(DEFAULT_FROM_EMAIL='Shop <shop@example.com>'):
            send_receipt(order)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, 'Shop <shop@example.com>')

    def test_mailcheck_reports_the_console_backend_without_sending(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        with self.settings(
            EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
        ):
            call_command('mailcheck', stdout=out)

        self.assertIn('nothing will be sent', out.getvalue())
