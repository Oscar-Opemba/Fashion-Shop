from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Colour, Product, ProductImage, Review, Size, WishlistItem


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'product_count']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

    @admin.display(description='products')
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ['name', 'position']
    list_editable = ['position']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Colour)
class ColourAdmin(admin.ModelAdmin):
    list_display = ['name', 'hex_value', 'swatch']
    prepopulated_fields = {'slug': ('name',)}

    @admin.display(description='swatch')
    def swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:18px;height:18px;'
            'border:1px solid #ccc;border-radius:50%;background:{}"></span>',
            obj.hex_value,
        )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'category', 'price', 'stock', 'is_active', 'rating_average',
        'rating_count', 'created',
    ]
    list_filter = ['is_active', 'category', 'sizes', 'colours', 'created']
    list_editable = ['price', 'stock', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['sizes', 'colours']
    inlines = [ProductImageInline]
    date_hierarchy = 'created'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'product', 'user', 'rating', 'is_verified_purchase', 'created',
    ]
    list_filter = ['rating', 'is_verified_purchase', 'created']
    search_fields = ['product__name', 'user__username', 'body']
    # Both are derived, never typed: the badge is computed on save, and the
    # timestamps are auto_now/auto_now_add.
    readonly_fields = ['is_verified_purchase', 'created', 'updated']
    date_hierarchy = 'created'

    def delete_queryset(self, request, queryset):
        """Bulk-delete has to leave the cached ratings correct too.

        The admin's default calls queryset.delete(), which never touches
        Review.delete() — so without this, deleting reviews in bulk would leave
        every affected product advertising a rating it no longer has.
        """
        products = {review.product for review in queryset.select_related('product')}
        super().delete_queryset(request, queryset)
        for product in products:
            product.recalculate_rating()


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'added']
    list_filter = ['added']
    search_fields = ['user__username', 'product__name']
