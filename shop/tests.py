from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from .management.commands.seed import COLOURS, PRODUCTS, SIZES
from .models import Category, Colour, Product, Size


@override_settings(ALLOWED_HOSTS=['testserver'])
class ProductListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.shirts = Category.objects.create(name='Shirts')
        cls.bags = Category.objects.create(name='Bags')

        cls.small = Size.objects.create(name='S', position=1)
        cls.large = Size.objects.create(name='L', position=2)
        cls.black = Colour.objects.create(name='Black', hex_value='#000000')
        cls.navy = Colour.objects.create(name='Navy', hex_value='#20315f')

        cls.tee = Product.objects.create(
            category=cls.shirts, name='Black Tee', price=Decimal('2000'), stock=5
        )
        cls.tee.sizes.set([cls.small, cls.large])
        cls.tee.colours.set([cls.black])

        cls.polo = Product.objects.create(
            category=cls.shirts, name='Navy Polo', price=Decimal('3000'), stock=5
        )
        cls.polo.sizes.set([cls.large])
        cls.polo.colours.set([cls.navy])

        cls.duffel = Product.objects.create(
            category=cls.bags, name='Canvas Duffel', price=Decimal('9000'), stock=5
        )
        cls.duffel.colours.set([cls.navy])

        cls.hidden = Product.objects.create(
            category=cls.bags, name='Retired Bag', price=Decimal('100'),
            stock=5, is_active=False,
        )

    def names(self, response):
        return {p.name for p in response.context['products']}

    def test_only_active_products_are_listed(self):
        response = self.client.get(reverse('shop:product_list'))
        self.assertNotIn('Retired Bag', self.names(response))
        self.assertEqual(len(response.context['products']), 3)

    def test_filtering_by_size(self):
        response = self.client.get(reverse('shop:product_list'), {'size': 's'})
        self.assertEqual(self.names(response), {'Black Tee'})

    def test_filtering_by_colour(self):
        response = self.client.get(reverse('shop:product_list'), {'colour': 'navy'})
        self.assertEqual(self.names(response), {'Navy Polo', 'Canvas Duffel'})

    def test_size_and_colour_combine(self):
        response = self.client.get(
            reverse('shop:product_list'), {'size': 'l', 'colour': 'navy'}
        )
        self.assertEqual(self.names(response), {'Navy Polo'})

    def test_unknown_facet_slug_returns_nothing_rather_than_everything(self):
        """A stale bookmark must not silently widen the results."""
        response = self.client.get(reverse('shop:product_list'), {'size': 'nope'})
        self.assertEqual(len(response.context['products']), 0)
        self.assertEqual(response.status_code, 200)

    def test_facets_only_offer_values_a_live_product_carries(self):
        orphan = Size.objects.create(name='XXL', position=9)
        orphan.products.set([self.hidden])

        response = self.client.get(reverse('shop:product_list'))
        offered = {link['option'].name for link in response.context['size_links']}
        self.assertNotIn('XXL', offered)
        self.assertEqual(offered, {'S', 'L'})

    def test_active_facet_link_toggles_itself_off(self):
        response = self.client.get(reverse('shop:product_list'), {'size': 's'})
        link = next(
            l for l in response.context['size_links'] if l['option'] == self.small
        )
        self.assertTrue(link['active'])
        self.assertNotIn('size=s', link['query'])

    def test_facet_link_preserves_other_filters_and_drops_the_page(self):
        response = self.client.get(
            reverse('shop:product_list'), {'colour': 'navy', 'page': '2'}
        )
        link = next(
            l for l in response.context['size_links'] if l['option'] == self.large
        )
        self.assertIn('colour=navy', link['query'])
        self.assertIn('size=l', link['query'])
        self.assertNotIn('page', link['query'])

    def test_search_matches_name(self):
        response = self.client.get(reverse('shop:product_list'), {'q': 'duffel'})
        self.assertEqual(self.names(response), {'Canvas Duffel'})

    def test_price_bounds_apply_independently(self):
        response = self.client.get(
            reverse('shop:product_list'), {'max_price': '2500'}
        )
        self.assertEqual(self.names(response), {'Black Tee'})

    def test_non_numeric_price_is_ignored_rather_than_500ing(self):
        response = self.client.get(
            reverse('shop:product_list'), {'min_price': 'abc'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['products']), 3)

    def test_category_counts_exclude_inactive_products(self):
        response = self.client.get(reverse('shop:product_list'))
        counts = {c.name: c.product_count for c in response.context['categories']}
        self.assertEqual(counts['Bags'], 1)      # Retired Bag not counted
        self.assertEqual(counts['Shirts'], 2)


@override_settings(ALLOWED_HOSTS=['testserver'])
class ProductDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Shirts')
        cls.product = Product.objects.create(
            category=cls.category, name='Black Tee', price=Decimal('2000'), stock=5
        )
        cls.hidden = Product.objects.create(
            category=cls.category, name='Retired Tee', price=Decimal('100'),
            stock=5, is_active=False,
        )

    def test_detail_page_renders(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Black Tee')

    def test_inactive_product_is_not_reachable(self):
        response = self.client.get(self.hidden.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_related_products_exclude_the_product_itself(self):
        Product.objects.create(
            category=self.category, name='Other Tee', price=Decimal('1000'), stock=1
        )
        response = self.client.get(self.product.get_absolute_url())
        related = {p.name for p in response.context['related_products']}
        self.assertNotIn('Black Tee', related)
        self.assertIn('Other Tee', related)


class SlugTests(TestCase):
    def test_slug_is_derived_from_the_name_when_blank(self):
        category = Category.objects.create(name='Shirts')
        product = Product.objects.create(
            category=category, name='Navy Tipped Polo Shirt', price=Decimal('1')
        )
        self.assertEqual(product.slug, 'navy-tipped-polo-shirt')

    def test_in_stock_tracks_the_stock_count(self):
        category = Category.objects.create(name='Shirts')
        product = Product.objects.create(
            category=category, name='Tee', price=Decimal('1'), stock=0
        )
        self.assertFalse(product.in_stock)
        product.stock = 1
        self.assertTrue(product.in_stock)


class SeedDataTests(TestCase):
    """Guards on the seed table itself.

    Every product in the shop was once mislabelled because names were paired
    to photos by list position while the files were read in lexicographic
    order. These assert the pairing stays explicit and one-to-one.
    """

    def test_every_product_names_a_photo_that_exists(self):
        img_dir = Path(settings.BASE_DIR) / 'static' / 'img' / 'product'
        missing = [
            spec['image'] for spec in PRODUCTS
            if not (img_dir / spec['image']).exists()
        ]
        self.assertEqual(missing, [])

    def test_no_two_products_share_a_photo(self):
        images = [spec['image'] for spec in PRODUCTS]
        duplicates = {i for i in images if images.count(i) > 1}
        self.assertEqual(duplicates, set())

    def test_product_names_are_unique(self):
        names = [spec['name'] for spec in PRODUCTS]
        duplicates = {n for n in names if names.count(n) > 1}
        self.assertEqual(duplicates, set())

    def test_every_product_has_its_own_description(self):
        bodies = [spec['description'] for spec in PRODUCTS]
        self.assertEqual(len(set(bodies)), len(bodies))

    def test_facet_values_referenced_by_products_are_defined(self):
        known_sizes = {name for name, _ in SIZES}
        known_colours = {name for name, _ in COLOURS}
        for spec in PRODUCTS:
            self.assertLessEqual(set(spec.get('sizes', [])), known_sizes, spec['name'])
            self.assertLessEqual(
                set(spec.get('colours', [])), known_colours, spec['name']
            )

    def test_gallery_shots_exist_on_disk(self):
        img_root = Path(settings.BASE_DIR) / 'static' / 'img'
        for spec in PRODUCTS:
            for rel_path, _alt in spec.get('gallery', []):
                self.assertTrue(
                    (img_root / rel_path).exists(), f'{spec["name"]}: {rel_path}'
                )
