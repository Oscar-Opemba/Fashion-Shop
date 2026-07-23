# Architecture

A Django storefront built on the MaleFashion HTML theme. Django 6.0.7, SQLite,
session-based cart, guest checkout, and M-Pesa payment through Safaricom's
Daraja API (STK Push).

- **~2,000 lines** of Python (excluding migrations and the virtualenv)
- **2,020 lines** across 31 templates
- **6 apps**, 11 models, 111 static files, 31 uploaded media files

---

## 1. Directory tree

```
Fashion-Shop/
│
├── manage.py                          22   Django CLI entrypoint
├── db.sqlite3                              5 categories, 20 products, 1 superuser
├── requirements.txt                        19 pinned packages
├── README.md
├── ARCHITECTURE.md                         this file
│
├── .env                                    secrets — GITIGNORED, never commit
├── .env.example                            tracked template of the above
├── .gitignore
│
├── myproject/                              ── PROJECT CONFIG ──
│   ├── __init__.py
│   ├── settings.py                   341   env-driven config (see §3)
│   ├── urls.py                        23   root URL routing
│   ├── wsgi.py                        16   sync deployment entrypoint
│   └── asgi.py                        16   async deployment entrypoint
│
├── core/                                   ── SITE-WIDE PAGES ── (no models)
│   ├── __init__.py
│   ├── apps.py                             CoreConfig
│   ├── urls.py                        11   app_name='core' — home, about, contact
│   ├── views.py                       24   home() queries shop for the homepage
│   └── migrations/__init__.py              no migrations — app owns no models
│
├── shop/                                ── PRODUCTS — the domain center ──
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                     140   Category, Product, ProductImage,
│   │                                       Review, WishlistItem
│   ├── views.py                      186   product_list, product_detail,
│   │                                       review_add, wishlist_toggle, wishlist
│   ├── forms.py                       16   ReviewForm
│   ├── admin.py                       40   4 x @admin.register + 1 plain register
│   ├── urls.py                        13   app_name='shop'
│   ├── context_processors.py          14   nav_categories + wishlist_count,
│   │                                       injected into EVERY template
│   ├── migrations/
│   │   ├── __init__.py
│   │   └── 0001_initial.py
│   └── management/
│       ├── __init__.py
│       └── commands/
│           ├── __init__.py
│           └── seed.py               155   `manage.py seed` — repeatable demo data
│
├── cart/                                   ── SESSION CART ── (no models)
│   ├── __init__.py
│   ├── apps.py
│   ├── cart.py                        91   Cart class — the whole shopping cart,
│   │                                       stored in request.session
│   ├── views.py                       76   AJAX-aware add/remove/clear/detail
│   ├── context_processors.py           6   `cart` in every template (header badge)
│   ├── urls.py                        12   app_name='cart'
│   ├── tests.py                       49   ✅ HAS TESTS
│   └── migrations/__init__.py              no migrations — nothing persisted
│
├── orders/                                 ── CHECKOUT & ORDERS ──
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                      97   Coupon, Order, OrderItem
│   ├── views.py                      203   checkout, order_placed, coupon
│   │                                       apply/remove, history, detail
│   ├── forms.py                       83   OrderCreateForm, CouponApplyForm
│   ├── admin.py                       32   Order + Coupon admin
│   ├── urls.py                        14   app_name='orders'
│   └── migrations/
│       ├── __init__.py
│       ├── 0001_initial.py
│       └── 0002_remove_order_paid_...py    dropped the payment fields
│
├── accounts/                               ── USER PROFILES ──
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                      48   Profile, Address
│   ├── views.py                       76   profile + address CRUD, all @login_required
│   ├── forms.py                       51   ProfileForm, AddressForm
│   ├── admin.py                       16
│   ├── urls.py                        11   app_name='accounts'
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py
│
├── templates/                              ── 28 FILES, 1,524 LINES ──
│   ├── base.html                      60   the skeleton every page extends
│   │
│   ├── includes/                           reusable partials
│   │   ├── header.html                83   nav, cart badge, account menu
│   │   ├── footer.html                60
│   │   ├── offcanvas.html             33   mobile slide-out menu
│   │   ├── product_card.html          39   ⚠️ MODIFIED — one card, used everywhere
│   │   ├── breadcrumb.html            16
│   │   ├── messages.html              12   renders alert-{{ message.tags }}
│   │   └── search_modal.html           9
│   │
│   ├── core/
│   │   ├── home.html                 126   ⚠️ MODIFIED — hero, categories, featured
│   │   ├── about.html                 34
│   │   └── contact.html               37
│   │
│   ├── shop/
│   │   ├── product_detail.html       176   largest template — gallery, reviews
│   │   ├── product_list.html         139   ⚠️ MODIFIED — filters, sorting
│   │   └── wishlist.html              30
│   │
│   ├── cart/
│   │   ├── detail.html                90
│   │   └── _summary.html               9   fragment — underscore = not a page
│   │
│   ├── orders/
│   │   ├── checkout.html              97
│   │   ├── placed.html                38   order confirmation
│   │   ├── detail.html                77
│   │   └── history.html               38
│   │
│   ├── accounts/                           YOUR views
│   │   ├── profile.html               61
│   │   ├── address_form.html          37
│   │   └── address_confirm_delete.html 24
│   │
│   └── account/                            ALLAUTH overrides (note: singular)
│       ├── base_entrance.html         17   shared frame for login/signup
│       ├── login.html                 31
│       └── signup.html                29
│
├── static/                                 ── 106 FILES — Ashion theme ──
│   ├── css/                           10   bootstrap.min, style, owl.carousel,
│   │                                       magnific-popup, nice-select, slicknav,
│   │                                       font-awesome, elegant-icons,
│   │                                       storefront.css (the only additions)
│   ├── js/                            11   jquery-3.3.1, bootstrap, owl.carousel,
│   │                                       mixitup, magnific-popup, nicescroll,
│   │                                       countdown, slicknav, nice-select,
│   │                                       main.js, shop.js (yours)
│   ├── fonts/                         10   FontAwesome + ElegantIcons
│   └── img/                                note: img/ not images/
│       ├── (root)                      5   logo, footer-logo, payment,
│       │                                   breadcrumb-bg, product-sale
│       ├── product/                   14
│       ├── shop-details/               9
│       ├── blog/                       9  (+ blog/details/ 2)
│       ├── clients/                    8
│       ├── about/                      7
│       ├── instagram/                  6
│       ├── icon/                       5
│       ├── shopping-cart/              4
│       ├── banner/                     3
│       └── hero/                       2
│
├── media/                                  ── USER UPLOADS — 25 files ──
│   ├── products/                      20   one per product
│   └── categories/                     5   one per category
│
├── .idea/                                  PyCharm config (partly gitignored)
└── .claude/settings.local.json             Claude Code project settings
```

**Not on disk but expected later:** `staticfiles/` — created by `collectstatic`
at deploy time, gitignored.

---

## 2. Data model

10 models across 3 apps. `core` and `cart` deliberately own none.

### shop (`shop/models.py`, 140 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `Category` | `name` (unique), `slug` (auto), `image` | 5 rows |
| `Product` | `category` FK **PROTECT**, `name`, `slug`, `price` Decimal(10,2), `stock`, `image`, `is_active`, `created`, M2M `sizes`/`colours` | 20 rows; DB indexes on `slug` and `-created` |
| `ProductImage` | `product` FK CASCADE, `image`, `alt` | gallery; 3 rows (Camel Crew Sweatshirt) |
| `Size` | `name` (unique), `slug` (auto), `position` | 8 rows, XS-4XL; `position` drives sidebar order |
| `Colour` | `name` (unique), `slug` (auto), `hex_value` | 10 rows; rendered as an inline background |
| `Review` | `product` FK, `user` FK, `rating` (choices), `comment` | UniqueConstraint(user, product); **0 rows** |
| `WishlistItem` | `user` FK, `product` FK, `added` | UniqueConstraint(user, product); **0 rows** |

### orders (`orders/models.py`, 97 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `Coupon` | `code` (unique), `discount_percent`, `valid_from`/`valid_to`, `active` | `is_valid()` checks the window |
| `Order` | `user` FK **nullable** → guest checkout; `full_name`, `phone`, `email`, `county`, `town`, `street`, `notes`; `coupon` FK; `discount_percent`; `status` (choices) | money methods: `get_subtotal()`, `get_discount()`, `get_total()` |
| `OrderItem` | `order` FK CASCADE, `product` FK **PROTECT**, `price`, `quantity` | `price` is a **snapshot** — later price changes don't rewrite history |

### accounts (`accounts/models.py`, 48 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `Profile` | `user` OneToOne, `phone`, `avatar` | |
| `Address` | `user` FK, `label`, `full_name`, `county`, `town`, `street`, `is_default` | overrides `save()` to keep one default per user |

### Deletion policy

- **PROTECT** — `Product.category`, `OrderItem.product`. Blocks destroying
  anything referenced by purchase history.
- **CASCADE** — `ProductImage`, `Review`, `WishlistItem`, `OrderItem.order`.
  Genuinely dependent rows.
- **SET_NULL / nullable** — `Order.user`, so guest orders survive.

---

## 3. Configuration (`myproject/settings.py`, 341 LOC)

Read top to bottom, the file is organised in blocks:

| Lines | Block | Contents |
|---|---|---|
| 8–28 | env loading | `python-dotenv` + three helpers: `env()`, `env_bool()`, `env_list()` |
| 31–39 | secrets/hosts | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` |
| 44–67 | `INSTALLED_APPS` | django · third-party · local, in that order |
| 69–80 | middleware | + `allauth.account.middleware.AccountMiddleware` |
| 82–99 | templates | `DIRS=[BASE_DIR/'templates']`, `APP_DIRS=True`, 2 custom context processors |
| 105–111 | database | SQLite at `BASE_DIR/'db.sqlite3'` |
| 125–131 | i18n | `TIME_ZONE = 'Africa/Nairobi'`, `USE_TZ = True` |
| 136–143 | static/media | see §5 |
| 148–165 | allauth | `SITE_ID=1`, login by **email**, no verification, console mail backend |
| 173–177 | messages | remaps `ERROR` → `danger` so Bootstrap alert classes work |
| 183–192 | prod hardening | inside `if not DEBUG:` — self-activating on deploy |
| 196–197 | crispy forms | bootstrap4 pack |
| 200–211 | CKEditor 5 | rich text for product descriptions |
| 341 | cart | `CART_SESSION_ID = 'cart'` |

**Env-var convention:** the course teaches `python-decouple` / `config('X')`.
This project uses `python-dotenv` instead — write `env('X')`, `env_bool('X')`,
or `env_list('X')`. Do not add decouple; it would duplicate the job.

---

## 4. Request flow

### URL mounting (`myproject/urls.py`)

```
/admin/         django admin
/accounts/      allauth.urls, then accounts.urls
/shop/          shop.urls
/cart/          cart.urls
/orders/        orders.urls
/payments/      payments.urls
/ckeditor5/     django_ckeditor_5.urls
/               core.urls        ← LAST: it is a catch-all prefix
+ media served by staticfiles when DEBUG
```

Every app sets `app_name`, so all reverses are namespaced:
`{% url 'core:home' %}`, `{% url 'shop:product_detail' slug=... %}`.
Only allauth's own names (`account_login`, `account_signup`) are bare.

**Ordering trap** in `shop/urls.py`: the literal `wishlist/` route is
declared *before* `<slug:slug>/`. Django matches top-down, so a slug catch-all
placed first would swallow `/shop/wishlist/`.

### The purchase path

```
browse            /shop/                      shop.product_list
                  /shop/<slug>/               shop.product_detail
add to cart       POST /cart/add/<id>/        cart.cart_add        (AJAX)
                  → Cart.add() mutates request.session
review cart       /cart/                      cart.cart_detail
                  POST /orders/coupon/apply/  orders.coupon_apply  (session)
checkout          /orders/checkout/           orders.checkout
                  → creates Order + OrderItem rows (price snapshot)
                    inside one @transaction.atomic block.
                    Stock is NOT taken here.
pay               /payments/start/<id>/       payments.start   → STK push
                  /payments/waiting/<id>/     payments.waiting
                  → polls /payments/status/<id>/ every few seconds
callback          POST /payments/callback/<token>/  payments.callback
                  → Safaricom; marks paid, takes stock under
                    Order.stock_applied, clears cart + coupon
confirm           /payments/success/<id>/     payments.success
                  /payments/failed/<id>/      payments.failed
```

Stock moves at the callback, not at checkout, so an abandoned STK prompt holds
no inventory and a replayed callback cannot take the same stock twice.

### Who may read an order

`orders/views.py:_owns_order()` is the single gate, imported by `payments`
rather than duplicated there. A member's order is matched
on `user_id`; a guest's on a list of order ids written into their session by
`checkout()` at the moment the order is created — the only point at which the
claim is known to be genuine. Anything else would let someone walk order ids
and read another buyer's name, phone and address.

---

## 5. Static, media, templates

| Setting | Value | Meaning |
|---|---|---|
| `STATIC_URL` | `'static/'` | URL prefix |
| `STATICFILES_DIRS` | `[BASE_DIR/'static']` | where dev looks |
| `STATIC_ROOT` | `BASE_DIR/'staticfiles'` | `collectstatic` target (not yet created) |
| `MEDIA_URL` | `'media/'` | uploads prefix |
| `MEDIA_ROOT` | `BASE_DIR/'media'` | uploads on disk |

Images live under `static/img/`, **not** `static/images/` — match the theme's
own naming. So `{% static 'img/logo.png' %}`.

Every template referencing assets carries `{% load static %}`. Verified: zero
hardcoded `href="css/..."` paths, zero hardcoded `.html` links, and all 29
distinct asset references on rendered pages resolve to real files.

### Template inheritance

```
base.html
├── blocks: title · meta_description · extra_css · breadcrumb
│           content · extra_js
├── includes: offcanvas · header · messages · footer · search_modal
│
├── 20 page templates  {% extends 'base.html' %}
└── account/base_entrance.html          ← two-level inheritance
    ├── account/login.html
    └── account/signup.html
```

### Context processors — data on every page

| Processor | Injects | Why |
|---|---|---|
| `cart.context_processors.cart` | `cart` | header item count + running total |
| `shop.context_processors.shop` | `nav_categories`, `wishlist_count` | nav menu + wishlist badge |

These exist so apps can share data with templates **without importing each
other**, which is what keeps the dependency graph acyclic.

---

## 6. Dependency graph

```
        core ──────┐
                   ▼
   cart ────────► shop ◄──── orders
                                   ▲
                             accounts (users/addresses)
```

`shop` is the root; nothing imports upward. `orders` reads `shop` (to
snapshot prices and take stock) and `cart`, and nothing reads `orders`.

`core/views.py` imports `shop.models`, which makes `core` the least reusable
app. That is deliberate for a homepage, but it means `core` cannot travel alone.

**If `shop` ever imports from `core`, startup breaks with a circular
import.** Use a context processor instead.

---

## 7. Conventions worth keeping

- **Money is `DecimalField(max_digits=10, decimal_places=2)`** everywhere.
  Never `FloatField` — binary floats round wrong on prices.
- **Purchase history is immutable.** `OrderItem` snapshots `price` at checkout,
  and `PROTECT` prevents deleting a product that appears in an order.
- **Secrets only via `.env`.** `.gitignore` ignores `.env` and `.env.*` while
  keeping `.env.example` tracked, so the required keys stay documented without
  the values.
- **Production hardening is automatic** — the `if not DEBUG:` block at
  `settings.py:183` switches on by itself; nothing to remember at deploy.
- **Message tags are Bootstrap names.** `MESSAGE_TAGS` remaps Django's `error`
  to `danger` so `includes/messages.html` can render `alert-{{ message.tags }}`
  directly.
- **Fragments are underscore-prefixed** (`cart/_summary.html`) to distinguish
  them from page templates.
- **Admin uses `@admin.register(Model)`**, not `admin.site.register(Model)` —
  the decorator form allows an attached `ModelAdmin`.

---

## 8. Current state & gaps

### Verified working

`manage.py check` → no issues. 0 unapplied migrations, 0 pending model changes.
Route sweep: `/`, `/about/`, `/contact/`, `/shop/`, `/shop/<slug>/`, `/cart/`,
`/accounts/login/`, `/accounts/signup/` → **200**; `/orders/`,
`/accounts/profile/`, `/admin/` → **302** to login (correct — login-gated).

### Gaps

| Gap | Impact |
|---|---|
| Only one product has a gallery | the theme photographed just one item from several angles; the other 19 fall back to their single shot |
| Size/colour are not variants | stock is per product, so the cart does not record which size was picked |
| Shoes carry no sizes | they need a numeric run; XS-4XL would be nonsense on a sneaker |
| JS runtime unverified | files load, but carousel/offcanvas/mixitup init untested in a real browser |
| `ALLOWED_HOSTS` lacks `testserver` | Django's test client returns 400 unless you pass `Client(SERVER_NAME='localhost')` |

### Testing

`python manage.py test` runs 83 tests across every app:

| App | Covers |
|---|---|
| `cart` | session serialisation, stock capping, captured prices |
| `shop` | listing, search, price bounds, size/colour facets, detail access, seed integrity |
| `orders` | checkout, stock timing, totals, coupons, phone normalisation, order ownership |
| `payments` | phone parsing, STK push, callback idempotency, token rejection |
| `accounts` | profile signal, one-default-address rule, cross-user access |
| `core` | home page, deal of the week, contact form |

`PASSWORD_HASHERS` drops to MD5 when `test` is in `sys.argv`, which takes the
suite from ~31s to under 2s.

---

## 9. Common commands

```bash
python manage.py runserver          # dev server at 127.0.0.1:8000
python manage.py check              # system checks
python manage.py makemigrations     # after editing any models.py
python manage.py migrate            # apply migrations
python manage.py seed               # repeatable demo data (shop)
python manage.py createsuperuser
python manage.py findstatic css/style.css     # debug a missing asset
python manage.py collectstatic      # deploy only → staticfiles/
python manage.py test               # cart only
```
