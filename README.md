# Django E-commerce Storefront

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
and are never edited. Everything the storefront adds on top lives in
`static/css/storefront.css`, loaded last — mostly places where the template
uses a link but a real shop needs a form POST (add to cart, wishlist, sign
out), plus the pages the template never shipped (orders, sign-in, addresses).
Its colours and metrics are the template's, so the site still looks like the
template.

`static/js/shop.js` layers add-to-cart-without-a-reload on top of the theme's
`main.js`. Every form still works with JavaScript off.

## Social login (optional)

Google and Facebook sign-in are wired through django-allauth and read their
keys from the environment. Leave a provider's keys blank and its button simply
does not appear — see `.env.example` for where to get them.

## Licence

The MaleFashion template is by [Colorlib](https://colorlib.com) under
**CC BY 3.0**. The attribution in the footer must stay.
