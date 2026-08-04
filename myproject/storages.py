"""Static file storage that survives the theme's dead asset references.

`ManifestStaticFilesStorage` rewrites every `url(...)` it finds inside a
stylesheet to the hashed filename, and raises if the target does not exist.
That strictness is the right default — a broken reference is usually a real
bug, and finding it at deploy time beats finding it in production.

The vendored theme has exactly one, and it is not ours to fix:

    static/css/owl.carousel.min.css  ->  url(owl.video.play.png)

Owl Carousel ships that PNG as the play overlay for video slides. The theme's
zip omitted it, and this shop has no video slides, so nothing has ever
requested it. Editing the file to remove the reference would break the rule the
whole CSS layering is built on (see MODULE.md 3.3), and inventing a
placeholder PNG would be worse — a fake asset committed to look like a real
one.

So a missing target degrades to the unhashed name and logs, rather than failing
the deploy. The log line matters: this must not become a silent blanket that
hides a genuine broken reference in our own CSS later on.
"""

import logging

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class ForgivingManifestStaticFilesStorage(ManifestStaticFilesStorage):
    # A template asking for a file that is not in the manifest gets the plain
    # name back instead of raising. Same reasoning as below.
    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError as exc:
            logger.warning(
                'Static reference could not be hashed, serving it unhashed: %s', exc
            )
            return name
