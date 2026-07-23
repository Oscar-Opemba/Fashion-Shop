"""Load sample data so the site looks like a real shop on first run.

Product photos are copied out of the theme's own image set, so there is
nothing to download and the styling looks right immediately.
"""

import random
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Profile
from shop.models import Category, Product


def needs_image(field):
    """True when a field has no file, or names one that has gone missing.

    media/ is gitignored, so a clone starts with shop rows pointing at
    photos that were never checked in. Without this the cards render but
    every image 404s, which reads as the products being invisible.
    """
    if not field:
        return True
    try:
        return not field.storage.exists(field.name)
    except (ValueError, OSError):
        return True


CATEGORIES = [
    ('Jackets', 'Outerwear for every season.'),
    ('Shirts', 'Everyday and occasion shirts.'),
    ('Bags', 'Backpacks, totes and travel bags.'),
    ('Shoes', 'Sneakers, boots and formal shoes.'),
    ('Accessories', 'Watches, belts and the small stuff.'),
]

# Each row names the photo it belongs to. The theme ships 14 product shots
# and every name here describes what is actually in that shot — pairing them
# by list position instead silently mislabels the whole shop, because
# sorted() orders the files product-1, product-10, product-11, ... not
# product-1, product-2, product-3.
PRODUCTS = [
    ('Shoes', 'Navy Suede Runner Sneakers', 6800, 'product-1.jpg'),
    ('Jackets', 'Camel Cotton Chore Jacket', 6750, 'product-2.jpg'),
    ('Shoes', 'Navy Leather Low-Top Sneakers', 5400, 'product-3.jpg'),
    ('Jackets', 'Brown Suede Hooded Overshirt', 7900, 'product-4.jpg'),
    ('Shirts', 'Black Graphic Print T-Shirt', 2400, 'product-5.jpg'),
    ('Accessories', 'Grey Wool Fringed Scarf', 2950, 'product-6.jpg'),
    ('Bags', 'Brown Leather Backpack', 9600, 'product-7.jpg'),
    ('Shirts', 'Navy Tipped Polo Shirt', 3100, 'product-8.jpg'),
    ('Shirts', 'Black Floral Print T-Shirt', 2750, 'product-9.jpg'),
    ('Accessories', 'Eau de Parfum Gift Set', 8200, 'product-10.jpg'),
    ('Bags', 'White Travel Backpack', 11500, 'product-11.jpg'),
    ('Jackets', 'Green Camo Hooded Anorak', 8900, 'product-12.jpg'),
    ('Bags', 'Brown Leather Briefcase', 10400, 'product-13.jpg'),
    ('Accessories', 'Gold Rectangular Cufflinks', 4100, 'product-14.jpg'),
    # product-15 to product-20 are squared-off crops of photos the theme
    # ships elsewhere (banners, instagram strip, shop-details hero, sale
    # badge). The original product/ folder only held 14 shots.
    ('Jackets', 'Grey Sleeve Varsity Bomber', 9800, 'product-15.jpg'),
    ('Accessories', 'Round Tortoiseshell Sunglasses', 4100, 'product-16.jpg'),
    ('Shoes', 'Two-Tone Leather Low-Tops', 7200, 'product-17.jpg'),
    ('Bags', 'Olive Canvas Weekend Duffel', 7900, 'product-18.jpg'),
    ('Shirts', 'Camel Crew Sweatshirt', 4600, 'product-19.jpg'),
    ('Bags', 'Rust Drawstring Bucket Bag', 5300, 'product-20.jpg'),
]

# Two rows are seeded empty so the sold-out badge and the disabled add-to-cart
# path are both visible without editing anything by hand.
OUT_OF_STOCK = {'Navy Leather Low-Top Sneakers', 'Brown Leather Briefcase'}

DESCRIPTION = (
    '<p>A well-made everyday piece, cut for a clean fit and built to last '
    'past a single season. Pairs with almost anything already in your '
    'wardrobe.</p><p>Free delivery on orders over KES 5,000.</p>'
)


class Command(BaseCommand):
    help = 'Load sample categories, products and a superuser.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete existing shop data before seeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # Deterministic stock/pricing so repeated runs are comparable.
        random.seed(42)

        if options['flush']:
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write('Cleared existing shop data.')

        image_dir = Path(settings.BASE_DIR) / 'static' / 'img' / 'product'
        images = {path.name: path for path in image_dir.glob('*.jpg')}
        if not images:
            self.stdout.write(self.style.WARNING(
                f'No theme images found in {image_dir}; products will have no photos.'
            ))

        # One representative photo per category, picked from that category's own
        # products so the home page tiles match what they link to.
        CATEGORY_IMAGES = {
            'Jackets': 'product-2.jpg',
            'Shirts': 'product-8.jpg',
            'Bags': 'product-7.jpg',
            'Shoes': 'product-1.jpg',
            'Accessories': 'product-14.jpg',
        }

        categories = {}
        for name, _ in CATEGORIES:
            category, created = Category.objects.get_or_create(name=name)
            source = images.get(CATEGORY_IMAGES[name])
            if source is not None and needs_image(category.image):
                with source.open('rb') as fh:
                    category.image.save(f'category-{source.name}', File(fh), save=True)
            categories[name] = category
        self.stdout.write(f'Categories: {len(categories)}')

        created = 0
        repaired = 0
        for category_name, name, price, image_name in PRODUCTS:
            source = images.get(image_name)

            existing = Product.objects.filter(name=name).first()
            if existing is not None:
                # Already seeded, but the photo may have gone missing with
                # media/. Re-attach it rather than skipping the row entirely.
                if source is not None and needs_image(existing.image):
                    with source.open('rb') as fh:
                        existing.image.save(image_name, File(fh), save=True)
                    repaired += 1
                continue

            product = Product(
                category=categories[category_name],
                name=name,
                price=price,
                stock=0 if name in OUT_OF_STOCK else random.randint(3, 40),
                description=DESCRIPTION,
            )

            if source is not None:
                with source.open('rb') as fh:
                    product.image.save(image_name, File(fh), save=False)

            product.save()
            created += 1

        self.stdout.write(f'Products created: {created}')
        if repaired:
            self.stdout.write(f'Product photos restored: {repaired}')

        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin', email='admin@example.com', password='admin12345'
            )
            self.stdout.write(self.style.WARNING(
                'Superuser created — admin@example.com / admin12345. '
                'Change this password before deploying anywhere.'
            ))

        # Users made before the Profile signal existed have no profile row.
        backfilled = 0
        for user in User.objects.filter(profile__isnull=True):
            Profile.objects.create(user=user)
            backfilled += 1
        if backfilled:
            self.stdout.write(f'Profiles backfilled: {backfilled}')

        self.stdout.write(self.style.SUCCESS('Seed complete.'))
