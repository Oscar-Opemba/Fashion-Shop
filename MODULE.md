# Building this shop from nothing — the full walkthrough

This is the beginner's guide to the project. It starts at an empty folder and
ends at a working online store: products, a cart, checkout, M-Pesa payment,
user accounts and an admin panel.

Read it top to bottom the first time. Every command here has been run against
this project — if a command's output is shown, that is what you should see.

- **[README.md](README.md)** — the 30-second version, for someone who just
  wants the server running.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — the reference: every file, every
  model, every decision and why it was made.
- **This file** — the story, in order, with the reasoning.

| Part | What you learn |
|---|---|
| [0](#part-0--what-you-are-building) | What the finished thing is |
| [1](#part-1--the-environment) | Python, virtual environments, pip, `requirements.txt` |
| [2](#part-2--starting-the-django-project) | `startproject`, `startapp`, settings, `.env` |
| [3](#part-3--the-theme-from-themewagon) | Picking a template, wiring its CSS/JS into Django |
| [4](#part-4--templates-the-django-way) | `base.html`, `{% extends %}`, `{% include %}`, context processors |
| [5](#part-5--models--databases) | Models, relationships, migrations, the ORM |
| [6](#part-6--the-admin) | `@admin.register`, inlines, `list_editable` |
| [7](#part-7--views-urls-and-the-request-flow) | How a URL becomes a page |
| [8](#part-8--the-shopping-cart) | Sessions, no database table needed |
| [9](#part-9--checkout-and-orders) | Forms, transactions, frozen prices |
| [10](#part-10--paying-with-m-pesa) | Daraja STK Push, ngrok, callbacks |
| [11](#part-11--user-accounts) | django-allauth, Google/Facebook sign-in |
| [12](#part-12--tests) | What is tested and why those things |
| [13](#part-13--running-it-day-to-day) | The commands you will actually type |
| [14](#part-14--when-it-breaks) | Errors you will hit, and the fix |
| [15](#part-15--before-it-goes-live) | The deploy checklist |

---

## Part 0 — What you are building

A clothing shop. A visitor can browse products, filter them by category, price,
size and colour, open a product, add it to a cart, check out with their
delivery details, and pay with M-Pesa on their phone. They can do all of that
without an account. If they *do* make an account, they get an order history, a
saved profile and saved addresses.

You (the owner) get Django's admin panel, where you add products, upload
photos, set prices and stock, and move orders from paid to shipped to
delivered.

The stack:

| Piece | Choice | Why |
|---|---|---|
| Language | Python 3.13 | what Django 6 wants |
| Framework | Django 6.0.7 | batteries included: ORM, admin, auth, forms |
| Database | SQLite | a single file, zero setup — swap for PostgreSQL later |
| Front end | MaleFashion HTML template (ThemeWagon) | a real designer's shop layout, free |
| Payments | Safaricom Daraja, STK Push | the customers are in Kenya |
| Accounts | django-allauth | email login + Google/Facebook without writing it |

---

## Part 1 — The environment

### 1.1 Check Python

```bash
python3 --version
```
```
Python 3.13.14
```

Anything 3.12 or newer is fine for Django 6. If `python3` is missing, install
it from your package manager (`sudo apt install python3 python3-venv` on
Debian/Ubuntu/Kali) — not from a random installer.

### 1.2 Make the project folder

```bash
mkdir Fashion-Shop
cd Fashion-Shop
```

### 1.3 Create a virtual environment

A **virtual environment** is a private copy of Python for this one project. It
exists so that installing Django 6 here cannot break some other project that
needs Django 4. Every Python project should have one. No exceptions.

```bash
python3 -m venv .venv
```

That creates a `.venv/` folder. Now **activate** it:

```bash
source .venv/bin/activate       # Linux / macOS
# .venv\Scripts\activate        # Windows PowerShell
```

Your prompt changes to show `(.venv)`. That prefix is how you know packages
will land in the project and not on your system Python.

> **You must re-activate every time you open a new terminal.** The single most
> common beginner error — `ModuleNotFoundError: No module named 'django'` — is
> almost always a terminal where nobody ran `source .venv/bin/activate`.

To leave it: `deactivate`.

### 1.4 Install the packages

```bash
pip install --upgrade pip
pip install django python-dotenv pillow requests \
            django-allauth django-crispy-forms crispy-bootstrap4 \
            django-ckeditor-5 django-embed-video
```

What each one is for:

| Package | Job |
|---|---|
| `django` | the framework |
| `python-dotenv` | reads secrets out of a `.env` file instead of hard-coding them |
| `pillow` | image handling — **required** by `ImageField`; product photos won't save without it |
| `requests` | makes the HTTP calls to Safaricom's Daraja API |
| `django-allauth` | sign up, sign in, password reset, Google/Facebook |
| `django-crispy-forms` + `crispy-bootstrap4` | renders Django forms with Bootstrap 4 classes so they match the theme |
| `django-ckeditor-5` | the rich-text editor for product descriptions in the admin |
| `django-embed-video` | lets a description embed a YouTube/Vimeo clip |

### 1.5 Freeze the list

```bash
pip freeze > requirements.txt
```

That writes every package **and its exact version** into a file. It is how
someone else — or you, on another machine — reproduces your environment:

```bash
pip install -r requirements.txt
```

This project's `requirements.txt` is 19 lines. Most of them you never installed
by hand; they are dependencies of the ones you did (`asgiref` comes with
Django; `certifi`, `urllib3` and `idna` come with `requests`, and so on).

**Pinned versions matter.** `Django==6.0.7` means everyone gets 6.0.7. Without
the pin, a clone six months from now silently gets a newer Django and breaks.

---

## Part 2 — Starting the Django project

### 2.1 Project vs app

Django splits code two ways, and the naming trips everyone up at first:

- A **project** is the whole site. It holds settings and the root URL list.
  Here it is `myproject/`. There is exactly one.
- An **app** is one feature area, with its own models, views, URLs and
  templates. Here there are six. Apps are meant to be small and focused.

### 2.2 Create the project

```bash
django-admin startproject myproject .
```

The trailing `.` matters. Without it you get `Fashion-Shop/myproject/myproject/`
— one folder deeper than anyone wants. With it, `manage.py` sits at the top:

```
Fashion-Shop/
├── manage.py          ← you run everything through this
└── myproject/
    ├── settings.py    ← all configuration
    ├── urls.py        ← the root URL table
    ├── wsgi.py        ← how a normal web server starts the site
    └── asgi.py        ← the async equivalent
```

Check it runs:

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and you get Django's rocket page. `Ctrl+C` stops
it. That is the whole "hello world"; from here on everything is additive.

### 2.3 Create the apps

```bash
python manage.py startapp core
python manage.py startapp shop
python manage.py startapp cart
python manage.py startapp orders
python manage.py startapp payments
python manage.py startapp accounts
```

Each gets the same skeleton: `models.py`, `views.py`, `admin.py`, `apps.py`,
`tests.py`, `migrations/`. You add `urls.py` and sometimes `forms.py` yourself
— `startapp` does not create those.

Why these six?

| App | Owns | Has models? |
|---|---|---|
| `core` | home, about, contact — the pages that are not shopping | no |
| `shop` | products, categories, sizes, colours — **the centre of the domain** | yes |
| `cart` | the shopping cart | no — it lives in the session |
| `orders` | checkout, orders, order lines, coupons | yes |
| `payments` | M-Pesa: the Daraja client, the callback | yes |
| `accounts` | profiles, saved addresses | yes |

**The rule that keeps this clean:** every app may import from `shop`; `shop`
imports from nobody. If `shop` ever imports from `core`, Django won't start —
that is a circular import. When two apps need to share data with templates, use
a context processor (Part 4.4), not an import.

### 2.4 Register the apps

Django ignores an app until it is listed. In `myproject/settings.py`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',        # allauth needs this

    # Third party
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'crispy_forms',
    'crispy_bootstrap4',
    'django_ckeditor_5',
    'embed_video',

    # Local
    'core', 'shop', 'cart', 'orders', 'payments', 'accounts',
]
```

Keep the three groups in that order and label them. In six months you will want
to know at a glance which of these you wrote.

### 2.5 Secrets go in `.env`, never in `settings.py`

`startproject` writes your `SECRET_KEY` straight into `settings.py`. That is
fine until you push to GitHub, at which point you have published the key that
signs every session cookie on your site.

The fix is a `.env` file that is **never committed**, read at startup:

```python
from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [v.strip() for v in env(name, default).split(',') if v.strip()]


SECRET_KEY = env('SECRET_KEY', 'django-insecure-dev-only-change-me')
DEBUG = env_bool('DEBUG', True)
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')
```

Three helpers, because everything in a `.env` file is a **string**. Without
`env_bool`, `DEBUG=False` in the file becomes the Python string `'False'`,
which is truthy, and you ship a live site with debug on and your source code
visible on every error page.

> Some tutorials use `python-decouple` and `config('X')` instead. It does the
> same job. This project uses `python-dotenv` — don't add both.

Now create the two files:

```bash
touch .env .env.example
```

- `.env` — the real values. **Gitignored.**
- `.env.example` — the same keys with blank values, plus comments saying where
  to get each one. **Committed.** It is the documentation of what a fresh clone
  needs.

Generate a real secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 2.6 `.gitignore`

```gitignore
__pycache__/
*.py[cod]
.venv/
.env
.env.*
!.env.example        # ← keep the template, drop everything else
db.sqlite3
staticfiles/
media/
.idea/
.DS_Store
```

Why each exclusion:

- **`.venv/`** — thousands of files, and it is machine-specific.
  `requirements.txt` replaces it.
- **`.env`** — your secrets. The `!.env.example` line is an un-ignore: it keeps
  the template tracked.
- **`db.sqlite3`** — the database is data, not code. Anyone can rebuild it with
  `migrate` + `seed`.
- **`media/`** — user uploads. Same reason.
- **`staticfiles/`** — generated by `collectstatic` at deploy time.

### 2.7 The other settings worth setting now

```python
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'      # timestamps in the admin read as local time
USE_TZ = True                     # store UTC, display local — always leave on

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']    # where dev looks for CSS/JS
STATIC_ROOT = BASE_DIR / 'staticfiles'      # where collectstatic writes, at deploy

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'             # uploaded photos land here
```

**Static vs media** is the distinction beginners lose most often:

- **Static** = files *you* wrote and shipped. CSS, JavaScript, the logo. They
  live in git.
- **Media** = files *users* uploaded. Product photos, avatars. They do not.

They are configured separately, served separately, and backed up separately.

---

## Part 3 — The theme, from ThemeWagon

You could write the CSS yourself. You would spend three weeks and it would look
worse. Starting from a finished HTML template is the normal professional move
for a project like this.

### 3.1 Choosing it

Go to [themewagon.com](https://themewagon.com), filter to **Free** and
**eCommerce**. What actually matters when picking:

1. **The licence.** Free ≠ no strings. Read it before you commit.
2. **Does it have the pages you need?** A shop template that ships a product
   listing, a product detail page and a cart page saves far more work than a
   prettier one that ships only a homepage.
3. **Bootstrap version.** Bootstrap 4 or 5 means you can find help. A bespoke
   grid means you are on your own.
4. **Plain HTML, not React.** You want files you can paste into a Django
   template.

This project uses
**[MaleFashion](https://themewagon.com/themes/free-bootstrap-4-html5-ecommerce-website-template-malefashion/)**
by [Colorlib](https://colorlib.com) — Bootstrap 4, and it ships the exact pages
a shop needs: `index.html`, `shop.html`, `shop-details.html`,
`shopping-cart.html`, `checkout.html`, `about.html`, `contact.html`.

> **Licence: CC BY 3.0.** That "BY" means attribution. The Colorlib credit in
> the footer is a condition of use — leave it there. Stripping it is a licence
> violation. It lives in `templates/includes/footer.html`.

### 3.2 Unpacking it

The download is a zip roughly like:

```
malefashion/
├── index.html          shop.html      shop-details.html
├── shopping-cart.html  checkout.html  about.html  contact.html
├── css/     bootstrap.min.css, style.css, owl.carousel.css, ...
├── js/      jquery, bootstrap.js, main.js, ...
├── fonts/   FontAwesome, ElegantIcons
└── img/     every photo the template uses
```

Copy the **asset folders** into a top-level `static/`, and keep the HTML files
somewhere outside the project to convert page by page:

```bash
mkdir static
cp -r malefashion/css malefashion/js malefashion/fonts malefashion/img static/
```

After the copy, `static/` holds ~111 files.

> Note it is `static/img/`, not `static/images/`. Keep the theme's own name.
> Renaming it means editing every path inside `style.css`, for nothing.

### 3.3 Never edit the theme's files

This is the single most valuable habit in this whole document.

`static/css/style.css` is thousands of lines of somebody else's CSS. The moment
you start editing it you can no longer tell your changes from theirs, and you
can never take an upstream fix.

Instead, add one file of your own and load it **last**:

```
static/css/style.css          ← theirs, never touched
static/css/storefront.css     ← yours, loaded after, so it wins
static/js/main.js             ← theirs, never touched
static/js/shop.js             ← yours, layered on top
```

Because CSS applies the last matching rule, loading your file after theirs is
all the "override" mechanism you need.

`storefront.css` in this project is deliberately **not a restyle**. It covers
exactly two things:

1. Places where the theme uses a link (`<a>`) but a real shop needs a form POST
   — add to cart, sign out. A `<button>` inside a form has to be made to look
   like the theme's link.
2. Pages the theme never shipped: order history, sign-in, the address book.

Every colour in it is lifted from the theme (`#111` text, `#e53637` accent), so
the new pages look like they came in the same zip.

### 3.4 Wire the assets into a Django template

The theme's HTML says:

```html
<link rel="stylesheet" href="css/style.css">
<img src="img/logo.png">
```

Those are relative paths that only work if the HTML sits next to the folders.
In Django you use the `static` tag, which asks the settings where static files
actually live:

```django
{% load static %}
<link rel="stylesheet" href="{% static 'css/style.css' %}">
<img src="{% static 'img/logo.png' %}">
```

`{% load static %}` goes on the **first line of every template that uses it**.
Forgetting it gives you `Invalid block tag 'static'`.

The payoff comes at deploy: `collectstatic` can rename `style.css` to
`style.a3f8b1.css` for cache-busting, and `{% static %}` emits the new name
everywhere automatically. Hard-coded paths would all break.

---

## Part 4 — Templates, the Django way

### 4.1 Tell Django where templates live

```python
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],     # ← project-wide templates
    'APP_DIRS': True,                     # ← plus each app's templates/ folder
    'OPTIONS': {'context_processors': [...]},
}]
```

`DIRS` is searched first, then every app. That ordering is what lets you
override a template that came from a third-party package — put a file at the
same path in your `templates/` and yours wins. This project uses it to restyle
allauth's login and signup pages.

```bash
mkdir templates
```

### 4.2 `base.html` — write the shell once

Every page of the theme repeats the same `<head>`, header, footer and script
tags. Copy that skeleton into `templates/base.html` once, and punch **blocks**
where pages differ:

```django
{% load static %}<!DOCTYPE html>
<html lang="en">
<head>
    <title>{% block title %}Shop{% endblock %}</title>
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
    {# Loaded last so it wins over the theme without editing the theme's files. #}
    <link rel="stylesheet" href="{% static 'css/storefront.css' %}">
    {% block extra_css %}{% endblock %}
</head>
<body>
    {% include 'includes/offcanvas.html' %}
    {% include 'includes/header.html' %}
    {% block breadcrumb %}{% endblock %}
    {% include 'includes/messages.html' %}
    {% block content %}{% endblock %}
    {% include 'includes/footer.html' %}
    <script src="{% static 'js/jquery-3.3.1.min.js' %}"></script>
    <!-- ... the theme's other scripts ... -->
    <script src="{% static 'js/shop.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

Then every page is just the bit that is different:

```django
{% extends 'base.html' %}

{% block title %}Shop{% endblock %}

{% block content %}
  <!-- only this page's markup -->
{% endblock %}
```

**`{% extends %}` must be the first line of the file.** Nothing above it.

### 4.3 `{% extends %}` vs `{% include %}`

| | What it does | Use for |
|---|---|---|
| `{% extends 'base.html' %}` | this page *is a* base page, filling its blocks | every page |
| `{% include 'includes/header.html' %}` | paste this fragment here | anything repeated |

Inheritance goes two levels deep in one place here:
`base.html` → `account/base_entrance.html` → `account/login.html`, so login and
signup share a centred card without duplicating it.

The eight includes:

```
includes/header.html          nav, cart badge, account menu
includes/footer.html          + the Colorlib attribution
includes/offcanvas.html       the mobile slide-out menu
includes/messages.html        renders alert-{{ message.tags }}
includes/product_card.html    one product card — used on home, shop, related
includes/breadcrumb.html
includes/search_modal.html
includes/social_login.html    the Google / Facebook buttons
```

`product_card.html` earns its keep: the same card appears on the homepage, the
listing and the related-products strip. One file, three uses — change the card
once and it changes everywhere.

A leading underscore (`cart/_summary.html`) marks a **fragment** — something
rendered into another page or returned by AJAX, never served as a page itself.
Django does not enforce it; it is a convention so you can read the folder.

### 4.4 Context processors — data on every single page

The header shows a cart badge. The nav shows a category dropdown. Both need
data on **every** page. Passing `cart` and `nav_categories` from all forty
views would be miserable and easy to forget.

A context processor is a function that runs on every render and adds to the
context:

```python
# cart/context_processors.py
from .cart import Cart

def cart(request):
    """The header shows an item count and running total on every page."""
    return {'cart': Cart(request)}
```

```python
# shop/context_processors.py
from .models import Category

def shop(request):
    """The nav's category dropdown, needed on every page."""
    return {'nav_categories': Category.objects.all()}
```

Register both:

```python
'context_processors': [
    'django.template.context_processors.debug',
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',      # gives every template `user`
    'django.contrib.messages.context_processors.messages',
    'cart.context_processors.cart',
    'shop.context_processors.shop',
],
```

The deeper reason these exist: they let apps share data with templates
**without importing each other**. That is what keeps the dependency graph
acyclic.

Cost: they run on every request, so keep them to one cheap query. Never put a
heavy join in one.

### 4.5 Messages

```python
from django.contrib import messages
messages.success(request, f'{product.name} added to your cart.')
```

renders through `includes/messages.html` as `alert-success`. But Django's error
level is called `error` while Bootstrap's class is `alert-danger`, so one line
of settings bridges it:

```python
MESSAGE_TAGS = {
    message_constants.DEBUG: 'secondary',
    message_constants.ERROR: 'danger',
}
```

---

## Part 5 — Models & databases

A **model** is a Python class that becomes a database table. One class, one
table; one attribute, one column. You never write `CREATE TABLE` — Django
generates the SQL from the class.

### 5.1 Where the models live

Split by app, not one giant `models.py`:

| File | Models |
|---|---|
| `shop/models.py` | `Category`, `Size`, `Colour`, `Product`, `ProductImage` |
| `orders/models.py` | `Coupon`, `Order`, `OrderItem` |
| `payments/models.py` | `MpesaPayment` |
| `accounts/models.py` | `Profile`, `Address` |

Eleven models. `core` and `cart` own none on purpose — `core` is pages, and the
cart lives in the session.

### 5.2 A model, annotated

```python
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True)

    class Meta:
        verbose_name_plural = 'categories'    # else the admin says "Categorys"
        ordering = ['name']                   # default sort for every query

    def __str__(self):
        return self.name                      # what the admin and shell show

    def save(self, *args, **kwargs):
        if not self.slug:                     # auto-slug, so nobody types one
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)         # ← never forget this line

    def get_absolute_url(self):
        return f"{reverse('shop:product_list')}?category={self.slug}"
```

Five things to take from that:

- **A slug** is the URL-safe form of a name: `Leather Jacket` →
  `leather-jacket`. URLs read as `/shop/leather-jacket/` instead of
  `/shop/17/`, which is better for humans and for search engines.
- **`__str__`** is what you see in admin dropdowns and the shell. Without it
  everything reads `Category object (1)`.
- **Overriding `save()`** puts the rule in the model, so it holds no matter who
  writes the row — a view, the admin, the shell, a management command.
  `super().save()` at the end is mandatory; drop it and nothing is written.
- **`Meta.ordering`** is the default sort, applied to every query.
- **`get_absolute_url()`** means a template can write
  `{{ product.get_absolute_url }}` and never construct a path by hand.

### 5.3 The three relationship types, in this codebase

**One-to-Many — `ForeignKey`.** One category has many products:

```python
class Product(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products'
    )
```

`related_name='products'` creates the reverse: `category.products.all()`.
Without it you would be writing `category.product_set.all()`.

**Many-to-Many — `ManyToManyField`.** A product comes in several sizes, and a
size fits many products:

```python
    sizes   = models.ManyToManyField(Size, blank=True, related_name='products')
    colours = models.ManyToManyField(Colour, blank=True, related_name='products')
```

Django silently creates the join table for you.

> **Important limitation, stated on purpose:** sizes and colours here are *not*
> variants. Stock is held on the product, not per size/colour combination.
> They narrow the listing and tell the shopper what a piece comes in; the cart
> does not record which size was chosen. Real per-variant inventory needs a
> `ProductVariant` model, and that is a bigger build.

**One-to-One — `OneToOneField`.** Every user has exactly one profile:

```python
class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile'
    )
```

Always write `settings.AUTH_USER_MODEL`, never
`from django.contrib.auth.models import User`. The indirection is what lets a
project swap in a custom user model later.

**Many-to-many *through* a model.** An order contains many products and a
product appears in many orders — but each line also needs its own quantity and
its own price, so the join is an explicit model:

```python
class OrderItem(models.Model):
    order    = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product  = models.ForeignKey(Product, on_delete=models.PROTECT)
    price    = models.DecimalField(max_digits=10, decimal_places=2)  # frozen
    quantity = models.PositiveIntegerField(default=1)
```

### 5.4 `on_delete` — the decision people skip

Django forces you to say what happens to a row when the thing it points at is
deleted. It is a real design decision, not boilerplate:

| Choice | Meaning | Used here for |
|---|---|---|
| `CASCADE` | delete this too | `ProductImage.product`, `OrderItem.order`, `Profile.user`, `Address.user`, `MpesaPayment.order` |
| `PROTECT` | refuse the delete | `Product.category`, `OrderItem.product` |
| `SET_NULL` | keep the row, blank the link | `Order.user`, `Order.coupon` |

The reasoning:

- **`PROTECT` on `OrderItem.product`** — you must not be able to delete a
  product that somebody bought. It would blow a hole in your sales history. Set
  `is_active=False` instead; the shop hides it and the history survives.
- **`SET_NULL` on `Order.user`** — a customer deletes their account; the order
  must remain, or your revenue figures change retroactively. That is also why
  the field is `null=True`: guest checkout produces orders with no user at all.
- **`CASCADE` on `Profile.user`** — a profile with no user is meaningless.

### 5.5 Money is `DecimalField`. Always.

```python
price = models.DecimalField(max_digits=10, decimal_places=2)
```

Never `FloatField`. Floats are binary and cannot represent `0.1` exactly, so
money arithmetic drifts:

```python
>>> 0.1 + 0.2
0.30000000000000004
```

Multiply that error over a few thousand orders and your books do not balance.
`Decimal` is exact. `max_digits=10, decimal_places=2` gives you up to
99,999,999.99.

### 5.6 Frozen prices — the most important rule in the file

```python
class OrderItem(models.Model):
    # Price is captured at purchase time and never re-read from the product.
    price = models.DecimalField(max_digits=10, decimal_places=2)
```

If an order line pointed at `product.price` instead of storing its own copy,
raising a price tomorrow would rewrite every past receipt for that item.
Customers would open their order history and see a number they never paid.

So the price is **copied** — into the cart when the item is added, and again
into the `OrderItem` at checkout. `Order` has no `total` column at all; it is
computed from the frozen lines:

```python
    def get_subtotal(self):
        return sum((item.get_cost() for item in self.items.all()), Decimal('0'))

    def get_discount(self):
        if not self.discount_percent:
            return Decimal('0')
        return (self.get_subtotal() * self.discount_percent / Decimal('100')).quantize(
            Decimal('0.01')
        )

    def get_total(self):
        return self.get_subtotal() - self.get_discount()
```

Computing beats storing here, because a stored total can silently disagree with
the lines it is supposed to sum. There is no such thing as an out-of-date
computed total.

### 5.7 `TextChoices` for status fields

```python
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING    = 'pending',    'Pending payment'
        PAID       = 'paid',       'Paid'
        PROCESSING = 'processing', 'Processing'
        SHIPPED    = 'shipped',    'Shipped'
        DELIVERED  = 'delivered',  'Delivered'
        CANCELLED  = 'cancelled',  'Cancelled'

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
```

Each entry has a value stored in the database and a label shown to humans. In
code you write `Order.Status.PAID`, not the string `'paid'` — a typo in an enum
member is an `AttributeError` you find immediately, while a typo in a string is
a silent bug.

Django gives you `order.get_status_display()` free, which returns the label.

`PROCESSING` is kept only because older rows still carry it, from a period when
checkout completed with no payment step. Deleting the member would make those
rows render a blank.

### 5.8 Indexes and properties

```python
    class Meta:
        ordering = ['-created']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['-created']),
        ]
```

An index is a lookup shortcut for the database. `slug` is indexed because every
product page looks a product up by it; `-created` because every listing sorts
by it. Do not index everything — each index costs write speed and disk.

```python
    @property
    def in_stock(self):
        return self.stock > 0
```

A `@property` is computed, never stored. Templates call it without parentheses:
`{% if product.in_stock %}`. Anything derivable from other fields should be a
property, not a column — a column can go stale, a property cannot.

### 5.9 Migrations

A **migration** is a versioned, replayable description of a schema change.
Editing `models.py` alone changes nothing in the database; the migration is
what applies it.

```bash
python manage.py makemigrations     # read the models, write a migration file
python manage.py migrate            # run the un-applied ones against the DB
```

Check what has run:

```bash
python manage.py showmigrations shop orders accounts payments
```
```
accounts
 [X] 0001_initial
orders
 [X] 0001_initial
 [X] 0002_remove_order_paid_remove_order_stock_applied_and_more
 [X] 0003_order_paid_order_stock_applied_alter_order_phone_and_more
payments
 [X] 0001_initial
shop
 [X] 0001_initial
 [X] 0002_remove_review_one_review_per_user_per_product_and_more
 [X] 0003_colour_size_product_colours_product_sizes
```

`[X]` = applied. Read the names as a history: `shop 0002` removed reviews and
wishlists, `shop 0003` added sizes and colours. `orders 0002` stripped the
payment fields when M-Pesa was taken out, and `0003` put them back when it
returned. That log of what happened when is exactly what migrations are for.

**Drift is the thing to watch.** Ask Django whether the models and the
migrations still agree:

```bash
python manage.py makemigrations --check --dry-run
```
```
No changes detected
```

That is the first command to run when a project is misbehaving. Anything else
means someone edited a model and never generated the migration.

See the SQL without running it:

```bash
python manage.py sqlmigrate shop 0001 | head -20
```

Real `CREATE TABLE` statements. Worth looking at once: the ORM *generates* SQL,
it does not replace it.

**Migrations roll back.** Practise on a throwaway field. Add to `Product`:

```python
    featured = models.BooleanField(default=False)
```

```bash
python manage.py makemigrations shop
```
```
Migrations for 'shop':
  shop/migrations/0004_product_featured.py
    + Add field featured to product
```

Open the generated file — it is short, and shows an `AddField` operation plus a
`dependencies` list pointing at `0003`. That dependency chain is how Django
knows what order to apply things in.

```bash
python manage.py migrate shop           #   Applying shop.0004_product_featured... OK
python manage.py migrate shop 0003      #   Unapplying shop.0004_product_featured... OK
```

Migrating *to* an earlier number rolls back. Clean up afterwards, or you leave
the repo dirty:

```bash
rm shop/migrations/0004_product_featured.py
# then delete the `featured` line from shop/models.py
python manage.py makemigrations --check --dry-run   # No changes detected
```

**Migration rules:**

- Commit migration files. They are source code, not build output.
- Never edit an applied migration. Make a new one.
- `makemigrations` then `migrate`, in that order, every time you touch a model.

### 5.10 The ORM, hands on

```bash
python manage.py shell
```

```python
from shop.models import Category, Product
from orders.models import Order, OrderItem
from django.contrib.auth import get_user_model

# ---- One-to-Many: Category -> Products ----
c = Category.objects.first()
c                      # <Category: Accessories>
c.products.count()     # 4   <- related_name at work
[p.name for p in c.products.all()[:3]]

# ---- and back the other way ----
p = Product.objects.first()
p.category.name        # 'Accessories'

# ---- One-to-One: User -> Profile ----
u = get_user_model().objects.first()
u.profile              # <Profile: Profile for admin>

# ---- Many-to-many through a model ----
[f.name for f in OrderItem._meta.fields]
# ['id', 'order', 'product', 'price', 'quantity']

# ---- The conventions, visible ----
str(p)                 # 'Polarised Sunglasses'    <- __str__
p.get_absolute_url()   # '/shop/polarised-sunglasses/'
p.in_stock             # True
Order.Status.choices   # [('pending', 'Pending payment'), ('paid', 'Paid'), ...]

# ---- Querying ----
Product.objects.filter(price__lt=5000).count()
Product.objects.filter(name__icontains='jacket')
Product.objects.filter(category__slug='shoes')        # __ traverses the FK
Product.objects.exclude(stock=0).order_by('price')
```

Double-underscore is the ORM's path separator: `category__slug` means "follow
the `category` foreign key, then look at its `slug`". It works to any depth —
`items__product__category__name`.

**The N+1 problem**, which is the performance bug you will actually hit:

```python
# BAD: 1 query for the products, then 1 more per product for its category
for p in Product.objects.all():
    print(p.category.name)

# GOOD: one query, joined
for p in Product.objects.select_related('category'):
    print(p.category.name)
```

- `select_related('category')` — for `ForeignKey`/`OneToOne`. Does a SQL JOIN.
- `prefetch_related('images', 'sizes', 'colours')` — for reverse FKs and
  many-to-many. Does one extra query per relation and stitches in Python.

Both are used in `shop/views.py`. Twenty products with an unoptimised loop is
21 queries; with `select_related` it is one.

### 5.11 Sample data — `manage.py seed`

An empty shop is impossible to build against, and typing twenty products into
the admin by hand is worse. So there is a custom management command at
`shop/management/commands/seed.py`:

```bash
python manage.py seed
```

It creates 5 categories, 20 products, 8 sizes, 10 colours, gallery images and a
superuser, copying product photos out of the theme's own `static/img/product/`
so there is nothing to download. It is **idempotent** — safe to run twice; it
updates rather than duplicating. `--flush` wipes products and categories first.

Two things in it are worth understanding, because both were bugs:

1. **`needs_image()`** re-attaches a photo whose file has gone missing. `media/`
   is gitignored, so a fresh clone has product rows pointing at files that were
   never committed. Without this the cards render with every image 404ing,
   which reads as the products being invisible.
2. **Products are paired with photos by name, never by list position.**
   `sorted(glob('*.jpg'))` returns `product-1, product-10, product-11,
   product-2…` — string order, not numeric. Pairing by index once mislabelled
   every product in the shop; a duffel bag was sold as a t-shirt. There is a
   test in `shop/tests.py` that keeps it fixed.

Any script you would otherwise run by hand belongs in a management command: it
gets Django's settings and database loaded for free, and it is repeatable.

---

## Part 6 — The admin

Django's admin is a complete CRUD interface generated from your models. It is
the biggest single reason to choose Django, and it costs about ten lines an app.

### 6.1 A superuser

```bash
python manage.py createsuperuser
```

`seed` already made one: `admin@example.com` / `admin12345`. **Change that
before this is ever public.**

### 6.2 Registering models

```python
from django.contrib import admin
from .models import Category, Product, ProductImage

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
```

The `@admin.register(Model)` decorator form is used throughout, rather than
`admin.site.register(Model, ModelAdmin)` at the bottom of the file. Same result,
less repetition, and the class and its registration stay together.

What each option buys you:

| Option | Effect |
|---|---|
| `list_display` | the columns. Can include **methods**, like `product_count` |
| `list_filter` | the filter sidebar |
| `list_editable` | edit price/stock **straight from the list**, then Save |
| `search_fields` | a search box; `user__email` searches across a relationship |
| `prepopulated_fields` | fills the slug live as you type the name |
| `filter_horizontal` | a proper two-pane picker for many-to-many |
| `inlines` | edit child rows on the parent's page |
| `date_hierarchy` | the year/month/day drill-down bar |
| `raw_id_fields` | a search picker instead of a dropdown — essential once you have thousands of rows |
| `readonly_fields` | shown but not editable — used on `created`/`updated` |

`ProductImageInline` is the one to understand: it is how you edit the *reverse*
side of a foreign key. `ProductImage` has an FK to `Product`, so an inline lets
you add gallery shots on the product's own page instead of navigating to a
separate Images section.

### 6.3 Have a look

```bash
python manage.py runserver
```

<http://127.0.0.1:8000/admin/> — then, in order:

- **Categories** — the `product_count` column is a method, not a field. Click
  "Add category" and watch the slug fill in as you type.
- **Products** — filter in the sidebar, edit a price inline from the list,
  drill down by date, open one and add a gallery image through the inline.
- **Colours** — the `swatch` column renders a coloured circle via
  `format_html`. That is how you put HTML in an admin column safely; string
  concatenation there is an XSS hole.
- **Orders** — `OrderItemInline` with `raw_id_fields`, a `total_display` column
  formatting `KES 1,234.00`, and greyed-out read-only timestamps.
- **Payments** — deliberately read-only. It mirrors what Safaricom told us;
  editing it by hand would be falsifying a payment record.

That is Create / Read / Update / Delete without writing a single view.

---

## Part 7 — Views, URLs and the request flow

### 7.1 What happens when someone opens a page

```
browser  →  myproject/urls.py  →  <app>/urls.py  →  a view function
                                                       ↓
                                                    the ORM  →  database
                                                       ↓
                                                    render(template, context)
                                                       ↓
                                                    HTML back to the browser
```

### 7.2 Root URLs

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('accounts/', include('accounts.urls')),
    path('shop/', include('shop.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include('orders.urls')),
    path('payments/', include('payments.urls')),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('', include('core.urls')),          # ← LAST: it is a catch-all prefix
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

Two things you can get wrong here:

- **`core.urls` goes last**, because `''` matches everything. Django tries
  patterns top to bottom and takes the first match; put the catch-all first and
  it swallows the rest.
- **That last `if settings.DEBUG` block is dev-only.** Django's dev server
  serves uploaded photos so you can see them. In production your web server
  does it — Django is not built to serve files at volume.

### 7.3 App URLs and namespaces

```python
# shop/urls.py
app_name = 'shop'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('<slug:slug>/', views.product_detail, name='product_detail'),
]
```

`app_name` creates a namespace, so templates say
`{% url 'shop:product_detail' slug=product.slug %}` and two apps can both have
a view called `detail` without colliding. Only allauth's names
(`account_login`, `account_signup`, `account_logout`) are un-namespaced.

Never hard-code a path in a template. `{% url %}` looks the route up by name,
so changing `/shop/` to `/products/` is a one-line edit in `urls.py` rather
than a hunt through thirty templates.

> **The ordering trap.** `<slug:slug>/` under `/shop/` is a catch-all. If you
> later add `path('sale/', views.sale)`, it must go **above** the slug pattern —
> otherwise `/shop/sale/` matches the slug route, Django looks for a product
> with the slug "sale", and the shopper gets a 404.

### 7.4 A view, annotated

Every view takes `request` and returns a response.

```python
def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related(
            'images', 'sizes', 'colours'
        ),
        slug=slug, is_active=True,
    )

    return render(request, 'shop/product_detail.html', {
        'product': product,
        'related_products': Product.objects.filter(
            category=product.category, is_active=True
        ).exclude(pk=product.pk)[:4],
    })
```

- `get_object_or_404` fetches or raises 404. It replaces a
  `try/except DoesNotExist` in every view.
- `is_active=True` is in the lookup, not checked afterwards — a deactivated
  product is a 404, not a visible page with a hidden flag.
- The `select_related`/`prefetch_related` pair is Part 5.10's N+1 fix.
- `render(request, template, context)` — the context dict is what the template
  can see.

### 7.5 The listing view — filtering and pagination

`product_list` is the most involved view in the project, and it is all one
pattern: start with a queryset, narrow it per parameter, paginate at the end.

```python
products = Product.objects.filter(is_active=True).select_related('category')

query = request.GET.get('q', '').strip()
if query:
    products = products.filter(
        Q(name__icontains=query) | Q(description__icontains=query)
    )
```

`Q` objects let you write OR. Chained `.filter()` calls are AND.

**Querysets are lazy.** None of the filtering above touches the database. The
query runs only when the results are iterated — which is at the Paginator, once,
with every filter already applied.

```python
page = Paginator(products, PAGE_SIZE).get_page(request.GET.get('page'))
```

`get_page()` (not `.page()`) handles a junk page number by returning page 1
instead of raising. The URL is user input; treat it that way.

Two details worth copying:

```python
# Price bounds are applied independently, so a shopper can set just a
# ceiling without also having to pick a floor.
for param, lookup in (('min_price', 'price__gte'), ('max_price', 'price__lte')):
    raw = request.GET.get(param, '').strip()
    if raw:
        try:
            products = products.filter(**{lookup: float(raw)})
        except ValueError:
            pass                    # ?min_price=banana just does nothing
```

```python
# Only offer facet values that a live product actually carries, otherwise
# the sidebar advertises filters that return nothing.
'size_links': facet_links(
    request, 'size', Size.objects.filter(products__is_active=True).distinct()
),
```

And `facet_links()` builds each sidebar link by copying the current
querystring, toggling one value and dropping `page` — so filters combine
(`?size=xl&colour=navy`) instead of replacing each other, and switching a
filter never lands you on page 5 of a 2-page result.

---

## Part 8 — The shopping cart

### 8.1 Why there is no cart table

A cart is temporary and mostly abandoned. Give it a database table and you get
a table full of dead rows from people who never came back, plus a signup wall
in front of anyone who just wants to add a jacket.

So the cart lives in the **session** — a per-visitor store Django keys to a
cookie. Anonymous shoppers get a cart. There is nothing to clean up.

### 8.2 The `Cart` class

`cart/cart.py` wraps `request.session` so nothing else in the codebase pokes at
session keys directly:

```python
class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if cart is None:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart

    def add(self, product, quantity=1, override_quantity=False):
        key = str(product.id)
        if key not in self.cart:
            self.cart[key] = {'quantity': 0, 'price': str(product.price)}
        ...
        # Never hold more than exists; drop the line at zero.
        self.cart[key]['quantity'] = min(self.cart[key]['quantity'], product.stock)
        if self.cart[key]['quantity'] <= 0:
            del self.cart[key]
        self.save()

    def save(self):
        self.session.modified = True    # ← without this, nothing persists
```

Four things to notice:

1. **The key is `str(product.id)`.** Sessions serialise to JSON, and JSON
   object keys are always strings. An int key would come back as a string and
   your lookups would miss.
2. **The price is stored as `str(product.price)`.** JSON cannot encode a
   `Decimal`. It is converted back on the way out.
3. **`session.modified = True`** — Django only saves the session if it thinks
   it changed, and mutating a nested dict does not trip that detection.
4. **The price is copied in at add time**, so a price change while someone is
   shopping does not silently rewrite their cart.

The subtlest bug in the file is already fixed, with a comment:

```python
def __iter__(self):
    products = Product.objects.filter(id__in=self.cart.keys())

    # Copy each entry, not just the outer dict. A shallow copy would share
    # the nested dicts with the session, so the Decimal conversion below
    # would be written back into it — and the session is serialised as
    # JSON, which cannot encode a Decimal.
    cart = {key: dict(item) for key, item in self.cart.items()}
```

`{**self.cart}` would copy the outer dict but share the inner ones. Attaching a
`Decimal` then corrupts the session on the next request.

Making `Cart` iterable and giving it `__len__` is what lets templates write
`{% for item in cart %}` and `{{ cart|length }}` as if it were a list.

### 8.3 Add-to-cart with and without JavaScript

```python
@require_POST
def cart_add(request, product_id):
    ...
    if _is_ajax(request):
        return JsonResponse(_cart_payload(request, cart))
    messages.success(request, f'{product.name} added to your cart.')
    return redirect('cart:detail')
```

- **`@require_POST`** — adding to a cart changes state, so it must not be a
  GET. A GET link would fire from a link prefetcher or a crawler.
- **The view answers both ways.** With JavaScript, `static/js/shop.js`
  intercepts the submit, POSTs it and updates the header badge in place. With
  JavaScript off, the same form does a normal POST and redirect. That is
  **progressive enhancement**: the site works either way, and you never have
  two implementations of the same rule.

---

## Part 9 — Checkout and orders

### 9.1 The form

```python
class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['full_name', 'phone', 'email', 'county', 'town', 'street', 'notes']
```

A `ModelForm` builds itself from the model: fields, validation and saving all
come for free. You list the fields the *customer* fills in — `status`, `paid`
and `user` are set by code, so they are not in the form and cannot be forged by
posting extra parameters.

Custom validation goes in `clean_<field>`:

```python
PHONE_RE = re.compile(r'^(?:\+?254|0)?(7\d{8}|1\d{8})$')

def clean_phone(self):
    raw = re.sub(r'[\s\-()]', '', self.cleaned_data['phone'])
    match = PHONE_RE.match(raw)
    if not match:
        raise forms.ValidationError('Enter a valid phone number, e.g. 0712345678.')
    return f'0{match.group(1)}'
```

People type `0712 345 678`, `+254712345678` and `254712345678`. All three are
accepted and **normalised to one stored form**. Normalising at the boundary
means nothing downstream has to care about the variations.

### 9.2 The checkout view

```python
with transaction.atomic():
    order = form.save(commit=False)
    if request.user.is_authenticated:
        order.user = request.user
    ...
    order.save()

    # Prices come from the cart, not the product, so what the shopper
    # agreed to is what gets charged.
    OrderItem.objects.bulk_create([
        OrderItem(order=order, product=item['product'],
                  price=item['price'], quantity=item['quantity'])
        for item in cart
    ])
```

- **`transaction.atomic()`** — all of it commits or none of it does. Without
  it, a crash between saving the order and saving its lines leaves an order
  with no contents in your database, permanently.
- **`commit=False`** gives you the unsaved instance so you can attach the user
  and the coupon before it hits the database.
- **`bulk_create`** inserts every line in one query.

Before any of that, two guards: an empty cart bounces to the shop, and a cart
holding more than current stock bounces back with a message per item.

### 9.3 Stock is taken at payment, not at checkout

```python
# Stock is NOT taken here. It comes off when M-Pesa confirms,
# guarded by order.stock_applied, so an abandoned STK prompt does
# not hold inventory and a replayed callback cannot double-count.
```

Deduct at checkout and every shopper who opens the payment prompt and wanders
off has removed stock from your shop with nothing to show for it. Deducting on
confirmation ties inventory to money received.

Same reasoning for the cart: **it survives checkout and is cleared only on
success**, so a cancelled prompt leaves the shopper somewhere to retry from
rather than an empty cart and a bad memory.

### 9.4 Who is allowed to read an order

This is the security-shaped part of the project, and it is worth reading
carefully.

```python
def _owns_order(request, order):
    """A member's order is tied to the user, a guest's to their session."""
    if order.user_id:
        return request.user.is_authenticated and order.user_id == request.user.id
    return order.pk in request.session.get('guest_orders', [])
```

A signed-in customer is matched on `user_id`. A guest has no account, so their
claim is a list of order ids written into their session **by the checkout view,
at the moment the order is created** — the only point at which the claim is
known to be genuine:

```python
if not order.user_id:
    owned = request.session.get('guest_orders', [])
    owned.append(order.pk)
    request.session['guest_orders'] = owned[-20:]
```

If the claim were recorded later — say, on first visit to the order page —
anyone could walk `/payments/success/1/`, `/2/`, `/3/` and read every buyer's
name, phone number and home address.

`_owns_order` lives in `orders/views.py` and is **imported** by `payments`, not
copied. Two implementations of one security check is one too many; they drift,
and the drift is a hole.

---

## Part 10 — Paying with M-Pesa

### 10.1 What STK Push is

**Lipa na M-Pesa Online**, a.k.a. STK Push: your server asks Safaricom to make
a PIN prompt appear on the customer's phone. They enter their M-Pesa PIN;
Safaricom moves the money and then **POSTs the result back to your server**.

The critical structural point: the answer does not come back on the same HTTP
request. Your server sends a push, gets an acknowledgement, and the actual
verdict arrives later on a separate connection Safaricom opens to you. That is
what a **callback** is, and everything about this part of the design follows
from it.

### 10.2 Getting credentials

<https://developer.safaricom.co.ke>

1. Register and log in.
2. **My Apps → Add a new App**, tick **Lipa Na M-Pesa Sandbox**. That gives a
   **Consumer Key** and **Consumer Secret**.
3. **APIs → Lipa Na M-Pesa Online → Simulate** shows the sandbox **Shortcode**
   (174379) and the **Passkey**.
4. The same page lists sandbox test phone numbers and the test PIN.

Into `.env`:

```bash
MPESA_ENV=sandbox
MPESA_CONSUMER_KEY=...
MPESA_CONSUMER_SECRET=...
MPESA_SHORTCODE=174379
MPESA_PASSKEY=...
MPESA_CALLBACK_BASE_URL=          # filled in below
MPESA_CALLBACK_TOKEN=some-long-random-string
```

**Leave them blank and the site still works.** Checkout runs right up to the
payment step and then lands on the failure page with the reason. Nothing else
is affected, which is what makes this safe to clone and explore.

### 10.3 ngrok — letting Safaricom reach your laptop

Safaricom must POST to a **public https URL**. `127.0.0.1:8000` is not one.
[ngrok](https://ngrok.com) opens a public https address that tunnels to your
local port:

```bash
ngrok http 8000
```
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

Put that URL in **two** places in `.env`:

```bash
MPESA_CALLBACK_BASE_URL=https://abc123.ngrok-free.app
CSRF_TRUSTED_ORIGINS=https://abc123.ngrok-free.app
```

The second one is not optional. The page is now being served from a different
host, and without trusting that origin every POST on your own site fails CSRF
validation. Restart `runserver` after editing `.env`.

> The free ngrok URL changes every restart. Both settings need updating each
> time.

### 10.4 The Daraja client

`payments/daraja.py`, ~210 lines, no SDK — the surface needed is three HTTP
calls, and keeping them explicit makes the request and response shapes visible
when something goes wrong.

**Authentication** — an OAuth token, cached:

```python
TOKEN_CACHE_SECONDS = 3300      # Daraja's last ~3599s; expire early to
                                # avoid racing the boundary
```

Fetching a token on every request would be slow and rude. Caching it for its
full life would occasionally use one that expires mid-flight, so it is expired
early. The push also retries once on a 401, in case a cached token died anyway.

**Phone normalisation** — Daraja wants `2547XXXXXXXX` and nothing else:

```python
def normalise_phone(raw):
    """Convert the ways Kenyans actually type a number into 2547XXXXXXXX."""
    digits = re.sub(r'\D', '', str(raw))
    if digits.startswith('254'):   national = digits[3:]
    elif digits.startswith('0'):   national = digits[1:]
    elif len(digits) == 9:         national = digits
    else:                          return None
    if len(national) != 9 or national[0] not in '71':
        return None
    return f'254{national}'
```

Returns `None` rather than raising, so a bad number is a caller's decision, not
an exception in the middle of a checkout.

**The push itself:**

```python
payload = {
    'BusinessShortCode': settings.MPESA_SHORTCODE,
    'Password': _password(timestamp),      # base64(shortcode + passkey + timestamp)
    'Timestamp': timestamp,
    'TransactionType': 'CustomerPayBillOnline',
    'Amount': int(amount),                 # whole shillings — decimals are rejected
    'PartyA': msisdn,
    'PartyB': settings.MPESA_SHORTCODE,
    'PhoneNumber': msisdn,
    'CallBackURL': callback_url(),
    # Daraja caps these two; over-long values are rejected outright.
    'AccountReference': str(account_reference)[:12],
    'TransactionDesc': (description or settings.MPESA_TRANSACTION_DESC)[:13],
}
```

`Amount` must be a whole number, which is why `Order.get_mpesa_amount()` rounds
**up**:

```python
def get_mpesa_amount(self):
    """Daraja rejects decimals, so the charge is rounded up to whole shillings."""
    total = self.get_total()
    return max(1, int(total.to_integral_value(rounding='ROUND_CEILING')))
```

Up, not down — rounding down means undercharging on every order with cents.

### 10.5 The flow, end to end

```
cart
  └─> checkout form            name, phone, county, town, street
        └─> Order + OrderItem rows, one atomic transaction
              └─> payments:start        fires the STK push
                    └─> waiting page    polls payments:status every few seconds
                          ├── Safaricom POSTs payments:callback   ← the real answer
                          └── or the poll asks Daraja directly    ← the fallback
                                └─> order marked paid, stock taken, cart cleared
                                      └─> success / failed page
```

The waiting page polls because the callback might never arrive — tunnels drop.
`query_stk_status()` asks Daraja directly and **returns `None` on any failure**,
never raising, because it is polled from a page the shopper is watching: an
unconfigured Daraja should leave them waiting, not throw an error at them.

While the prompt is still on the handset, Daraja answers with `errorCode
500.001.1001` and no `ResultCode`. Only a `ResultCode` is a verdict; anything
else means keep waiting.

### 10.6 Why an unauthenticated callback is safe

Safaricom cannot log in to your site, so the callback endpoint is
`@csrf_exempt` and unauthenticated. Four things carry the weight:

1. **An unguessable URL.** The path carries `MPESA_CALLBACK_TOKEN`; a mismatch
   raises 404. That is why the token should be long and random.
2. **Lookup strictly by `CheckoutRequestID`.** Nothing in the body that names
   an order is trusted. A forged callback claiming "order 5 is paid" finds no
   payment row and does nothing.
3. **Idempotency.** An already-successful payment returns the acknowledgement
   and changes nothing. Safaricom retries; retries must be harmless.
4. **Always acknowledge.** Any reply other than `ResultCode: 0` makes Safaricom
   retry forever, so the view accepts the POST and works out the meaning itself.

The raw body is stored **before** anything is parsed:

```python
# Store the raw body before interpreting any of it.
payment.raw_callback = body
payment.save(update_fields=['raw_callback'])
```

A payload that is malformed or shaped differently than expected is still
debuggable afterwards. You cannot ask Safaricom to resend.

And the stock deduction is guarded:

```python
# stock_applied is the guard that makes a replayed callback harmless.
if not order.stock_applied:
    for item in order.items.select_related('product'):
        product = Product.objects.select_for_update().get(pk=item.product_id)
        product.stock = max(0, product.stock - item.quantity)
        product.save(update_fields=['stock'])
    order.stock_applied = True
```

`select_for_update()` locks the rows for the transaction, so two callbacks
arriving at once cannot both read the same stock figure and both write it back.

### 10.7 Testing the sandbox

1. `python manage.py runserver` in one terminal, `ngrok http 8000` in another.
2. Update both ngrok values in `.env`, restart the server.
3. Add something to the cart and check out using a **sandbox test number** from
   the Daraja portal.
4. Watch the ngrok terminal — you will see the inbound
   `POST /payments/callback/...` land. In the sandbox no real phone rings;
   Daraja resolves it for you.
5. The waiting page redirects itself to success or failure.

---

## Part 11 — User accounts

### 11.1 Why allauth

Django ships authentication, but not signup, email verification, password reset
or social login as finished flows. `django-allauth` is those flows.

```python
INSTALLED_APPS = [..., 'django.contrib.sites', 'allauth', 'allauth.account',
                  'allauth.socialaccount',
                  'allauth.socialaccount.providers.google',
                  'allauth.socialaccount.providers.facebook']

MIDDLEWARE = [..., 'allauth.account.middleware.AccountMiddleware']

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',            # username/password
    'allauth.account.auth_backends.AuthenticationBackend',  # email + social
]

ACCOUNT_LOGIN_METHODS = {'email'}                  # sign in with email, not username
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'                # fine for dev, revisit for prod
LOGIN_REDIRECT_URL = 'core:home'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

The console email backend prints password-reset mails into your terminal, so
you can complete the flow in development without an SMTP server.

To restyle allauth's pages, put your own file at the same path — `DIRS` is
searched before app templates. Note the folder is `account/` (singular) for
allauth, while this project's own account pages are in `accounts/` (plural).
That is confusing, and it is allauth's naming, not a typo.

### 11.2 Profile via a signal

```python
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
```

A **signal** is a hook that fires on an event. Every new user gets a profile
automatically, whether they came from the signup form, social login, the admin
or `createsuperuser`. Doing it in the signup view would only cover one of those
four.

`if created:` matters — without it you would try to make a second profile every
time a user row is saved.

### 11.3 One default address, enforced in the model

```python
def save(self, *args, **kwargs):
    super().save(*args, **kwargs)
    # Exactly one default per user, enforced by demoting the others.
    if self.is_default:
        Address.objects.filter(user=self.user).exclude(pk=self.pk).update(
            is_default=False
        )
```

In the model, not the view, so the rule holds for the admin and the shell too.

### 11.4 Social login without a database fixture

The keys come from the environment, and a provider whose keys are absent is
**not registered at all**, so its button never renders:

```python
SOCIALACCOUNT_PROVIDERS = {}

if env('GOOGLE_CLIENT_ID') and env('GOOGLE_CLIENT_SECRET'):
    SOCIALACCOUNT_PROVIDERS['google'] = {
        'APP': {'client_id': env('GOOGLE_CLIENT_ID'),
                'secret': env('GOOGLE_CLIENT_SECRET'), 'key': ''},
        'SCOPE': ['profile', 'email'],
        # No refresh token: the shop only needs the identity at sign-in time.
        'AUTH_PARAMS': {'access_type': 'online'},
    }
```

That is what makes it safe to ship with the keys unset — no half-configured
button that errors when clicked, and no `SocialApp` row to create in the admin
on a fresh clone.

One subtlety worth knowing about:

```python
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
```

Someone who registered with a password and later clicks "Continue with Google"
should land in their existing account, not hit "an account already exists with
this email". allauth only links the two when the provider says the address is
verified — true for Google, not for Facebook, which is why a Facebook collision
still routes through the normal error path.

Where to get keys: Google at
<https://console.cloud.google.com/apis/credentials> (Create Credentials → OAuth
client ID → Web application; redirect URI
`http://localhost:8000/accounts/google/login/callback/`). Facebook at
<https://developers.facebook.com/apps> (add the Facebook Login product;
Facebook requires https, so use the ngrok host when testing locally).

---

## Part 12 — Tests

```bash
python manage.py test
```
```
Ran 83 tests in 1.590s

OK
```

| App | Tests | Covers |
|---|---|---|
| `shop` | 23 | listing, search, price bounds, size/colour facets, detail access, seed integrity |
| `orders` | 24 | checkout, stock timing, totals, coupons, phone normalisation, order ownership |
| `payments` | 14 | phone parsing, STK push, callback idempotency, token rejection |
| `accounts` | 10 | profile signal, one-default-address rule, cross-user access |
| `core` | 8 | home page, deal of the week, contact form |
| `cart` | 4 | session serialisation, stock capping, captured prices |

Each test runs against a **fresh throwaway database**, created and destroyed
per run. Your real data is never touched.

The ones worth keeping green are the security-shaped ones:

- a second user must get a **404** on someone else's order and address
- a callback with a **bad token** must 404
- a **replayed callback** must not take stock twice

Those are the tests that catch a refactor quietly opening a hole.

One settings trick makes the suite fast:

```python
if 'test' in sys.argv:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
```

Django's default hasher is deliberately slow — correct in production, and it
was costing this suite most of its runtime (~31s down to under 2s). Tests never
assert on hash strength. **This applies only under `manage.py test`.**

Run a subset:

```bash
python manage.py test shop
python manage.py test shop.tests.SeedDataTests
```

---

## Part 13 — Running it day to day

```bash
source .venv/bin/activate           # first, every new terminal

python manage.py runserver          # dev server at 127.0.0.1:8000
python manage.py check              # system checks, no server needed
python manage.py makemigrations     # after editing any models.py
python manage.py migrate            # apply migrations
python manage.py seed               # demo data — safe to re-run
python manage.py seed --flush       # wipe products/categories first
python manage.py createsuperuser
python manage.py shell              # a Python REPL with Django loaded
python manage.py test               # all 83
python manage.py findstatic css/style.css     # debug a missing asset
python manage.py collectstatic      # deploy only → staticfiles/
ngrok http 8000                     # public https url for the M-Pesa callback
```

**Setting up a fresh clone from scratch:**

```bash
git clone <url> && cd Fashion-Shop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                # then fill it in
python manage.py migrate
python manage.py seed
python manage.py runserver
```

Six commands and you have a running shop with 20 products.

---

## Part 14 — When it breaks

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'django'` | virtualenv not active | `source .venv/bin/activate` |
| `no such table: shop_product` | migrations never applied | `python manage.py migrate` |
| `You have N unapplied migration(s)` | someone else added a migration | `python manage.py migrate` |
| Model changed but nothing happened | forgot the migration | `makemigrations` **then** `migrate` |
| `Invalid block tag 'static'` | missing `{% load static %}` | add it as the template's first line |
| `NoReverseMatch` | wrong url name or missing namespace | it is `shop:product_detail`, not `product_detail` |
| CSS loads but images 404 | wrong folder name | it is `img/`, not `images/` |
| Uploaded photos 404 | media not served | the `if settings.DEBUG:` block in `myproject/urls.py` |
| `CSRF verification failed` | new host (ngrok) not trusted | add it to `CSRF_TRUSTED_ORIGINS`, restart |
| `SuspiciousOperation: Invalid HTTP_HOST` | host not allowed | add it to `ALLOWED_HOSTS` |
| Form silently does nothing | missing `{% csrf_token %}` | add it inside every POST form |
| `TemplateDoesNotExist` | path wrong or app not in `INSTALLED_APPS` | check both |
| `ImproperlyConfigured: Pillow` | `pillow` missing | `pip install pillow` |
| Product page 404s | product `is_active=False` | the detail view filters on it |
| Test client 400s | `testserver` not in `ALLOWED_HOSTS` | `@override_settings(ALLOWED_HOSTS=['testserver'])` |
| M-Pesa: "MPESA_CALLBACK_BASE_URL is not set" | ngrok URL missing | set it in `.env`, restart |
| M-Pesa: callback never arrives | ngrok restarted, URL changed | update `.env`, restart |

**How to read a Django traceback:** with `DEBUG=True` the browser shows the
full stack. Read it **bottom up** — the last line is the actual error. Then
find the topmost frame that is *your* file, not Django's or a package's. That
is nearly always where the mistake is.

---

## Part 15 — Before it goes live

- [ ] `DEBUG=False` in the production `.env`
- [ ] A fresh 50-character `SECRET_KEY`, never the dev one
- [ ] `ALLOWED_HOSTS` set to the real domain
- [ ] **Change the seeded `admin12345` password**
- [ ] Move from SQLite to PostgreSQL
- [ ] `python manage.py collectstatic`, and let the web server serve `staticfiles/`
- [ ] Real SMTP instead of the console email backend
- [ ] `MPESA_ENV=production` with production Daraja credentials
- [ ] `MPESA_CALLBACK_BASE_URL` on the real https domain, and a long random
      `MPESA_CALLBACK_TOKEN`
- [ ] `ACCOUNT_EMAIL_VERIFICATION = 'mandatory'` if you care about real addresses
- [ ] `python manage.py check --deploy` — Django audits its own settings
- [ ] Back up the database and `media/`
- [ ] Keep the Colorlib attribution in the footer (CC BY 3.0)

The hardening itself is already automatic:

```python
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    ...
```

It is off in development because the dev server is plain http and these would
make it unusable. Nothing to remember at deploy time — flipping `DEBUG` turns
them all on.

---

## The ideas worth carrying to your next project

1. **Virtual environment, always.** And `requirements.txt` with pinned versions.
2. **Secrets in `.env`, never in git.** Commit `.env.example` so the required
   keys stay documented without the values.
3. **Never edit a vendored theme.** Add your own file and load it last.
4. **`DecimalField` for money.** Never `Float`.
5. **Freeze prices at purchase.** History must not change under you.
6. **Put rules in the model.** `save()` and properties hold for the admin, the
   shell and every view; a rule in one view does not.
7. **Choose `on_delete` deliberately.** `PROTECT` around sales history,
   `SET_NULL` where the record must outlive the reference.
8. **`select_related` / `prefetch_related`** the moment a template loops over a
   relation.
9. **Compute what can be computed.** A stored total can go stale; a computed
   one cannot.
10. **Never trust an id from a URL.** Check ownership on every view that shows
    someone's data — and write exactly one implementation of that check.
11. **Make retries harmless.** Anything a third party can send twice needs an
    idempotency guard.
12. **Test the security-shaped things.** They are the ones a refactor breaks
    silently.
