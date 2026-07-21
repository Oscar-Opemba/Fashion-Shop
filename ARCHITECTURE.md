# Architecture

A mobile-first Django storefront with M-Pesa STK Push payments, built on the
Ashion HTML theme. Django 6.0.7, SQLite, session-based cart, guest checkout.

- **~2,540 lines** of Python (excluding migrations and the virtualenv)
- **1,524 lines** across 28 templates
- **6 apps**, 11 models, 106 static files, 25 uploaded media files

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
│   ├── settings.py                   232   env-driven config (see §3)
│   ├── urls.py                        24   root URL routing
│   ├── wsgi.py                        16   sync deployment entrypoint
│   └── asgi.py                        16   async deployment entrypoint
│
├── core/                                   ── SITE-WIDE PAGES ── (no models)
│   ├── __init__.py
│   ├── apps.py                             CoreConfig
│   ├── urls.py                        11   app_name='core' — home, about, contact
│   ├── views.py                       24   home() queries catalog for the homepage
│   └── migrations/__init__.py              no migrations — app owns no models
│
├── catalog/                                ── PRODUCTS — the domain center ──
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py                     140   Category, Product, ProductImage,
│   │                                       Review, WishlistItem
│   ├── views.py                      186   product_list, product_detail,
│   │                                       review_add, wishlist_toggle, wishlist
│   ├── forms.py                       16   ReviewForm
│   ├── admin.py                       40   4 x @admin.register + 1 plain register
│   ├── urls.py                        13   app_name='catalog'
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
│   ├── models.py                     105   Coupon, Order, OrderItem
│   ├── views.py                      169   checkout, coupon apply/remove,
│   │                                       order_history, order_detail
│   ├── forms.py                       78   OrderCreateForm, CouponApplyForm
│   ├── admin.py                       56   Order + Coupon admin
│   ├── urls.py                        13   app_name='orders'
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py
│
├── payments/                               ── M-PESA DARAJA ── (most involved)
│   ├── __init__.py
│   ├── apps.py
│   ├── daraja.py                     212   Safaricom API client — NO Django
│   │                                       imports, pure integration layer
│   ├── models.py                      44   MpesaPayment
│   ├── views.py                      264   start → waiting → status → success/
│   │                                       failed/retry, + callback webhook
│   ├── admin.py                       22
│   ├── urls.py                        18   app_name='payments'
│   ├── tests.py                      184   ✅ HAS TESTS (best-covered app)
│   └── migrations/
│       ├── __init__.py
│       └── 0001_initial.py
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
│   ├── catalog/
│   │   ├── product_detail.html       176   largest template — gallery, reviews
│   │   ├── product_list.html         139   ⚠️ MODIFIED — filters, sorting
│   │   └── wishlist.html              30
│   │
│   ├── cart/
│   │   ├── detail.html                90
│   │   └── _summary.html               9   fragment — underscore = not a page
│   │
│   ├── orders/
│   │   ├── checkout.html              99
│   │   ├── detail.html                70
│   │   └── history.html               44
│   │
│   ├── payments/
│   │   ├── waiting.html               84   polls the status endpoint via JS
│   │   ├── success.html               37
│   │   └── failed.html                38
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
│   ├── css/                           11   bootstrap.min, style, owl.carousel,
│   │                                       magnific-popup, nice-select, slicknav,
│   │                                       font-awesome, elegant-icons,
│   │                                       ⚠️ theme-dark.css (MODIFIED),
│   │                                       ⚠️ storefront.css (UNTRACKED)
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

11 models across 4 apps. `core` and `cart` deliberately own none.

### catalog (`catalog/models.py`, 140 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `Category` | `name` (unique), `slug` (auto), `image` | 5 rows |
| `Product` | `category` FK **PROTECT**, `name`, `slug`, `price` Decimal(10,2), `stock`, `image`, `is_active`, `created` | 20 rows; DB indexes on `slug` and `-created` |
| `ProductImage` | `product` FK CASCADE, `image`, `alt` | gallery; **0 rows** |
| `Review` | `product` FK, `user` FK, `rating` (choices), `comment` | UniqueConstraint(user, product); **0 rows** |
| `WishlistItem` | `user` FK, `product` FK, `added` | UniqueConstraint(user, product); **0 rows** |

### orders (`orders/models.py`, 105 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `Coupon` | `code` (unique), `discount_percent`, `valid_from`/`valid_to`, `active` | `is_valid()` checks the window |
| `Order` | `user` FK **nullable** → guest checkout; `full_name`, `phone`, `email`, `county`, `town`, `street`, `notes`; `coupon` FK; `discount_percent`; `status` (choices); `paid`; `stock_applied` | money methods: `get_subtotal()`, `get_discount()`, `get_total()`, `get_mpesa_amount()` |
| `OrderItem` | `order` FK CASCADE, `product` FK **PROTECT**, `price`, `quantity` | `price` is a **snapshot** — later price changes don't rewrite history |

### payments (`payments/models.py`, 44 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `MpesaPayment` | `order` **OneToOne**, `phone`, `amount` (int), `merchant_request_id`, `checkout_request_id` (unique), `mpesa_receipt`, `result_code`/`result_desc`, `status`, `raw_callback` JSON | `amount` is `PositiveIntegerField` — Daraja transacts whole shillings |

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

## 3. Configuration (`myproject/settings.py`, 232 LOC)

Read top to bottom, the file is organised in blocks:

| Lines | Block | Contents |
|---|---|---|
| 8–28 | env loading | `python-dotenv` + three helpers: `env()`, `env_bool()`, `env_list()` |
| 31–39 | secrets/hosts | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` (needed for ngrok) |
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
| 215 | cart | `CART_SESSION_ID = 'cart'` |
| 220–232 | M-Pesa | env, keys, shortcode, passkey, callback base URL + token |

**Env-var convention:** the course teaches `python-decouple` / `config('X')`.
This project uses `python-dotenv` instead — write `env('X')`, `env_bool('X')`,
or `env_list('X')`. Do not add decouple; it would duplicate the job.

---

## 4. Request flow

### URL mounting (`myproject/urls.py`)

```
/admin/         django admin
/accounts/      allauth.urls, then accounts.urls
/shop/          catalog.urls
/cart/          cart.urls
/orders/        orders.urls
/payments/      payments.urls
/ckeditor5/     django_ckeditor_5.urls
/               core.urls        ← LAST: it is a catch-all prefix
+ media served by staticfiles when DEBUG
```

Every app sets `app_name`, so all reverses are namespaced:
`{% url 'core:home' %}`, `{% url 'catalog:product_detail' slug=... %}`.
Only allauth's own names (`account_login`, `account_signup`) are bare.

**Ordering trap** in `catalog/urls.py`: the literal `wishlist/` route is
declared *before* `<slug:slug>/`. Django matches top-down, so a slug catch-all
placed first would swallow `/shop/wishlist/`.

### The purchase path

```
browse            /shop/                      catalog.product_list
                  /shop/<slug>/               catalog.product_detail
add to cart       POST /cart/add/<id>/        cart.cart_add        (AJAX)
                  → Cart.add() mutates request.session
review cart       /cart/                      cart.cart_detail
                  POST /orders/coupon/apply/  orders.coupon_apply  (session)
checkout          /orders/checkout/           orders.checkout
                  → creates Order + OrderItem rows (price snapshot)
pay               POST /payments/start/<id>/  payments.start
                  → daraja.stk_push() → phone prompt
                  /payments/waiting/<id>/     payments.waiting
                  → JS polls /payments/status/<id>/
       meanwhile: POST /payments/callback/<token>/   ← Safaricom, server-to-server
                  → _mark_paid() @transaction.atomic
resolve           /payments/success/<id>/  or  /failed/<id>/  or  retry
```

### Two entry points, one payment

`payments/views.py` handles both a **browser** polling `status()` and
Safaricom's **server** POSTing `callback()`. Both can settle the same payment,
so `_mark_paid()` is `@transaction.atomic` and the write is idempotent.
`callback` is `@csrf_exempt` (Safaricom has no CSRF token); its security comes
from the unguessable `<str:token>` segment matched against
`MPESA_CALLBACK_TOKEN`.

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
│           content · sticky_bar · extra_js
├── includes: offcanvas · header · messages · footer · search_modal
│
├── 19 page templates  {% extends 'base.html' %}
└── account/base_entrance.html          ← two-level inheritance
    ├── account/login.html
    └── account/signup.html
```

### Context processors — data on every page

| Processor | Injects | Why |
|---|---|---|
| `cart.context_processors.cart` | `cart` | header item count + running total |
| `catalog.context_processors.catalog` | `nav_categories`, `wishlist_count` | nav menu + wishlist badge |

These exist so apps can share data with templates **without importing each
other**, which is what keeps the dependency graph acyclic.

---

## 6. Dependency graph

```
        core ──────┐
                   ▼
   cart ────────► catalog ◄──── orders ◄──── payments
                                   ▲
                             accounts (users/addresses)
```

`catalog` is the root; nothing imports upward. `payments` depends only on
`orders`. `payments/daraja.py` imports no Django models at all — it is a pure
HTTP client and could be lifted into another project unchanged.

`core/views.py` imports `catalog.models`, which makes `core` the least reusable
app. That is deliberate for a homepage, but it means `core` cannot travel alone.

**If `catalog` ever imports from `core`, startup breaks with a circular
import.** Use a context processor instead.

---

## 7. Conventions worth keeping

- **Money is `DecimalField(max_digits=10, decimal_places=2)`** everywhere.
  Never `FloatField` — binary floats round wrong on prices. The single
  exception is `MpesaPayment.amount`, an integer because Daraja takes whole
  shillings.
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
| `Review` = 0 rows | `avg_rating` annotation is `None`; star ratings render empty |
| `ProductImage` = 0 rows | product galleries fall back to the single main image |
| `WishlistItem` = 0 rows | wishlist badge always 0 |
| No tests in `catalog`, `orders`, `accounts`, `core` | only `cart` (49) and `payments` (184) are covered |
| JS runtime unverified | files load, but carousel/offcanvas/mixitup init untested in a real browser |
| `ALLOWED_HOSTS` lacks `testserver` | Django's test client returns 400 unless you pass `Client(SERVER_NAME='localhost')` |

### Uncommitted work

```
 M catalog/management/commands/seed.py
 M catalog/models.py                     +22 lines, methods only — no migration needed
 M catalog/views.py
 M core/views.py
 M myproject/settings.py
 M static/css/theme-dark.css
 M templates/base.html
 M templates/catalog/product_list.html
 M templates/core/home.html
 M templates/includes/product_card.html
?? static/css/storefront.css             never committed
```

---

## 9. Common commands

```bash
python manage.py runserver          # dev server at 127.0.0.1:8000
python manage.py check              # system checks
python manage.py makemigrations     # after editing any models.py
python manage.py migrate            # apply migrations
python manage.py seed               # repeatable demo data (catalog)
python manage.py createsuperuser
python manage.py findstatic css/style.css     # debug a missing asset
python manage.py collectstatic      # deploy only → staticfiles/
python manage.py test               # cart + payments only
```

**M-Pesa in development** needs a public HTTPS URL Safaricom can POST back to.
Run ngrok, then set `MPESA_CALLBACK_BASE_URL` and add the host to
`CSRF_TRUSTED_ORIGINS` in `.env` — otherwise every POST fails the CSRF check.
