from django.db import models
from django.urls import reverse
from django.utils.text import slugify


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

    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['-created']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('shop:product_detail', args=[self.slug])

    @property
    def in_stock(self):
        return self.stock > 0


class ProductImage(models.Model):
    """Extra shots feeding the gallery on the product detail page."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='images'
    )
    image = models.ImageField(upload_to='products/')
    alt = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f'Image for {self.product}'
