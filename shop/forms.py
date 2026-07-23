from django import forms
from django.utils.text import slugify
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import Category, Product


class SlugFromNameMixin:
    """Fill a blank slug during `clean()` so uniqueness is still checked.

    `Product.save()` and `Category.save()` already slugify a blank slug, but
    that happens after validation — a second "Denim Jacket" would reach the
    database with a duplicate slug and raise IntegrityError. Doing it here
    means `_post_clean()` sees the real slug and reports it as a form error.
    """

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('slug') and cleaned.get('name'):
            cleaned['slug'] = slugify(cleaned['name'])
            self.instance.slug = cleaned['slug']
        return cleaned


class BootstrapFormMixin:
    """Give every widget the theme's form classes, as the accounts forms do."""

    def _style_widgets(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, forms.CheckboxSelectMultiple):
                continue  # styled by the template, not by a single class
            elif isinstance(widget, CKEditor5Widget):
                continue  # the editor replaces the textarea entirely
            elif isinstance(widget, forms.ClearableFileInput):
                widget.attrs.setdefault('class', 'form-control-file')
            else:
                widget.attrs.setdefault('class', 'form-control')


class ProductForm(SlugFromNameMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'slug', 'description', 'price', 'category',
            'sizes', 'colours', 'image', 'stock', 'is_active',
        ]
        widgets = {
            # The project ships CKEditor 5 configured for exactly this field
            # (settings.CKEDITOR_5_CONFIGS['extends']); the model column stays
            # a plain TextField so nothing else has to know about the editor.
            'description': CKEditor5Widget(config_name='extends'),
            'sizes': forms.CheckboxSelectMultiple,
            'colours': forms.CheckboxSelectMultiple,
        }
        help_texts = {
            'slug': 'Leave blank to build it from the name.',
            'stock': 'Zero hides the add-to-cart button but keeps the page live.',
            'is_active': 'Unticked keeps the product out of the shop entirely.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['price'].widget.attrs.setdefault('step', '0.01')
        self.fields['price'].widget.attrs.setdefault('min', '0')
        self._style_widgets()


class CategoryForm(SlugFromNameMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        # Category has no description field — the lesson's third field lives on
        # Product here.
        fields = ['name', 'slug', 'image']
        help_texts = {
            'slug': 'Leave blank to build it from the name.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_widgets()
