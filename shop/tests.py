import tempfile
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .imaging import MAX_SIDE
from .management.commands.seed import COLOURS, PRODUCTS, SIZES
from .models import Category, Colour, Product, Review, Size, WishlistItem

# Imported to prove the PROTECT on OrderItem.product surfaces as a message.
from orders.models import Order, OrderItem


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


@override_settings(ALLOWED_HOSTS=['testserver'])
class ProductCrudTests(TestCase):
    """The staff-only Create/Update/Delete views in shop/views.py."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user(
            'keeper', 'keeper@example.com', 'pw', is_staff=True
        )
        cls.shopper = User.objects.create_user(
            'shopper', 'shopper@example.com', 'pw'
        )
        cls.category = Category.objects.create(name='Jackets')
        cls.product = Product.objects.create(
            category=cls.category, name='Denim Jacket',
            price=Decimal('4500'), stock=3,
        )

    def form_data(self, **overrides):
        data = {
            'name': 'Leather Jacket',
            'slug': '',
            'description': 'Full grain.',
            'price': '9000',
            'category': self.category.pk,
            'sizes': [],
            'colours': [],
            'stock': '2',
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    # -- access -------------------------------------------------------------

    def test_anonymous_is_sent_to_login(self):
        for name, kwargs in (
            ('shop:manage_list', {}),
            ('shop:product_create', {}),
            ('shop:product_update', {'slug': self.product.slug}),
            ('shop:product_delete', {'slug': self.product.slug}),
        ):
            response = self.client.get(reverse(name, kwargs=kwargs))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn('/accounts/login/', response.url, name)

    def test_signed_in_shopper_is_forbidden(self):
        self.client.force_login(self.shopper)
        response = self.client.get(reverse('shop:product_create'))
        self.assertEqual(response.status_code, 403)

    def test_shopper_cannot_delete_by_posting(self):
        self.client.force_login(self.shopper)
        response = self.client.post(
            reverse('shop:product_delete', kwargs={'slug': self.product.slug})
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    # -- read ---------------------------------------------------------------

    def test_manage_list_shows_inactive_products(self):
        hidden = Product.objects.create(
            category=self.category, name='Retired Parka',
            price=Decimal('7000'), stock=0, is_active=False,
        )
        self.client.force_login(self.staff)
        response = self.client.get(reverse('shop:manage_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, hidden.name)
        # ...unlike the public listing.
        self.assertNotContains(
            self.client.get(reverse('shop:product_list')), hidden.name
        )

    def test_every_staff_page_renders(self):
        self.client.force_login(self.staff)
        for name, kwargs in (
            ('shop:manage_list', {}),
            ('shop:product_create', {}),
            ('shop:product_update', {'slug': self.product.slug}),
            ('shop:product_delete', {'slug': self.product.slug}),
            ('shop:category_create', {}),
            ('shop:category_update', {'slug': self.category.slug}),
            ('shop:category_delete', {'slug': self.category.slug}),
        ):
            with self.subTest(view=name):
                response = self.client.get(reverse(name, kwargs=kwargs))
                self.assertEqual(response.status_code, 200)

    # -- create -------------------------------------------------------------

    def test_staff_can_create_a_product(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('shop:product_create'), self.form_data(), follow=True
        )
        self.assertEqual(response.status_code, 200)
        created = Product.objects.get(name='Leather Jacket')
        self.assertEqual(created.slug, 'leather-jacket')
        self.assertEqual(created.price, Decimal('9000'))

    def test_duplicate_slug_is_a_form_error_not_a_crash(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('shop:product_create'), self.form_data(name='Denim Jacket')
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'], 'slug',
            'Product with this Slug already exists.',
        )
        self.assertEqual(Product.objects.filter(name='Denim Jacket').count(), 1)

    # -- update -------------------------------------------------------------

    def test_staff_can_update_a_product(self):
        self.client.force_login(self.staff)
        self.client.post(
            reverse('shop:product_update', kwargs={'slug': self.product.slug}),
            self.form_data(name='Denim Jacket', slug=self.product.slug, stock='11'),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 11)

    # -- delete -------------------------------------------------------------

    def test_staff_can_delete_an_unsold_product(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('shop:product_delete', kwargs={'slug': self.product.slug}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_deleting_a_sold_product_is_refused_not_a_500(self):
        order = Order.objects.create(
            full_name='Wanjiru', phone='0712345678', email='w@example.com',
            county='Nairobi', town='Nairobi', street='Ngong Rd',
        )
        OrderItem.objects.create(
            order=order, product=self.product, price=self.product.price, quantity=1
        )

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('shop:product_delete', kwargs={'slug': self.product.slug}),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertContains(response, 'appears in an order')

    def test_deleting_a_category_with_products_is_refused(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse('shop:category_delete', kwargs={'slug': self.category.slug}),
            follow=True,
        )
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assertContains(response, 'still holds products')

    def test_staff_can_delete_an_empty_category(self):
        empty = Category.objects.create(name='Hats')
        self.client.force_login(self.staff)
        self.client.post(
            reverse('shop:category_delete', kwargs={'slug': empty.slug}), follow=True
        )
        self.assertFalse(Category.objects.filter(pk=empty.pk).exists())


@override_settings(ALLOWED_HOSTS=['testserver'])
class ReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Bags')
        cls.product = Product.objects.create(
            category=cls.category, name='Tote', price=Decimal('6500'), stock=5
        )
        cls.amina = User.objects.create_user('amina', password='pw')
        cls.brian = User.objects.create_user('brian', password='pw')

    def post_review(self, rating=5, body='Great'):
        return self.client.post(
            self.product.get_absolute_url(), {'rating': rating, 'body': body}
        )

    def test_a_new_product_has_no_rating(self):
        self.assertEqual(self.product.rating_count, 0)
        self.assertEqual(self.product.rating_average, Decimal('0'))
        self.assertEqual(self.product.stars, [False] * 5)

    def test_posting_a_review_updates_the_cached_rating(self):
        self.client.force_login(self.amina)
        self.post_review(rating=4)

        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_count, 1)
        self.assertEqual(self.product.rating_average, Decimal('4.00'))
        self.assertEqual(self.product.stars, [True, True, True, True, False])

    def test_the_average_is_the_mean_of_every_review(self):
        Review.objects.create(product=self.product, user=self.amina, rating=5)
        Review.objects.create(product=self.product, user=self.brian, rating=2)

        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_average, Decimal('3.50'))
        self.assertEqual(self.product.rating_count, 2)

    def test_deleting_a_review_recalculates_the_rating(self):
        first = Review.objects.create(product=self.product, user=self.amina, rating=5)
        Review.objects.create(product=self.product, user=self.brian, rating=1)
        first.delete()

        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_average, Decimal('1.00'))
        self.assertEqual(self.product.rating_count, 1)

    def test_deleting_the_last_review_returns_the_rating_to_zero(self):
        review = Review.objects.create(product=self.product, user=self.amina, rating=5)
        review.delete()

        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_count, 0)
        self.assertEqual(self.product.rating_average, Decimal('0'))

    def test_posting_twice_edits_the_first_review_rather_than_adding_one(self):
        self.client.force_login(self.amina)
        self.post_review(rating=5, body='First impression')
        self.post_review(rating=2, body='Changed my mind')

        self.assertEqual(Review.objects.filter(product=self.product).count(), 1)
        review = Review.objects.get(product=self.product)
        self.assertEqual(review.rating, 2)
        self.assertEqual(review.body, 'Changed my mind')

        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_average, Decimal('2.00'))

    def test_anonymous_visitors_are_sent_to_sign_in(self):
        response = self.post_review()
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.assertFalse(Review.objects.exists())

    def test_a_rating_outside_one_to_five_is_rejected(self):
        self.client.force_login(self.amina)
        response = self.post_review(rating=9)
        self.assertEqual(response.status_code, 200)  # re-rendered, not redirected
        self.assertFalse(Review.objects.exists())

    def test_a_review_without_a_purchase_is_not_marked_verified(self):
        self.client.force_login(self.amina)
        self.post_review()
        self.assertFalse(Review.objects.get().is_verified_purchase)

    def test_a_review_after_a_paid_order_is_marked_verified(self):
        order = Order.objects.create(
            user=self.amina, full_name='Amina', phone='0712345678',
            county='Nairobi', town='Nairobi', street='Moi Ave', paid=True,
        )
        OrderItem.objects.create(
            order=order, product=self.product, price=self.product.price, quantity=1
        )

        self.client.force_login(self.amina)
        self.post_review()
        self.assertTrue(Review.objects.get().is_verified_purchase)

    def test_an_unpaid_order_does_not_earn_the_badge(self):
        order = Order.objects.create(
            user=self.amina, full_name='Amina', phone='0712345678',
            county='Nairobi', town='Nairobi', street='Moi Ave', paid=False,
        )
        OrderItem.objects.create(
            order=order, product=self.product, price=self.product.price, quantity=1
        )

        self.client.force_login(self.amina)
        self.post_review()
        self.assertFalse(Review.objects.get().is_verified_purchase)

    def test_a_bulk_delete_still_recalculates(self):
        """queryset.delete() never calls Review.delete(), so this proves the
        post_delete signal is what keeps the cached rating honest."""
        Review.objects.create(product=self.product, user=self.amina, rating=5)
        Review.objects.create(product=self.product, user=self.brian, rating=5)

        Review.objects.filter(product=self.product).delete()

        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_count, 0)
        self.assertEqual(self.product.rating_average, Decimal('0'))

    def test_deleting_the_author_recalculates(self):
        """Same again for the cascade when an account is removed."""
        Review.objects.create(product=self.product, user=self.amina, rating=5)
        Review.objects.create(product=self.product, user=self.brian, rating=1)

        self.brian.delete()

        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_count, 1)
        self.assertEqual(self.product.rating_average, Decimal('5.00'))

    def test_the_detail_page_lists_reviews(self):
        Review.objects.create(
            product=self.product, user=self.amina, rating=5, body='Roomy and solid'
        )
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, 'Roomy and solid')
        self.assertContains(response, 'Reviews (1)')

    def test_sorting_by_rating_puts_the_best_first(self):
        poor = Product.objects.create(
            category=self.category, name='Poor', price=Decimal('100'), stock=1
        )
        Review.objects.create(product=self.product, user=self.amina, rating=5)
        Review.objects.create(product=poor, user=self.amina, rating=1)

        response = self.client.get(reverse('shop:product_list'), {'sort': 'rating'})
        names = [p.name for p in response.context['products']]
        self.assertLess(names.index('Tote'), names.index('Poor'))


@override_settings(ALLOWED_HOSTS=['testserver'])
class WishlistTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Bags')
        cls.product = Product.objects.create(
            category=cls.category, name='Tote', price=Decimal('6500'), stock=5
        )
        cls.amina = User.objects.create_user('amina', password='pw')

    def toggle(self, **extra):
        return self.client.post(
            reverse('shop:wishlist_toggle', args=[self.product.pk]), **extra
        )

    def test_saving_then_saving_again_removes_it(self):
        self.client.force_login(self.amina)

        self.toggle()
        self.assertTrue(
            WishlistItem.objects.filter(user=self.amina, product=self.product).exists()
        )

        self.toggle()
        self.assertFalse(
            WishlistItem.objects.filter(user=self.amina, product=self.product).exists()
        )

    def test_the_ajax_toggle_answers_json(self):
        self.client.force_login(self.amina)
        response = self.toggle(headers={'x-requested-with': 'XMLHttpRequest'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'saved': True, 'count': 1, 'label': 'Saved'})

    def test_anonymous_visitors_are_sent_to_sign_in(self):
        response = self.toggle()
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])
        self.assertFalse(WishlistItem.objects.exists())

    def test_the_toggle_refuses_get(self):
        self.client.force_login(self.amina)
        response = self.client.get(
            reverse('shop:wishlist_toggle', args=[self.product.pk])
        )
        self.assertEqual(response.status_code, 405)

    def test_the_saved_page_lists_saved_products(self):
        WishlistItem.objects.create(user=self.amina, product=self.product)
        self.client.force_login(self.amina)

        response = self.client.get(reverse('shop:wishlist'))
        self.assertContains(response, 'Tote')

    def test_the_saved_page_is_private(self):
        response = self.client.get(reverse('shop:wishlist'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_the_empty_saved_page_says_so(self):
        self.client.force_login(self.amina)
        response = self.client.get(reverse('shop:wishlist'))
        self.assertContains(response, 'not saved anything yet')

    def test_one_row_per_user_and_product(self):
        from django.db import IntegrityError, transaction

        WishlistItem.objects.create(user=self.amina, product=self.product)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WishlistItem.objects.create(user=self.amina, product=self.product)


class ImageOptimisationTests(TestCase):
    """The upload-time downscaler in shop/imaging.py."""

    def make_png(self, width, height):
        from io import BytesIO
        from PIL import Image

        buffer = BytesIO()
        Image.new('RGB', (width, height), (180, 120, 90)).save(buffer, format='PNG')
        return SimpleUploadedFile('shot.png', buffer.getvalue(), 'image/png')

    def setUp(self):
        self.category = Category.objects.create(name='Bags')

    def test_an_upload_is_re_encoded_as_webp(self):
        with tempfile.TemporaryDirectory() as media:
            with override_settings(MEDIA_ROOT=media):
                product = Product.objects.create(
                    category=self.category, name='Tote', price=Decimal('1'),
                    image=self.make_png(2000, 2000),
                )
                self.assertTrue(product.image.name.endswith('_opt.webp'))

    def test_an_oversized_upload_is_bounded(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as media:
            with override_settings(MEDIA_ROOT=media):
                product = Product.objects.create(
                    category=self.category, name='Tote', price=Decimal('1'),
                    image=self.make_png(3000, 2000),
                )
                with Image.open(product.image) as img:
                    self.assertLessEqual(max(img.size), MAX_SIDE)

    def test_a_second_save_does_not_re_encode(self):
        with tempfile.TemporaryDirectory() as media:
            with override_settings(MEDIA_ROOT=media):
                product = Product.objects.create(
                    category=self.category, name='Tote', price=Decimal('1'),
                    image=self.make_png(800, 800),
                )
                first = product.image.name

                product.price = Decimal('2')
                product.save()

                # A re-encode would append a second marker, or storage would
                # hand back a suffixed duplicate name.
                self.assertEqual(product.image.name, first)

    def test_a_product_without_an_image_saves_fine(self):
        product = Product.objects.create(
            category=self.category, name='Plain', price=Decimal('1')
        )
        self.assertFalse(product.image)
