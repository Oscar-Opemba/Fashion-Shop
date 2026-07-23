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
