# Django E-commerce with M-Pesa (Daraja STK Push)

A mobile-first online store built on Django 6, styled with a dark restyle of the
[MaleFashion](https://themewagon.com/themes/free-bootstrap-4-html5-ecommerce-website-template-malefashion/)
ThemeWagon template, taking payment via Safaricom's Daraja STK Push.

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
| `catalog` | `Category`, `Product`, `ProductImage`, `Review`, `WishlistItem` |
| `cart` | Session-backed cart — `cart/cart.py` holds the `Cart` class everything reuses |
| `orders` | `Order`, `OrderItem`, `Coupon`, checkout, order history |
| `payments` | `payments/daraja.py` (Daraja client), `MpesaPayment`, callback, status polling |
| `accounts` | `Profile`, `Address`, allauth wiring |

## Getting Daraja sandbox credentials

1. Register at [developer.safaricom.co.ke](https://developer.safaricom.co.ke) and log in.
2. **My Apps → Add a new App**, tick *Lipa Na M-Pesa Sandbox*. This gives you a
   **Consumer Key** and **Consumer Secret**.
3. **APIs → Lipa Na M-Pesa Online → Simulate** shows the sandbox **Shortcode**
   (`174379`) and the **Passkey**.
4. That same page lists the sandbox test phone numbers and the PIN to use.
5. Put all four in `.env` and set `MPESA_ENV=sandbox`.

## Testing a payment locally

Safaricom posts the payment result to a callback URL, so it needs to reach your
machine over **public HTTPS**. Without this, orders are created but stay
`pending` — the status poller is what stops the checkout hanging.

```bash
ngrok http 8000
```

Then in `.env`:

```
MPESA_CALLBACK_BASE_URL=https://<your-id>.ngrok-free.app
CSRF_TRUSTED_ORIGINS=https://<your-id>.ngrok-free.app
ALLOWED_HOSTS=localhost,127.0.0.1,<your-id>.ngrok-free.app
```

Restart the server, add something to your cart, check out with a sandbox test
number, and enter the sandbox PIN on the prompt.

### How the payment flow works

```
checkout  ->  order created (unpaid, stock untouched)
          ->  payments:start   sends the STK push
          ->  payments:waiting polls payments:status every 3s
          ->  Safaricom POSTs  payments:callback
          ->  order marked paid, stock decremented, cart cleared
```

Three things are worth knowing about the design:

- **Stock is decremented when payment is confirmed, not at checkout.** An
  abandoned STK prompt therefore never holds inventory hostage.
- **The callback is idempotent.** Safaricom retries until it gets a zero
  `ResultCode`, so the handler guards on `Order.stock_applied` and returns
  `{"ResultCode": 0}` for a payment that is already settled. Replaying the same
  callback changes nothing.
- **The callback cannot be authenticated** (Safaricom sends no credentials), so
  the defences are an unguessable URL segment from `MPESA_CALLBACK_TOKEN`,
  lookup strictly by `CheckoutRequestID`, and never trusting an order id from
  the request body.

The status poller also queries Daraja directly, so a dropped tunnel or a lost
callback still resolves the checkout instead of spinning forever.

## The dark theme

The template is light by default. Every override lives in
`static/css/theme-dark.css`, loaded **after** the theme's `style.css` — the
theme's own files are never edited, so re-downloading it cannot clobber the
restyle.

The palette is a set of CSS custom properties on `:root`. The theme's red
`#e53637` only reaches 4.07:1 as text on the dark surface, so it is split into
three roles:

| Token | Value | Use |
|---|---|---|
| `--accent` | `#e53637` | Borders, underlines, non-text accents |
| `--accent-text` | `#ef5350` | Red text — 4.99:1 on `--surface` |
| `--accent-btn` | `#d32f2f` | Button fills — white on it is 4.98:1 |

All pages were checked to WCAG AA (4.5:1) with a scripted contrast audit.

## Mobile-first notes

The theme is responsive but authored desktop-down; new markup here goes the
other way. Base styles are the phone, and `md`/`lg` breakpoints add desktop
affordances back.

- Shop filters collapse behind a **Filter & sort** button on phones and render
  as the theme's sidebar from `lg` up.
- Product detail, cart and checkout carry a **sticky bottom action bar**
  (mobile only) so the primary action never scrolls away.
- The M-Pesa field is `type="tel" inputmode="numeric"` so handsets show a
  number pad.
- Cart lines are cards, not table rows — a table forces sideways scrolling on a
  phone.
- Checkout is single-column at every breakpoint.

## Licence

The MaleFashion template is by [Colorlib](https://colorlib.com) under
**CC BY 3.0**. The attribution in the footer must stay.
