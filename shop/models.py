from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify

from .imaging import optimise


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{reverse('shop:product_list')}?category={self.slug}"


class Size(models.Model):
    """A wearable size. Bags and most accessories simply have none."""

    name = models.CharField(max_length=10, unique=True)
    slug = models.SlugField(max_length=10, unique=True, blank=True)
    # The sidebar has to read XS, S, M, L ... not 3XL, 4XL, L, M — so order is
    # stored rather than derived from the name.
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Colour(models.Model):
    name = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=40, unique=True, blank=True)
    # Rendered as an inline background so a colour can be added without also
    # editing the stylesheet. The theme only hardcodes nine.
    hex_value = models.CharField(max_length=7, default='#000000')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products'
    )
    # Which sizes and colours a product is offered in. Stock is held on the
    # product, not per combination, so these narrow the listing and populate
    # the detail page — they are not a variant-level inventory.
    sizes = models.ManyToManyField(Size, blank=True, related_name='products')
    colours = models.ManyToManyField(Colour, blank=True, related_name='products')
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True)
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    # Denormalised from Review, recomputed by Review.save/delete.
    #
    # The alternative is annotating every queryset that renders a card, and
    # cards render on the homepage, the listing, the related strip and the
    # wishlist — four places that would each have to remember. Worse, sorting
    # the listing by rating needs the value in the database anyway. So it is
    # stored, with exactly one writer (`recalculate_rating`) so there is one
    # place for it to be wrong.
    rating_average = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal('0'), editable=False
    )
    rating_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['-created']),
            # Sorting the listing by "best rated".
            models.Index(fields=['-rating_average']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

        # After the row exists, so the file is in storage and can be reopened.
        # optimise() is a no-op on anything it has already been through, which
        # is what keeps an ordinary price edit from re-encoding the photo.
        if optimise(self.image):
            super().save(update_fields=['image'])

    def get_absolute_url(self):
        return reverse('shop:product_detail', args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0

    def recalculate_rating(self):
        """Re-derive the cached rating from the reviews. The only writer."""
        stats = self.reviews.aggregate(avg=Avg('rating'), n=Count('id'))
        Product.objects.filter(pk=self.pk).update(
            rating_average=Decimal(stats['avg'] or 0).quantize(Decimal('0.01')),
            rating_count=stats['n'],
        )
        # .update() writes the row but leaves this instance stale, and callers
        # usually go on to render it.
        self.rating_average = Decimal(stats['avg'] or 0).quantize(Decimal('0.01'))
        self.rating_count = stats['n']

    @property
    def stars(self):
        """Five booleans — filled or not — so a template can just loop.

        Rounded to the nearest whole star. Django templates cannot do
        arithmetic, and doing it here beats a template filter nobody finds.
        """
        filled = int(Decimal(self.rating_average).to_integral_value(rounding='ROUND_HALF_UP'))
        return [i < filled for i in range(5)]


class ProductImage(models.Model):
    """Extra shots feeding the gallery on the product detail page."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='images'
    )
    image = models.ImageField(upload_to='products/')
    alt = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f'Image for {self.product}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if optimise(self.image):
            super().save(update_fields=['image'])


class Review(models.Model):
    """One shopper's verdict on one product.

    Reviews are open to any signed-in account rather than to confirmed buyers
    only, because a shop with no reviews has nothing to show and a course demo
    needs to be able to write one. What buying does earn is the
    `is_verified_purchase` badge, computed once at write time from the orders
    that exist then — a shopper who reviews first and buys later keeps the
    review they wrote, unbadged, which is the honest reading of it.
    """

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='reviews'
    )
    # A review without its author is not worth keeping, unlike an order.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    body = models.TextField(blank=True)
    is_verified_purchase = models.BooleanField(default=False, editable=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        # One review per person per product. Posting again edits the first one
        # rather than stuffing the ballot — enforced in the database, not only
        # in the view, because the view is not the only way in.
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'user'], name='one_review_per_user_per_product'
            )
        ]
        indexes = [models.Index(fields=['product', '-created'])]

    def __str__(self):
        return f'{self.rating}/5 for {self.product} by {self.user}'

    @property
    def stars(self):
        return [i < self.rating for i in range(5)]

    def save(self, *args, **kwargs):
        # Recomputed on every save so an edited rating cannot leave a stale
        # badge, and so a review written before the order was paid picks the
        # badge up when it is edited afterwards.
        self.is_verified_purchase = self.product.orderitem_set.filter(
            order__user=self.user, order__paid=True
        ).exists()
        super().save(*args, **kwargs)

    # Recalculation hangs off signals rather than off save() and delete(),
    # because those two methods are not the only ways a review disappears.
    # `Review.objects.filter(...).delete()` from the admin's bulk action never
    # calls delete(), and neither does the cascade when an account is removed —
    # both would leave a product advertising a rating nobody gave it.
    # post_delete fires for all of them.


class WishlistItem(models.Model):
    """A product an account has saved for later.

    Signed-in only. A session-backed wishlist was considered and dropped: the
    cart already works that way and is meant to be transient, whereas the point
    of a wishlist is that it is still there next month, on whichever device.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist'
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='wishlisted_by'
    )
    added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'], name='one_wishlist_row_per_user_product'
            )
        ]

    def __str__(self):
        return f'{self.product} saved by {self.user}'


@receiver(post_save, sender=Review)
@receiver(post_delete, sender=Review)
def _refresh_product_rating(sender, instance, **kwargs):
    """Keep Product.rating_average and rating_count true to the reviews.

    See the note on Review — signals catch the bulk and cascade deletes that
    an overridden `delete()` would miss.
    """
    # A cascade from Product itself is the one case to skip: the product row
    # is on its way out, and touching it would resurrect nothing useful.
    if kwargs.get('origin') is not None and isinstance(kwargs['origin'], Product):
        return
    try:
        instance.product.recalculate_rating()
    except Product.DoesNotExist:
        pass
