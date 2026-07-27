# M-Pesa Daraja Integration — Complete Reference

A one-page map of the Safaricom Daraja (Lipa na M-Pesa Online / STK Push)
integration: every course lesson pointed at the code that implements it, the
design decisions that make it production-grade, and the commands used to demo
it. Companion to [MODULE.md](../MODULE.md) Part 10 and
[ARCHITECTURE.md](../ARCHITECTURE.md).

## Lessons → code map

| Lesson | Concept | Where it lives |
|---|---|---|
| 4.1 Overview | OAuth, endpoints, sandbox/prod | `payments/daraja.py` (whole module) |
| 4.2 Credentials | Key / Secret / Shortcode / Passkey | `.env` → `settings.py:353-365` |
| 4.3 OAuth token | Basic Auth → access_token | `daraja.py` `get_access_token` |
| 4.4 STK Push | phone, password, payload, send | `daraja.py` `stk_push` |
| 4.5 Callback | receive & process the result | `payments/views.py` `callback` |
| (status) | poll fallback | `views.py` `status` + `daraja.py` `query_stk_status` |
| 4.6 Full flow | cart → order → pay → log | `orders/views.py` `checkout` → `payments/views.py` `start` |

## The files

| File | Role |
|---|---|
| `payments/daraja.py` | API client — token, STK push, status query, phone/password/callback helpers |
| `payments/views.py` | start → waiting → status poll, callback, success/failed, retry |
| `payments/models.py` | `MpesaPayment` (OneToOne with Order, unique `checkout_request_id`) |
| `payments/urls.py` | routes, including `callback/<token>/` |
| `orders/views.py` | checkout: order creation, cart-kept-until-paid |
| `myproject/settings.py` | `MPESA_*` config read from `.env` |
| `.env` | credentials + tunnel URL (git-ignored) |
| `templates/payments/` | waiting / success / failed pages |

## The one flow to remember

```
cart -> checkout (order, paid=False, stock NOT taken, cart KEPT)
      -> start() -> stk_push()  -- Safaricom accepts (ResponseCode 0)
      -> save CheckoutRequestID (PENDING) -> waiting page
           |
    +------+-----------------------------------+
 callback() (push, authoritative)   status()->query (pull, fallback)
    +------+-----------------------------------+
      -> _mark_paid:  paid=True, stock taken (once), coupon counted, cart cleared
         _mark_failed: FAILED (only on terminal codes)
```

**Key mental model:** `stk_push` succeeding means *"prompt sent"*, **not**
*"paid"*. The real result arrives asynchronously — settled by whichever of the
callback/poll wins, made safe by idempotency.

## What makes this production-grade

| Design choice | Where | Why |
|---|---|---|
| Token cached + **401 retry** | `daraja.py` (`TOKEN_CACHE_SECONDS`, `stk_push`) | Fast, self-healing — not "regenerate every call" |
| **Secret token in callback URL** | `daraja.py` `callback_url`, `views.py` `callback` | Safaricom's callback is unauthenticated; blocks forgery |
| Lookup by **CheckoutRequestID** only | `views.py` `callback` | Body is untrusted; can't target an arbitrary order |
| **Idempotent** callback (3 guards) | `views.py` `callback` + `_mark_paid` | Safaricom retries; stock is taken exactly once |
| Always **ACK (ResultCode 0)** | `views.py` `ACK` | Stops Safaricom retrying forever |
| **Terminal vs transient** codes | `views.py` `TERMINAL_STK_FAILURE_CODES` | Poll never fails a payment that may still succeed |
| Cart **kept until paid** | `orders/views.py` `checkout` | A failed/cancelled prompt leaves somewhere to retry |
| Stock on **paid**, not checkout | `views.py` `_mark_paid` (`stock_applied`) | An abandoned prompt never holds inventory |
| Money as **int shillings** | `orders/models.py` `get_mpesa_amount` | Daraja rejects decimals |
| **Raw callback** persisted | `models.py` `raw_callback` (JSONField) | Debuggable after the fact |

## The Daraja endpoints used

| Endpoint | Method | Function |
|---|---|---|
| `/oauth/v1/generate` | GET | `get_access_token` |
| `/mpesa/stkpush/v1/processrequest` | POST | `stk_push` |
| `/mpesa/stkpushquery/v1/query` | POST | `query_stk_status` |
| `/payments/callback/<token>/` (ours) | POST | `callback` (received) |

Sandbox host `https://sandbox.safaricom.co.ke`, production
`https://api.safaricom.co.ke` — selected by `MPESA_ENV` in `base_url()`.

## Configuration (`.env`)

| Var | Meaning |
|---|---|
| `MPESA_ENV` | `sandbox` or `production` (defaults to sandbox) |
| `MPESA_CONSUMER_KEY` / `_SECRET` | OAuth credentials from the Daraja portal app |
| `MPESA_SHORTCODE` | Business shortcode (`174379` in sandbox) |
| `MPESA_SHORTCODE_TYPE` | `paybill` or `till` — picks the transaction type |
| `MPESA_PARTY_B` | Who receives the money; blank means "same as shortcode" |
| `MPESA_PASSKEY` | Used with shortcode + timestamp to build the request password |
| `MPESA_CALLBACK_BASE_URL` | Public https base Safaricom posts to (tunnel in dev) |
| `MPESA_CALLBACK_TOKEN` | Unguessable segment in the callback path |
| `MPESA_TRANSACTION_DESC` | Default transaction description |

**Switching sandbox → production is a `.env` edit, never a code change.**

## Going live — where the money actually goes

In sandbox `PartyB` is `174379`, Safaricom's shared public test Paybill. Every
Daraja developer pushes to that same number, which is why a sandbox receipt
looks real but no shillings move — not even when a real handset confirms the
prompt.

**STK Push always pays a shortcode, never a phone number.** There is no
configuration that routes checkout takings to a personal `07xx` line; Daraja
requires a Paybill or Buy Goods till for `PartyB`. A personal number only
enters the picture further downstream, when the business account is settled.

Going live is three steps, and only the last one touches this repo:

1. **Get an M-Pesa business account** from Safaricom — Paybill or Buy Goods
   till. Business registration paperwork, not a portal click.
2. **Apply to Go Live** on the Daraja portal. This issues *production*
   Consumer Key, Secret and Passkey bound to that shortcode. Sandbox
   credentials do not carry over.
3. **Edit `.env`.** `.env.example` carries the full block, commented out.

The Paybill/till distinction is the one that bites, because the two take
different `TransactionType` values and a till splits the shortcode in two:

| | `MPESA_SHORTCODE` | `MPESA_PARTY_B` | `TransactionType` sent |
|---|---|---|---|
| Paybill | the paybill number | blank (defaults to shortcode) | `CustomerPayBillOnline` |
| Buy Goods | head office / store number | the till number | `CustomerBuyGoodsOnline` |

`daraja.transaction_type()` maps `MPESA_SHORTCODE_TYPE` to the right value and
falls back to Paybill on an unrecognised setting — a typo degrades to the
common case rather than taking checkout down.

## Development callback tunnel

Safaricom must reach a public https URL, so in development a tunnel exposes the
local server. This project uses a cloudflared quick tunnel; `ALLOWED_HOSTS` and
`CSRF_TRUSTED_ORIGINS` wildcard `.trycloudflare.com`.

```bash
cloudflared tunnel --url http://localhost:8000     # prints a public https URL
# put that URL in MPESA_CALLBACK_BASE_URL, then restart Django so it re-reads .env
```

Quick-tunnel URLs are ephemeral — a new one is issued on every restart, so the
`.env` value and Django must be refreshed together whenever the tunnel changes.

## Verifying it works

```bash
# Credentials authenticate (fetches a real sandbox token):
python manage.py shell -c "from payments.daraja import get_access_token; print(get_access_token())"

# The test suite (callback idempotency, token rejection, STK push, poll):
python manage.py test payments
```

A real end-to-end check fires an STK push to a sandbox test number
(`254708374149`) and watches the callback land in the server log as
`POST /payments/callback/<token>/ 200`. The sandbox test number returns a
`1037` timeout (no real handset to enter a PIN), which exercises the failure
path; the success path is covered by the callback tests.
