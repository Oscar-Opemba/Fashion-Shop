"""Shrink uploaded product photos to something a phone can afford.

Catalogue photos arrive at whatever the supplier or the phone camera produced.
The live media directory had four files between 100 KB and 340 KB against a
1.4 MB total, and the largest of them was a PNG being painted into a 300 px
card. On a Kenyan mobile connection that is the slowest thing on the page by a
wide margin — far slower than any query on it.

So every image is re-encoded once, on save, to a bounded WebP. WebP because it
is 25-35% smaller than JPEG at the same quality and every browser in the
support window reads it, and *once* because the output name carries a marker
suffix that this module then refuses to process again.

Deliberately not a thumbnail pipeline. There is no per-size rendition, no
srcset and no cache table — one bounded original, which is the 90% of the win
for a few dozen lines and nothing to keep in sync.
"""

import logging
from io import BytesIO

from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

# Big enough that the detail page's 480 px frame still has pixels to spare on a
# 2x screen, small enough that nobody ships a 4000 px phone photo to a shopper.
MAX_SIDE = 1400
QUALITY = 82

# Files already carrying this have been through here. It is how a re-save of an
# unrelated field (a price edit, say) avoids re-encoding the photo every time,
# which would compound the lossy step over and over.
MARKER = '_opt'


def already_optimised(name):
    stem = name.rsplit('/', 1)[-1].rsplit('.', 1)[0]
    return stem.endswith(MARKER)


def optimise(image_field):
    """Re-encode `image_field`'s file in place. True if it was replaced.

    Returns False — leaving the original untouched — for anything already
    processed, and for any file Pillow cannot read. A photo that fails to
    convert is not worth losing an upload over; it just stays big.
    """
    if not image_field:
        return False

    name = image_field.name
    if already_optimised(name):
        return False

    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is a hard dependency
        logger.warning('Pillow is not installed; leaving %s at full size', name)
        return False

    try:
        image_field.open()
        with Image.open(image_field) as img:
            img.load()

            # WebP has no CMYK or palette mode, and an alpha channel is only
            # worth keeping if something is actually transparent.
            has_alpha = img.mode in ('RGBA', 'LA') or (
                img.mode == 'P' and 'transparency' in img.info
            )
            img = img.convert('RGBA' if has_alpha else 'RGB')

            if max(img.size) > MAX_SIDE:
                img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)

            buffer = BytesIO()
            img.save(buffer, format='WEBP', quality=QUALITY, method=6)
    except Exception:
        # Truncated uploads, unsupported formats, or a storage backend that
        # cannot reopen the file. None of those should break saving a product.
        logger.exception('Could not optimise %s; keeping the original', name)
        return False

    stem = name.rsplit('/', 1)[-1].rsplit('.', 1)[0]
    new_name = f'{stem}{MARKER}.webp'

    old_name = name
    # save=False: the caller owns the model row and writes it once, so this
    # does not recurse back into Model.save().
    image_field.save(new_name, ContentFile(buffer.getvalue()), save=False)

    # The original is nothing but weight now. Storage may have renamed the new
    # file to avoid a collision, so never delete what we just wrote.
    if old_name and old_name != image_field.name:
        try:
            image_field.storage.delete(old_name)
        except Exception:
            logger.warning('Could not remove the original %s', old_name)

    return True
