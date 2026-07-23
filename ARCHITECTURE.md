# Architecture

A Django storefront built on the MaleFashion HTML theme. Django 6.0.7, SQLite,
session-based cart, guest checkout, and M-Pesa payment through Safaricom's
Daraja API (STK Push).

- **~3,500 lines** of Python (excluding migrations and the virtualenv)
- **2,031 lines** across 32 templates
- **7 apps**, 11 models, 111 static files, 28 uploaded media files

---

## 1. Directory tree

Line counts are for the file as it stands; they are a rough guide to where the
weight sits, not a contract.

```
Fashion-Shop/
│
├── manage.py                          22   Django CLI entrypoint
├── db.sqlite3                              GITIGNORED — demo data, see §8
├── requirements.txt                        19 pinned packages
├── README.md                               setup and how checkout works
├── ARCHITECTURE.md                         this file
├── MODULE.md                               beginner walkthrough, setup → payments
│
├── .env                                    secrets — GITIGNORED, never commit
├── .env.example                            tracked template of the above
├── .gitignore
│
├── myproject/                              ── PROJECT CONFIG ──
│   ├── settings.py                   365   env-driven config (see §3)
│   ├── urls.py                        24   root URL routing
│   ├── wsgi.py                        16   sync deployment entrypoint
│   └── asgi.py                        16   async deployment entrypoint
│
├── core/                                   ── SITE-WIDE PAGES ── (no models)
│   ├── urls.py                        11   app_name='core' — home, about, contact
│   ├── views.py                       50   home() queries shop for the homepage
│   ├── forms.py                       20   ContactForm
│   ├── tests.py                       74
│   └── migrations/__init__.py              no migrations — app owns no models
│
├── shop/                                   ── PRODUCTS — the domain center ──
│   ├── models.py                     118   Category, Product, ProductImage,
│   │                                       Size, Colour
│   ├── views.py                      157   product_list, product_detail,
│   │                                       facet_links, price_band_links
│   ├── admin.py                       53   4 × @admin.register + image inline
│   ├── urls.py                        10   app_name='shop'
│   ├── context_processors.py           6   nav_categories, on EVERY template
│   ├── tests.py                      221
│   ├── migrations/                         0001_initial, 0002 (drops Review /
│   │                                       WishlistItem), 0003 (Size, Colour)
│   └── management/commands/seed.py   438   `manage.py seed` — repeatable demo data
│
├── cart/                                   ── SESSION CART ── (no models)
│   ├── cart.py                        91   Cart class — the whole shopping cart,
│   │                                       stored in request.session
│   ├── views.py                       76   AJAX-aware add/remove/clear/detail
│   ├── context_processors.py           6   `cart` in every template (header badge)
│   ├── urls.py                        12   app_name='cart'
│   ├── tests.py                       49
│   └── migrations/__init__.py              no migrations — nothing persisted
│
├── orders/                                 ── CHECKOUT & ORDERS ──
│   ├── models.py                     108   Coupon, Order, OrderItem
│   ├── views.py                      185   checkout, coupon apply/remove,
│   │                                       history, detail, _owns_order
│   ├── forms.py                       83   OrderCreateForm, CouponApplyForm
│   ├── admin.py                       32   Order + Coupon admin
│   ├── urls.py                        13   app_name='orders'
│   ├── tests.py                      217
│   └── migrations/                         0001, 0002 (drops payment fields),
│                                           0003 (puts them back)
│
├── payments/                               ── M-PESA ──
│   ├── daraja.py                     212   STK Push client — no SDK, three
│   │                                       HTTP calls, token cached
│   ├── models.py                      44   MpesaPayment
│   ├── views.py                      253   start, waiting, status, callback,
│   │                                       success, failed, retry
│   ├── admin.py                       22   read-only — mirrors Daraja
│   ├── urls.py                        18   app_name='payments'
│   ├── tests.py                      184
│   └── migrations/0001_initial.py
│
├── accounts/                               ── USER PROFILES ──
│   ├── models.py                      48   Profile, Address
│   ├── views.py                       76   profile + address CRUD, all @login_required
│   ├── forms.py                       51   ProfileForm, AddressForm
│   ├── admin.py                       16
│   ├── urls.py                        12   app_name='accounts'
│   ├── tests.py                       92
│   └── migrations/0001_initial.py
│
├── templates/                              ── 32 FILES, 2,031 LINES ──
│   ├── base.html                      59   the skeleton every page extends
│   │
│   ├── includes/                           8 reusable partials
│   │   ├── header.html                79   nav, cart badge, account menu
│   │   ├── footer.html                60
│   │   ├── social_login.html          33   Google/Facebook buttons
│   │   ├── offcanvas.html             29   mobile slide-out menu
│   │   ├── product_card.html          24   one card, used everywhere
│   │   ├── breadcrumb.html            16
│   │   ├── messages.html              12   renders alert-{{ message.tags }}
│   │   └── search_modal.html           9
│   │
│   ├── core/
│   │   ├── home.html                 251   hero, categories, featured, deal
│   │   ├── about.html                206
│   │   └── contact.html               78
│   │
│   ├── shop/
│   │   ├── product_detail.html       197   gallery, sizes/colours, add to cart
│   │   └── product_list.html         194   search, category, price, size, colour
│   │
│   ├── cart/
│   │   ├── detail.html               107
│   │   └── _summary.html               9   fragment — underscore = not a page
│   │
│   ├── orders/
│   │   ├── checkout.html              97
│   │   ├── detail.html                80
│   │   └── history.html               44
│   │
│   ├── payments/
│   │   ├── waiting.html               84   polls status, then redirects
│   │   ├── failed.html                38
│   │   └── success.html               37
│   │
│   ├── accounts/                           our own views
│   │   ├── profile.html               61
│   │   ├── address_form.html          37
│   │   └── address_confirm_delete.html 24
│   │
│   ├── account/                            ALLAUTH overrides (note: singular)
│   │   ├── login.html                 33
│   │   ├── signup.html                31
│   │   └── base_entrance.html         17   shared frame for login/signup
│   │
│   └── socialaccount/                      allauth social overrides
│       ├── signup.html                32
│       ├── login.html                 30
│       ├── authentication_error.html  13
│       └── login_cancelled.html       10
│
├── static/                                 ── 111 FILES — theme + ours ──
│   ├── css/                           10   bootstrap.min, style, owl.carousel,
│   │                                       magnific-popup, nice-select, slicknav,
│   │                                       font-awesome, elegant-icons,
│   │                                       style.css.map, storefront.css (ours)
│   ├── js/                            11   jquery-3.3.1, bootstrap, owl.carousel,
│   │                                       mixitup, magnific-popup, nicescroll,
│   │                                       countdown, slicknav, nice-select,
│   │                                       main.js, shop.js (ours)
│   ├── fonts/                         10   FontAwesome + ElegantIcons
│   └── img/                           80   note: img/ not images/
│       ├── (root)                      5   logo, footer-logo, payment,
│       │                                   breadcrumb-bg, product-sale
│       ├── product/                   20   the 20 product shots (see §8)
│       ├── blog/                       9  (+ blog/details/ 2)
│       ├── shop-details/               9   one sweatshirt from four angles
│       ├── clients/                    8
│       ├── about/                      7
│       ├── instagram/                  6
│       ├── icon/                       5
│       ├── shopping-cart/              4
│       ├── banner/                     3
│       └── hero/                       2
│
├── media/                                  ── UPLOADS — GITIGNORED, 28 files ──
│   ├── products/                      23   20 main shots + 3 gallery shots
│   └── categories/                     5   one per category
│
├── .idea/                                  PyCharm config (gitignored)
├── .run/                                   PyCharm run configurations
└── .claude/settings.local.json             Claude Code project settings
```

**Not on disk but expected later:** `staticfiles/` — created by `collectstatic`
at deploy time, gitignored.

---

## 2. Data model

11 models across 4 apps. `core` and `cart` deliberately own none — `core` is
pages, and the cart lives in the session.

### shop (`shop/models.py`, 118 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `Category` | `name` (unique), `slug` (auto), `image` | 5 rows |
| `Product` | `category` FK **PROTECT**, `name`, `slug`, `description`, `price` Decimal(10,2), `stock`, `image`, `is_active`, `created`; M2M `sizes`, `colours` | 20 rows; DB indexes on `slug` and `-created` |
| `ProductImage` | `product` FK CASCADE, `image`, `alt` | extra gallery shots; 3 rows |
| `Size` | `name` (unique), `slug` (auto), `position` | 8 rows, XS–4XL; `position` drives sidebar order, since alphabetical would read 3XL, 4XL, L, M |
| `Colour` | `name` (unique), `slug` (auto), `hex_value` | 10 rows; rendered as an inline background so a colour can be added without touching CSS |

`Category` and `Product` both fill `slug` from `name` in `save()` when it is
blank. `Product.in_stock` is a property over `stock > 0`.

**Sizes and colours are not variants.** Stock is held on the product, not per
combination. They narrow the listing and populate the detail page; the cart
does not record which size was picked.

### orders (`orders/models.py`, 108 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `Coupon` | `code` (unique), `discount_percent` (1–100), `valid_from`/`valid_to`, `active` | `is_valid` property checks the window |
| `Order` | `user` FK **SET_NULL, nullable** → guest checkout; `full_name`, `phone`, `email`, `county`, `town`, `street`, `notes`; `coupon` FK SET_NULL; `discount_percent`; `status`; `paid`; `stock_applied` | money: `get_subtotal()`, `get_discount()`, `get_total()`, `get_mpesa_amount()` |
| `OrderItem` | `order` FK CASCADE, `product` FK **PROTECT**, `price`, `quantity` | `price` is a **snapshot** — later price changes don't rewrite history |

`Order.Status`: `pending` → `paid` → `shipped` → `delivered`, plus `cancelled`.
`processing` survives from the period when checkout completed without a payment
step, so older rows still render a label.

`get_mpesa_amount()` rounds **up** to whole shillings — Daraja rejects
decimals, and rounding down would undercharge.

### payments (`payments/models.py`, 44 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `MpesaPayment` | `order` OneToOne CASCADE, `phone`, `amount`, `merchant_request_id`, `checkout_request_id` (**unique**), `mpesa_receipt`, `result_code`, `result_desc`, `status`, `raw_callback` JSON | `checkout_request_id` is the callback's lookup key, hence unique and indexed |

`raw_callback` stores the untouched body **before** anything is parsed, so a
malformed or unexpected payload is still debuggable afterwards.

### accounts (`accounts/models.py`, 48 LOC)

| Model | Key fields | Notes |
|---|---|---|
| `Profile` | `user` OneToOne CASCADE, `phone`, `avatar` | created by a `post_save` signal on the user |
| `Address` | `user` FK CASCADE, `label`, `full_name`, `county`, `town`, `street`, `is_default` | overrides `save()` to demote a user's other defaults |

### Deletion policy

- **PROTECT** — `Product.category`, `OrderItem.product`. Blocks destroying
  anything referenced by purchase history.
- **CASCADE** — `ProductImage.product`, `OrderItem.order`, `MpesaPayment.order`,
  `Profile.user`, `Address.user`. Genuinely dependent rows.
- **SET_NULL** — `Order.user`, so guest orders and deleted users' orders
  survive; `Order.coupon`, so retiring a coupon does not delete orders.

---

## 3. Configuration (`myproject/settings.py`, 365 LOC)

The file is organised in commented blocks, top to bottom. Grep the banner
comment rather than trusting a line number:

| Block | Contents |
|---|---|
| env loading | `python-dotenv` + three helpers: `env()`, `env_bool()`, `env_list()` |
| secrets/hosts | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` |
| `Application definition` | `INSTALLED_APPS` — django · third-party · local, in that order |
| middleware | + `allauth.account.middleware.AccountMiddleware` |
| templates | `DIRS=[BASE_DIR/'templates']`, `APP_DIRS=True`, 2 custom context processors |
| `Database` | SQLite at `BASE_DIR/'db.sqlite3'` |
| `Password validation` | 4 validators, **and** the MD5 test hasher (below) |
| `Internationalization` | `TIME_ZONE = 'Africa/Nairobi'`, `USE_TZ = True` |
| `Static files and user uploads` | see §5 |
| `Authentication (django-allauth)` | `SITE_ID=1`, login by **email**, no verification, console mail backend |
| `Social login (Google, Facebook)` | credentials from env, not the admin's `SocialApp` table |
| `Messages` | remaps `ERROR` → `danger` so Bootstrap alert classes work |
| `Production hardening` | inside `if not DEBUG:` — self-activating on deploy |
| `Forms` | crispy, bootstrap4 pack |
| `Rich text editor` | CKEditor 5, used for product descriptions |
| `Shopping cart` | `CART_SESSION_ID = 'cart'` |
| `M-Pesa Daraja` | the seven `MPESA_*` keys |

**Env-var convention:** the course teaches `python-decouple` / `config('X')`.
This project uses `python-dotenv` instead — write `env('X')`, `env_bool('X')`,
or `env_list('X')`. Do not add decouple; it would duplicate the job.

**Test-only hasher.** `PASSWORD_HASHERS` drops to MD5 when `test` is in
`sys.argv`. The default PBKDF2 hasher is deliberately slow, which is right in
production and was costing the suite most of its runtime — ~31s down to under
2s. Tests never assert on hash strength.

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

**Ordering trap** in `shop/urls.py`: `<slug:slug>/` is a catch-all under
`/shop/`. Django matches top-down, so any literal route added later (`sale/`,
`new-in/`) must be declared **above** it or the slug pattern swallows it and
raises a 404 for a product that does not exist.

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
                  POST /payments/retry/<id>/  payments.retry
```

**Stock moves at the callback, not at checkout.** An abandoned STK prompt holds
no inventory, and `Order.stock_applied` means a callback Safaricom replays
cannot take the same stock twice. The cart likewise survives checkout and is
cleared only on success, so a cancelled prompt leaves somewhere to retry from.

### Why the callback is safe

Safaricom cannot authenticate to us, so the callback endpoint is `@csrf_exempt`
and unauthenticated. Four things carry the weight:

1. **An unguessable url.** The path carries `MPESA_CALLBACK_TOKEN`; a mismatch
   raises 404.
2. **Lookup strictly by `CheckoutRequestID`.** Nothing in the body that names
   an order is trusted.
3. **Idempotency.** An already-successful payment returns the acknowledgement
   and does nothing else.
4. **Always acknowledge.** Any reply other than `ResultCode: 0` makes Safaricom
   retry, so we accept the POST and sort out the meaning ourselves.

`payments.status` is a fallback for when the callback never lands — tunnels
drop. It asks Daraja directly, and `query_stk_status()` returns `None` rather
than raising on any failure, so an unconfigured Daraja leaves the shopper
waiting rather than erroring out.

### Who may read an order

`orders/views.py:_owns_order()` is the single gate, imported by `payments`
rather than duplicated there — two copies of a security check is one too many.
A member's order is matched on `user_id`; a guest's on a list of order ids
written into their session by `checkout()` at the moment the order is created,
the only point at which the claim is known to be genuine. Anything else would
let someone walk order ids and read another buyer's name, phone and address.

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

`media/` is gitignored, so a fresh clone has product rows pointing at photos
that were never checked in. `seed` handles this: `needs_image()` re-attaches a
photo whose file has gone missing rather than skipping the row, because the
cards would otherwise render with every image 404ing.

### Template inheritance

```
base.html
├── blocks: title · meta_description · extra_css · breadcrumb
│           content · extra_js
├── includes: offcanvas · header · messages · footer · search_modal
│
├── 15 page templates  {% extends 'base.html' %}
└── account/base_entrance.html          ← two-level inheritance
    ├── account/login.html
    └── account/signup.html
```

### Context processors — data on every page

| Processor | Injects | Why |
|---|---|---|
| `cart.context_processors.cart` | `cart` | header item count + running total |
| `shop.context_processors.shop` | `nav_categories` | the nav's category dropdown |

These exist so apps can share data with templates **without importing each
other**, which is what keeps the dependency graph acyclic.

---

## 6. Dependency graph

```
        core ─────────┐
                      ▼
        cart ───────► shop ◄─────── orders
                       ▲              ▲
                       │              │
                       └─ payments ───┘
                             │
        accounts ◄───────────┘ (only via seed; see below)
```

`shop` is the root; nothing it imports belongs to another app of ours.

- `cart`, `core`, `orders` and `payments` all read `shop.models`.
- `orders` reads `cart` (to turn a cart into order lines).
- `payments` reads `shop`, `cart`, and `orders` — including
  `orders.views._owns_order`. It is the top of the stack; nothing reads it.
- `accounts` imports no other app of ours.

The one edge that runs the "wrong" way is `shop/management/commands/seed.py`
importing `accounts.models.Profile`, to backfill profiles for users created
before the signal existed. It sits in a management command rather than in
`shop/models.py` or a view, so it never runs at import time and cannot form a
startup cycle.

**If `shop` ever imports from `core`, startup breaks with a circular import.**
Use a context processor instead.

---

## 7. Conventions worth keeping

- **Money is `DecimalField(max_digits=10, decimal_places=2)`** everywhere.
  Never `FloatField` — binary floats round wrong on prices.
- **Purchase history is immutable.** `OrderItem` snapshots `price` at checkout,
  and `PROTECT` prevents deleting a product that appears in an order.
- **Secrets only via `.env`.** `.gitignore` ignores `.env` and `.env.*` while
  keeping `.env.example` tracked, so the required keys stay documented without
  the values.
- **Production hardening is automatic** — the `if not DEBUG:` block switches on
  by itself; nothing to remember at deploy.
- **Message tags are Bootstrap names.** `MESSAGE_TAGS` remaps Django's `error`
  to `danger` so `includes/messages.html` can render `alert-{{ message.tags }}`
  directly.
- **Fragments are underscore-prefixed** (`cart/_summary.html`) to distinguish
  them from page templates.
- **Admin uses `@admin.register(Model)`**, not `admin.site.register(Model)` —
  the decorator form allows an attached `ModelAdmin`.
- **Seed data pairs a product with its photo by name, never by list position.**
  `sorted(glob('*.jpg'))` yields `product-1, product-10, product-11, …`, not
  numeric order. Pairing by index once mislabelled every product in the shop —
  a duffel bag that was a t-shirt. `shop/tests.py` guards this.
- **A filter that cannot be satisfied is not offered.** The size and colour
  facets list only values a live product carries, so the sidebar never
  advertises a filter that returns nothing.

---

## 8. Current state & gaps

### Verified working

`manage.py check` → no issues. 0 unapplied migrations, 0 pending model changes.
83 tests pass. Route sweep: `/`, `/about/`, `/contact/`, `/shop/`,
`/shop/<slug>/`, `/cart/`, `/accounts/login/`, `/accounts/signup/` → **200**;
`/orders/`, `/accounts/profile/`, `/admin/` → **302** to login (correct —
login-gated). Listing, facet filtering and the product gallery confirmed in
Chrome, not just by test client.

### Demo data (`db.sqlite3`, gitignored)

5 categories, 20 products, 3 gallery shots, 8 sizes, 10 colours. Rebuild from
nothing with `migrate` then `seed`; `seed` is idempotent and safe to re-run.

### Gaps

| Gap | Impact |
|---|---|
| `MPESA_*` keys unset | checkout runs to the payment step and then lands on the failure page with the reason. The rest of the site is unaffected. Needs Daraja credentials and a public https callback (`ngrok http 8000`) |
| Only one product has a gallery | the theme photographed just one item from several angles; the other 19 fall back to their single shot |
| Size/colour are not variants | stock is per product, so the cart does not record which size was picked |
| Shoes carry no sizes | they need a numeric run; XS–4XL would be nonsense on a sneaker |
| `Coupon` = 0 rows | the coupon box rejects everything until one is added in the admin |
| `Address` = 0 rows | checkout's default-address prefill has no data to exercise it by hand |
| `ALLOWED_HOSTS` lacks `testserver` | test classes using `self.client` need `@override_settings(ALLOWED_HOSTS=['testserver'])`, or `Client(headers={'host': 'localhost'})` |
| JS runtime only partly verified | pages, filters and the gallery work in Chrome; the carousel, countdown and mixitup init are still unexercised |

### Testing

`python manage.py test` runs **83 tests** in under 2 seconds:

| App | Tests | Covers |
|---|---|---|
| `shop` | 23 | listing, search, price bounds, size/colour facets, detail access, seed integrity |
| `orders` | 24 | checkout, stock timing, totals, coupons, phone normalisation, order ownership |
| `payments` | 14 | phone parsing, STK push, callback idempotency, token rejection |
| `accounts` | 10 | profile signal, one-default-address rule, cross-user access |
| `core` | 8 | home page, deal of the week, contact form |
| `cart` | 4 | session serialisation, stock capping, captured prices |

The security-shaped ones are worth keeping green: a second user must get a 404
on someone else's order and address, a bad callback token must 404, and a
replayed callback must not take stock twice.

---

## 9. Common commands

```bash
python manage.py runserver          # dev server at 127.0.0.1:8000
python manage.py check              # system checks
python manage.py makemigrations     # after editing any models.py
python manage.py migrate            # apply migrations
python manage.py seed               # repeatable demo data — safe to re-run
python manage.py seed --flush       # wipe products/categories first
python manage.py createsuperuser
python manage.py findstatic css/style.css     # debug a missing asset
python manage.py collectstatic      # deploy only → staticfiles/
python manage.py test               # all 83
python manage.py test shop.tests.SeedDataTests   # one class
ngrok http 8000                     # public https url for the M-Pesa callback
```
