# Django E-commerce Storefront

![Top language](https://img.shields.io/github/languages/top/Oscar-Opemba/Fashion-Shop)
![Last commit](https://img.shields.io/github/last-commit/Oscar-Opemba/Fashion-Shop)

An online store built on Django 6, using the
[MaleFashion](https://themewagon.com/themes/free-bootstrap-4-html5-ecommerce-website-template-malefashion/)
ThemeWagon template as its front end.

New to the project? **[MODULE.md](MODULE.md)** walks through it from an empty
folder to a working shop. **[ARCHITECTURE.md](ARCHITECTURE.md)** is the
reference for how it all fits together.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then fill it in (see below)
python manage.py migrate
python manage.py seed         # sample categories, 20 products, a superuser
python manage.py runserver
```

The seed command creates `admin@example.com` / `admin12345`. **Change that
password before this goes anywhere real.**

## Layout

| App | What it owns |
|---|---|
| `core` | Home, about, contact, `base.html` and shared includes |
| `shop` | `Category`, `Product`, `ProductImage`, `Size`, `Colour` |
| `cart` | Session-backed cart — `cart/cart.py` holds the `Cart` class everything reuses |
| `orders` | `Order`, `OrderItem`, `Coupon`, checkout, order history |
| `payments` | `MpesaPayment`, the Daraja STK Push client and its callback |
| `accounts` | `Profile`, `Address`, allauth wiring |

## How checkout works

Payment is M-Pesa via Safaricom's Daraja API (Lipa na M-Pesa Online / STK
Push). Fill in the `MPESA_*` keys in `.env` — without them checkout still
works up to the point of payment and then lands on the failure page with the
reason, so the rest of the site stays usable.

```
cart  ->  checkout form (name, phone, county, town, street)
      ->  Order + OrderItem rows created in one transaction
      ->  payments:start fires the STK push
      ->  waiting page polls payments:status
      ->  Daraja POSTs the result to payments:callback
      ->  order marked paid, stock taken, cart cleared
```

- Line prices are copied from the cart, not re-read from the product, so what
  the shopper agreed to is what the order records.
- **Stock is taken when payment confirms, not at checkout.** An abandoned STK
  prompt holds no inventory. `Order.stock_applied` guards the decrement, so a
  callback Safaricom replays cannot take the same stock twice.
- The cart survives checkout and is cleared only on success, so a cancelled
  prompt leaves the shopper somewhere to retry from.
- The order starts at status `pending`; after payment it becomes `paid`, and
  you move it through `shipped` and `delivered` from the admin.
- The callback is unauthenticated on Safaricom's side. What protects it is an
  unguessable url segment (`MPESA_CALLBACK_TOKEN`), lookup strictly by
  `CheckoutRequestID`, and idempotency — nothing in the body that names an
  order is trusted.
- A guest's claim on an order is written into their session at the moment it is
  created, which is what lets them follow the payment without an account and
  stops anyone else reading it by walking order ids.

Safaricom must reach the callback on a public https url, so in development run
`ngrok http 8000` and put the forwarding url in `MPESA_CALLBACK_BASE_URL` and
`CSRF_TRUSTED_ORIGINS`.

## Reviews and saved items

Any signed-in account can review a product once — 1&ndash;5 stars and an
optional note. Posting again edits the first review rather than adding a
second, enforced by a unique constraint on `(product, user)`. Having bought
the product earns a **Verified purchase** badge, recomputed on every save.

`Product.rating_average` and `rating_count` are denormalised and recalculated
by a signal on `Review`, not by the model's `save()`/`delete()` — bulk deletes
from the admin and the cascade when an account is removed both skip those
methods, and either would leave a product advertising a rating nobody gave it.

Saved items are a per-account list (`WishlistItem`): a heart on every card, a
`/shop/saved/` page and a count in the header. The toggle answers JSON to
fetch and a redirect to a plain form post, so it works with JavaScript off.

## Tracking an order

Most orders here are placed as guests, so order history behind a login is not
enough. `/orders/track/` takes an order number and the phone the order was
placed with, and shows a timeline built from `OrderStatusEvent` rows — real
history, not a guess from the current status. Phone numbers are compared on
the last nine digits, so `0712345678`, `+254712345678` and `254712345678` are
the same person.

That pair is not a password and is not treated as one. The page and its JSON
sibling at `/orders/track/api/` return status, timeline and a line count, and
never the address, total or contents. A wrong phone is indistinguishable from
a missing order, so the endpoint cannot be used to discover which order
numbers exist.

Every status change goes through `Order.record_status()` — checkout, the
M-Pesa callback, and the admin (both the dropdown and the bulk actions). A
receipt email goes out when payment confirms, guarded against Safaricom's
callback replays so one payment sends one receipt.

## The Android app

`~/projects/ReactNativeWrapper` is an Expo WebView wrapper around this site,
built on EAS. It consumes `/orders/track/api/` for a native tracker that
raises a local notification when an order moves, keeps recently-viewed
products on the phone so the app still shows something with no signal, and
shares the current page through the system sheet.

## Sizes and colours

`Size` and `Colour` are plain lookup tables joined to `Product` many-to-many.
They drive the shop sidebar filters (`?size=xl`, `?colour=navy`, and both at
once) and populate the detail page.

Stock is held on the product, not per size/colour combination, so these narrow
the listing and say what a piece comes in — they are not a variant-level
inventory, and the cart does not record which size was picked.

## Tests

```bash
python manage.py test
```

Covers the cart, the shop listing and its facets, checkout and order
ownership, the Daraja client and callback, accounts, and the seed table
itself. Password hashing drops to MD5 under `manage.py test` so the suite runs
in seconds.

## The front end

`static/css/style.css` and the rest of `static/` are the template's own files
and are never edited. Two sheets of ours load after it and win:

- `static/css/refresh.css` — the palette (as `:root` custom properties), the
  type scale and the button, card and form treatment. This is where the shop
  stops looking like the stock template.
- `static/css/storefront.css` — markup the template never had: places where it
  uses a link but a real shop needs a form POST (add to cart, sign out), plus
  the pages it never shipped (orders, sign-in, addresses, the M-Pesa results).
  It writes its colours as `var(--ink)`, `var(--accent)` and so on, so both
  sheets stay in step.

`static/js/shop.js` layers add-to-cart-without-a-reload on top of the theme's
`main.js`. Every form still works with JavaScript off.

## Email

Order receipts and password-reset links print to the console until `.env`
carries mail credentials:

```
EMAIL_HOST_USER=shop@gmail.com
EMAIL_HOST_PASSWORD=<16-character Google App Password>
```

Setting both switches `EMAIL_BACKEND` to SMTP; leaving them blank keeps the
console backend, so a fresh clone runs with no mail server.

Gmail rather than a transactional provider, deliberately: PythonAnywhere's
free tier refuses connections to `smtp.sendgrid.net` and `smtp-relay.brevo.com`
and allows `smtp.gmail.com`. The password must be an **App Password**
(<https://myaccount.google.com/apppasswords>, 2-Step Verification required) —
an ordinary Google password is rejected.

```bash
python manage.py mailcheck                    # config, socket, TLS, login
python manage.py mailcheck --to you@here.com  # ...and send a test message
python manage.py mailcheck --receipt 15       # ...re-send a real order's receipt
```

## Social login (optional)

Google and Facebook sign-in are wired through django-allauth and read their
keys from the environment. Leave a provider's keys blank and its button simply
does not appear — see `.env.example` for where to get them.

## Licence

The MaleFashion template is by [Colorlib](https://colorlib.com) under
**CC BY 3.0**. The attribution in the footer must stay.
