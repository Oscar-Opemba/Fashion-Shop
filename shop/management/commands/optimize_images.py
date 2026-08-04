"""Run the upload-time image optimiser over photos that predate it.

New uploads are bounded by `Product.save()` (see shop/imaging.py). Everything
already in the media directory when that landed is still full size, and on a
deployed site that is the majority of it — so this walks the catalogue once and
brings the back-catalogue in line.

    python manage.py optimize_images --dry-run
    python manage.py optimize_images

Safe to run twice: the optimiser skips anything carrying its marker suffix, so
a second pass reports every file as already done rather than re-encoding it and
compounding the lossy step.
"""

from django.core.management.base import BaseCommand

from shop.imaging import already_optimised, optimise
from shop.models import Product, ProductImage


class Command(BaseCommand):
    help = 'Re-encode existing product photos as bounded WebP.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='List what would be converted without writing anything.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        saved = converted = skipped = 0

        for model, field in ((Product, 'image'), (ProductImage, 'image')):
            for obj in model.objects.exclude(**{field: ''}):
                image = getattr(obj, field)

                if already_optimised(image.name):
                    skipped += 1
                    continue

                try:
                    before = image.size
                except (OSError, ValueError):
                    # The row points at a file that is not on this disk —
                    # normal after a database is copied between environments.
                    self.stderr.write(f'  missing: {image.name}')
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(f'  would convert {image.name} ({before / 1024:.0f} KB)')
                    converted += 1
                    continue

                name = image.name
                if not optimise(image):
                    skipped += 1
                    continue

                # save=False in optimise() means the row still points at the
                # old name until this writes it.
                model.objects.filter(pk=obj.pk).update(**{field: image.name})

                after = image.size
                saved += before - after
                converted += 1
                self.stdout.write(
                    f'  {name} -> {image.name}  '
                    f'{before / 1024:.0f} KB -> {after / 1024:.0f} KB'
                )

        verb = 'would convert' if dry_run else 'converted'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {converted} image(s), skipped {skipped}'
            + ('' if dry_run else f', saved {saved / 1024:.0f} KB')
        ))
