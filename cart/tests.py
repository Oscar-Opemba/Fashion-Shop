from decimal import Decimal

from django.test import TestCase, override_settings

from shop.models import Category, Product


@override_settings(ALLOWED_HOSTS=['testserver'])
class CartTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Shirts')
        self.product = Product.objects.create(
            category=self.category, name='Test Shirt', price=Decimal('1500.00'), stock=10
        )

    def add_one(self):
        return self.client.post(f'/cart/add/{self.product.id}/', {'quantity': 1})

    def test_iterating_the_cart_leaves_the_session_json_serialisable(self):
        """Regression: a shallow copy in Cart.__iter__ wrote Decimals into the
        session, and the session is serialised as JSON — every checkout 500ed
        on save."""
        self.add_one()
        self.client.get('/cart/')          # iterates the cart
        self.client.get('/')               # forces another session save

        stored = self.client.session['cart'][str(self.product.id)]
        self.assertIsInstance(stored['price'], str)

    def test_quantity_is_capped_at_available_stock(self):
        self.client.post(f'/cart/add/{self.product.id}/', {'quantity': 99})
        self.assertEqual(
            self.client.session['cart'][str(self.product.id)]['quantity'], 10
        )

    def test_totals_use_the_price_captured_at_add_time(self):
        self.add_one()
        self.product.price = Decimal('9999.00')
        self.product.save()

        response = self.client.get('/cart/')
        self.assertContains(response, '1500.00')
        self.assertNotContains(response, '9999.00')

    def test_out_of_stock_product_cannot_be_added(self):
        self.product.stock = 0
        self.product.save()
        self.add_one()
        self.assertNotIn(str(self.product.id), self.client.session.get('cart', {}))
