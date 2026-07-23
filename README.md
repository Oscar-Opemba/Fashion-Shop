# Django E-commerce Storefront

An online store built on Django 6, using the
[MaleFashion](https://themewagon.com/themes/free-bootstrap-4-html5-ecommerce-website-template-malefashion/)
ThemeWagon template as its front end.

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
| `shop` | `Category`, `Product`, `ProductImage`, `Review`, `WishlistItem` |
| `cart` | Session-backed cart — `cart/cart.py` holds the `Cart` class everything reuses |
| `orders` | `Order`, `OrderItem`, `Coupon`, checkout, order history |
| `accounts` | `Profile`, `Address`, allauth wiring |

## How checkout works

There is no online payment. Checkout collects delivery details and places the
order; it is settled with the customer off-site.

```
cart  ->  checkout form (name, phone, county, town, street)
      ->  Order + OrderItem rows created in one transaction
      ->  stock decremented, cart and coupon cleared
      ->  orders:placed confirmation page
```

- Line prices are copied from the cart, not re-read from the product, so what
  the shopper agreed to is what the order records.
- The order starts at status `pending`; move it through `processing`,
  `shipped` and `delivered` from the admin.
- A guest's claim on an order is written into their session at the moment it is
  created, which is what lets them see the confirmation page without an account
  and stops anyone else reading it by walking order ids.

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
