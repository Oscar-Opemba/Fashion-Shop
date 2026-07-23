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
from shop.models import Category, Colour, Product, ProductImage, Size


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

# Ordered smallest to largest; the sidebar reads in this order.
SIZES = [
    ('XS', 1), ('S', 2), ('M', 3), ('L', 4),
    ('XL', 5), ('XXL', 6), ('3XL', 7), ('4XL', 8),
]

# The first nine match the theme's own .c-1 to .c-9 swatches; the rest were
# added for products the theme's palette does not cover.
COLOURS = [
    ('Black', '#0b090c'),
    ('Navy', '#20315f'),
    ('Grey', '#636068'),
    ('Olive', '#57594d'),
    ('White', '#ffffff'),
    ('Gold', '#f1af4d'),
    ('Camel', '#c19a6b'),
    ('Brown', '#6b4b2f'),
    ('Tan', '#a9714b'),
    ('Rust', '#b5532a'),
]

APPAREL = ['S', 'M', 'L', 'XL', 'XXL']
FULL_RANGE = ['XS', 'S', 'M', 'L', 'XL', 'XXL', '3XL', '4XL']

DELIVERY_NOTE = '<p>Free delivery on orders over KES 5,000.</p>'


def body(*paragraphs):
    return ''.join(f'<p>{p}</p>' for p in paragraphs) + DELIVERY_NOTE


# Each row names the photo it belongs to. The theme ships 14 product shots
# and every name here describes what is actually in that shot — pairing them
# by list position instead silently mislabels the whole shop, because
# sorted() orders the files product-1, product-10, product-11, ... not
# product-1, product-2, product-3.
#
# `sizes` is empty for anything not worn on the body. Shoes are left empty
# too: they need a numeric run, and XS-4XL would be nonsense on a sneaker.
PRODUCTS = [
    {
        'category': 'Shoes', 'name': 'Navy Suede Runner Sneakers',
        'price': 6800, 'image': 'product-1.jpg',
        'colours': ['Navy', 'Tan'],
        'description': body(
            'A low-profile runner in navy suede and mesh, with a tan saddle '
            'over the midfoot and a gum outsole that keeps its grip on wet '
            'pavement.',
            'Padded collar and a cushioned insole you can lift out and swap.',
        ),
    },
    {
        'category': 'Jackets', 'name': 'Camel Cotton Chore Jacket',
        'price': 6750, 'image': 'product-2.jpg',
        'sizes': APPAREL, 'colours': ['Camel'],
        'description': body(
            'Cut from heavy camel cotton twill in the shape of a French work '
            'jacket — boxy through the body, square at the hem, with three '
            'patch pockets you will actually use.',
            'Soft enough to wear straight off the rail, and it only looks '
            'better once the twill starts to fade at the elbows.',
        ),
    },
    {
        'category': 'Shoes', 'name': 'Navy Leather Low-Top Sneakers',
        'price': 5400, 'image': 'product-3.jpg',
        'colours': ['Navy', 'White'],
        'description': body(
            'A clean navy leather low-top on a white cupsole. No branding to '
            'speak of, which is the point.',
            'Wipes clean with a damp cloth, so it survives a Nairobi commute.',
        ),
    },
    {
        'category': 'Jackets', 'name': 'Brown Suede Hooded Overshirt',
        'price': 7900, 'image': 'product-4.jpg',
        'sizes': ['S', 'M', 'L', 'XL'], 'colours': ['Brown'],
        'description': body(
            'Half shirt, half jacket: brushed brown suede with a soft hood, a '
            'chest pocket and a press-stud placket.',
            'The layer for when a jacket is too much and a shirt is not '
            'enough — which in Nairobi is most evenings.',
        ),
    },
    {
        'category': 'Shirts', 'name': 'Black Graphic Print T-Shirt',
        'price': 2400, 'image': 'product-5.jpg',
        'sizes': FULL_RANGE, 'colours': ['Black'],
        'description': body(
            'A relaxed black tee in mid-weight cotton, with a spare line '
            'graphic printed across the chest.',
            'Pre-shrunk, so the fit you buy is the fit you keep.',
        ),
    },
    {
        'category': 'Accessories', 'name': 'Grey Wool Fringed Scarf',
        'price': 2950, 'image': 'product-6.jpg',
        'colours': ['Grey'],
        'description': body(
            'A generously sized wool scarf in marled grey, finished with a '
            'hand-knotted fringe.',
            'Warm without the bulk, and long enough to loop twice.',
        ),
    },
    {
        'category': 'Bags', 'name': 'Brown Leather Backpack',
        'price': 9600, 'image': 'product-7.jpg',
        'colours': ['Brown'],
        'description': body(
            'A full-grain leather backpack with a zip main compartment, a '
            'padded sleeve for a 15" laptop and a slim external pocket.',
            'Unlined shoulder straps that soften and shape to you with wear.',
        ),
    },
    {
        'category': 'Shirts', 'name': 'Navy Tipped Polo Shirt',
        'price': 3100, 'image': 'product-8.jpg',
        'sizes': APPAREL, 'colours': ['Navy', 'White'],
        'description': body(
            'A navy piqué polo with a stand collar and white tipping at the '
            'collar and cuffs.',
            'Smart enough for the office, plain enough for the weekend.',
        ),
    },
    {
        'category': 'Shirts', 'name': 'Black Floral Print T-Shirt',
        'price': 2750, 'image': 'product-9.jpg',
        'sizes': ['XS', 'S', 'M', 'L', 'XL'], 'colours': ['Black'],
        'description': body(
            'Black cotton jersey with a floral print running over one '
            'shoulder and down the sleeve.',
            'The print is screen-printed rather than transferred, so it will '
            'not crack or peel in the wash.',
        ),
    },
    {
        'category': 'Accessories', 'name': 'Eau de Parfum Gift Set',
        'price': 8200, 'image': 'product-10.jpg',
        'description': body(
            'Three 50ml eau de parfum bottles in a boxed set — one citrus, '
            'one woody, one clean and soapy.',
            'Comes gift-boxed, so it needs no wrapping.',
        ),
    },
    {
        'category': 'Bags', 'name': 'White Travel Backpack',
        'price': 11500, 'image': 'product-11.jpg',
        'colours': ['White'],
        'description': body(
            'A structured cabin-sized backpack in coated white canvas, with a '
            'clamshell opening and compression zips down each side.',
            'Water-resistant coating and a luggage strap on the back panel.',
        ),
    },
    {
        'category': 'Jackets', 'name': 'Green Camo Hooded Anorak',
        'price': 8900, 'image': 'product-12.jpg',
        'sizes': ['M', 'L', 'XL', 'XXL', '3XL'], 'colours': ['Olive'],
        'description': body(
            'A half-zip anorak in a washed green camo, with a drawcord hem, '
            'an adjustable hood and a deep kangaroo pocket.',
            'Light enough to pack down into its own pocket.',
        ),
    },
    {
        'category': 'Bags', 'name': 'Brown Leather Briefcase',
        'price': 10400, 'image': 'product-13.jpg',
        'colours': ['Brown'],
        'description': body(
            'A slim leather briefcase with twin rolled handles, a full-width '
            'zip pocket on the front and a padded laptop compartment inside.',
            'Includes a detachable shoulder strap.',
        ),
    },
    {
        'category': 'Accessories', 'name': 'Gold Rectangular Cufflinks',
        'price': 4100, 'image': 'product-14.jpg',
        'colours': ['Gold'],
        'description': body(
            'Brushed gold-tone cufflinks with a softly rounded rectangular '
            'face and a smooth swivel bar.',
            'Supplied in a small presentation box.',
        ),
    },
    # product-15 to product-20 are squared-off crops of photos the theme
    # ships elsewhere (banners, instagram strip, shop-details hero, sale
    # badge). The original product/ folder only held 14 shots.
    {
        'category': 'Jackets', 'name': 'Grey Sleeve Varsity Bomber',
        'price': 9800, 'image': 'product-15.jpg',
        'sizes': APPAREL, 'colours': ['Black', 'Grey'],
        'description': body(
            'A varsity-cut bomber with a black body and contrast grey melton '
            'sleeves, ribbed at the collar, cuffs and hem.',
            'Zip front with two slash pockets, fully lined.',
        ),
    },
    {
        'category': 'Accessories', 'name': 'Round Tortoiseshell Sunglasses',
        'price': 4100, 'image': 'product-16.jpg',
        'colours': ['Tan', 'Gold'],
        'description': body(
            'Round acetate frames in a warm tortoiseshell, set on slim gold '
            'metal arms with gradient amber lenses.',
            'Full UV400 protection. Hard case included.',
        ),
    },
    {
        'category': 'Shoes', 'name': 'Two-Tone Leather Low-Tops',
        'price': 7200, 'image': 'product-17.jpg',
        'colours': ['Navy', 'Tan'],
        'description': body(
            'Navy leather with a tan heel counter and matching lace loop, on '
            'a white vulcanised sole.',
            'Slightly roomier through the toe than the low-top above.',
        ),
    },
    {
        'category': 'Bags', 'name': 'Olive Canvas Weekend Duffel',
        'price': 7900, 'image': 'product-18.jpg',
        'colours': ['Olive', 'Tan'],
        'description': body(
            'A proper weekend bag: heavy olive canvas, tan leather straps and '
            'a full-length brass zip.',
            'Takes two days of clothes and still fits in an overhead locker.',
        ),
    },
    {
        'category': 'Shirts', 'name': 'Camel Crew Sweatshirt',
        'price': 4600, 'image': 'product-19.jpg',
        'sizes': FULL_RANGE, 'colours': ['Camel'],
        # The only product the theme photographed from more than one angle.
        'gallery': [
            ('shop-details/product-big-2.png', 'Worn front view'),
            ('shop-details/product-big-3.png', 'Full-length styling shot'),
            ('shop-details/product-big-4.png', 'Close-up of the hem tab'),
        ],
        'description': body(
            'A heavyweight camel crew in loopback cotton, cut long in the '
            'body with a dropped shoulder and ribbed side panels.',
            'Brushed inside for warmth, with a woven tab at the hem.',
        ),
    },
    {
        'category': 'Bags', 'name': 'Rust Drawstring Bucket Bag',
        'price': 5300, 'image': 'product-20.jpg',
        'colours': ['Rust'],
        'description': body(
            'A quilted cotton bucket bag in rust, gathered with a thick cream '
            'drawstring and carried on soft webbing handles.',
            'Unstructured, so it packs flat when you are not using it.',
        ),
    },
]

# Two rows are seeded empty so the sold-out badge and the disabled add-to-cart
# path are both visible without editing anything by hand.
OUT_OF_STOCK = {'Navy Leather Low-Top Sneakers', 'Brown Leather Briefcase'}


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

        sizes = {}
        for name, position in SIZES:
            size, _ = Size.objects.get_or_create(
                name=name, defaults={'position': position}
            )
            sizes[name] = size

        colours = {}
        for name, hex_value in COLOURS:
            colour, _ = Colour.objects.get_or_create(
                name=name, defaults={'hex_value': hex_value}
            )
            colours[name] = colour
        self.stdout.write(f'Sizes: {len(sizes)}  Colours: {len(colours)}')

        img_root = Path(settings.BASE_DIR) / 'static' / 'img'

        created = 0
        repaired = 0
        gallery_added = 0
        for spec in PRODUCTS:
            name = spec['name']
            image_name = spec['image']
            source = images.get(image_name)

            product = Product.objects.filter(name=name).first()
            if product is not None:
                # Already seeded, but the photo may have gone missing with
                # media/. Re-attach it rather than skipping the row entirely.
                if source is not None and needs_image(product.image):
                    with source.open('rb') as fh:
                        product.image.save(image_name, File(fh), save=True)
                    repaired += 1
            else:
                product = Product(
                    category=categories[spec['category']],
                    name=name,
                    price=spec['price'],
                    stock=0 if name in OUT_OF_STOCK else random.randint(3, 40),
                    description=spec['description'],
                )
                if source is not None:
                    with source.open('rb') as fh:
                        product.image.save(image_name, File(fh), save=False)
                product.save()
                created += 1

            # Facets are set on every run, not just on creation: they were
            # added after the first seed, so existing rows need them too.
            product.sizes.set([sizes[s] for s in spec.get('sizes', [])])
            product.colours.set([colours[c] for c in spec.get('colours', [])])

            for rel_path, alt in spec.get('gallery', []):
                extra = img_root / rel_path
                if not extra.exists():
                    continue
                # Keyed on alt text so a re-run tops up rather than duplicates.
                if product.images.filter(alt=alt).exists():
                    continue
                shot = ProductImage(product=product, alt=alt)
                with extra.open('rb') as fh:
                    shot.image.save(Path(rel_path).name, File(fh), save=False)
                shot.save()
                gallery_added += 1

        self.stdout.write(f'Products created: {created}')
        if repaired:
            self.stdout.write(f'Product photos restored: {repaired}')
        if gallery_added:
            self.stdout.write(f'Gallery images added: {gallery_added}')

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
