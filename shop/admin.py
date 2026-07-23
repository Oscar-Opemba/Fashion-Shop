from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Colour, Product, ProductImage, Size


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
    list_display = ['name', 'category', 'price', 'stock', 'is_active', 'created']
    list_filter = ['is_active', 'category', 'sizes', 'colours', 'created']
    list_editable = ['price', 'stock', 'is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['sizes', 'colours']
    inlines = [ProductImageInline]
    date_hierarchy = 'created'
