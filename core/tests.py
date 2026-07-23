from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from shop.models import Category, Product


@override_settings(ALLOWED_HOSTS=['testserver'])
class HomePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Shirts')
        cls.cheap = Product.objects.create(
            category=cls.category, name='Cheap Tee', price=Decimal('500'), stock=5
        )
        cls.dear = Product.objects.create(
            category=cls.category, name='Dear Coat', price=Decimal('9000'), stock=5
        )
        cls.hidden = Product.objects.create(
            category=cls.category, name='Retired Tee', price=Decimal('1'),
            stock=5, is_active=False,
        )

    def test_home_page_renders(self):
        self.assertEqual(self.client.get(reverse('core:home')).status_code, 200)

    def test_featured_products_exclude_inactive_ones(self):
        response = self.client.get(reverse('core:home'))
        names = {p.name for p in response.context['featured_products']}
        self.assertNotIn('Retired Tee', names)

    def test_deal_of_the_week_is_the_cheapest_product_in_stock(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.context['deal_product'], self.cheap)

    def test_deal_of_the_week_skips_sold_out_products(self):
        self.cheap.stock = 0
        self.cheap.save()
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.context['deal_product'], self.dear)

    def test_deal_of_the_week_copes_with_an_empty_shop(self):
        Product.objects.all().delete()
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['deal_product'])


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class ContactFormTests(TestCase):
    def test_static_pages_render(self):
        for name in ['core:about', 'core:contact']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_a_valid_message_is_sent_and_redirects(self):
        response = self.client.post(reverse('core:contact'), {
            'name': 'Wanjiku', 'email': 'w@example.com', 'message': 'Hello',
        })
        self.assertRedirects(response, reverse('core:contact'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Wanjiku', mail.outbox[0].subject)

    def test_an_invalid_message_is_not_sent(self):
        response = self.client.post(reverse('core:contact'), {
            'name': '', 'email': 'not-an-email', 'message': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
