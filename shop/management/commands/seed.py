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

PRODUCTS = [
    ('Jackets', 'Pique Biker Jacket', 6750),
    ('Jackets', 'Bomber Jacket', 8200),
    ('Jackets', 'Quilted Puffer Coat', 11500),
    ('Jackets', 'Denim Trucker Jacket', 5400),
    ('Shirts', 'Oxford Button-Down Shirt', 2950),
    ('Shirts', 'Linen Summer Shirt', 3400),
    ('Shirts', 'Flannel Check Shirt', 3100),
    ('Shirts', 'Slim Fit Poplin Shirt', 2750),
    ('Bags', 'Multi-pocket Chest Bag', 4300),
    ('Bags', 'Canvas Weekend Duffel', 7900),
    ('Bags', 'Leather Laptop Satchel', 9600),
    ('Bags', 'Everyday Backpack', 5200),
    ('Shoes', 'Retro Court Sneakers', 6800),
    ('Shoes', 'Chelsea Ankle Boots', 10400),
    ('Shoes', 'Canvas Low Tops', 3600),
    ('Shoes', 'Suede Desert Boots', 8900),
    ('Accessories', 'Minimal Field Watch', 12500),
    ('Accessories', 'Woven Leather Belt', 2400),
    ('Accessories', 'Wool Beanie', 1500),
    ('Accessories', 'Polarised Sunglasses', 4100),
]

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
        images = sorted(image_dir.glob('*.jpg'))
        if not images:
            self.stdout.write(self.style.WARNING(
                f'No theme images found in {image_dir}; products will have no photos.'
            ))

        categories = {}
        for index, (name, _) in enumerate(CATEGORIES):
            category, created = Category.objects.get_or_create(name=name)
            # Give each category a distinct tile image, otherwise the home page
            # shows the same fallback photo three times over.
            if images and needs_image(category.image):
                source = images[(index * 3) % len(images)]
                with source.open('rb') as fh:
                    category.image.save(f'category-{source.name}', File(fh), save=True)
            categories[name] = category
        self.stdout.write(f'Categories: {len(categories)}')

        created = 0
        repaired = 0
        for index, (category_name, name, price) in enumerate(PRODUCTS):
            existing = Product.objects.filter(name=name).first()
            if existing is not None:
                # Already seeded, but the photo may have gone missing with
                # media/. Re-attach it rather than skipping the row entirely.
                if images and needs_image(existing.image):
                    source = images[index % len(images)]
                    with source.open('rb') as fh:
                        existing.image.save(source.name, File(fh), save=True)
                    repaired += 1
                continue

            product = Product(
                category=categories[category_name],
                name=name,
                price=price,
                # A couple of out-of-stock items make that path visible.
                stock=0 if index % 9 == 4 else random.randint(3, 40),
                description=DESCRIPTION,
            )

            if images:
                source = images[index % len(images)]
                with source.open('rb') as fh:
                    product.image.save(source.name, File(fh), save=False)

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
