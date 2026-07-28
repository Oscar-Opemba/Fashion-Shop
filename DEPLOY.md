# Deploying to PythonAnywhere (free "Beginner" account)

The free tier is enough to run this shop, including M-Pesa. Two things make it
work that are worth knowing up front:

- **You get HTTPS for free** on `<username>.pythonanywhere.com`. That is a
  permanent, public https address, so it replaces the ngrok tunnel as the
  M-Pesa callback URL. No more restarting a tunnel before a demo.
- **Free accounts can only reach allowlisted sites**, but `.safaricom.co.ke`
  is on that allowlist, so STK push requests get through. (Step 6 verifies
  this rather than trusting it.)

Throughout, replace `<username>` with your PythonAnywhere account name.

---

## 1. Upload the shop data

`db.sqlite3` and `media/` are gitignored, so a clone gives you an empty shop
with no product images. Bundle them locally:

```bash
cd ~/projects/Fashion-Shop
tar czf shopdata.tar.gz db.sqlite3 media/
```

On PythonAnywhere: **Files** tab → navigate to `/home/<username>/` → *Upload a
file* → pick `shopdata.tar.gz`.

## 2. Run the setup script

Open a **Bash** console (Consoles tab → *Bash*) and run:

```bash
git clone https://github.com/Oscar-Opemba/Fashion-Shop.git
tar xzf ~/shopdata.tar.gz -C ~/Fashion-Shop
bash ~/Fashion-Shop/deploy/pythonanywhere_setup.sh
```

The script creates the virtualenv, installs the dependencies, writes a
production `.env` (with a fresh `SECRET_KEY` and the right host baked in),
runs `collectstatic`, and applies migrations. It takes a few minutes, mostly
`pip install`. It is safe to re-run — it will not overwrite your `.env`.

Extracting the tarball *before* the script matters: that way `migrate` runs
against your real database instead of creating an empty one.

## 3. Create the web app

**Web** tab → *Add a new web app* → **Manual configuration** (not "Django" —
that scaffolds a new project over yours) → **Python 3.13**.

Then set, in the sections down that page:

| Setting | Value |
| --- | --- |
| Source code | `/home/<username>/Fashion-Shop` |
| Working directory | `/home/<username>/Fashion-Shop` |
| Virtualenv | `/home/<username>/.virtualenvs/fashionshop` |

## 4. WSGI file and static mappings

Still on the Web tab, click the **WSGI configuration file** link. Delete
everything in it and paste the contents of
`deploy/pythonanywhere_wsgi.py`. Nothing in it needs editing — it derives its
paths from your home directory. Save.

In the **Static files** section add *both* mappings:

| URL | Directory |
| --- | --- |
| `/static/` | `/home/<username>/Fashion-Shop/staticfiles` |
| `/media/` | `/home/<username>/Fashion-Shop/media` |

The `/media/` one is easy to forget and is what serves the product images:
with `DEBUG=False` Django refuses to serve uploads itself, so without this
mapping every product photo 404s.

Hit the green **Reload** button. The site should now load at
`https://<username>.pythonanywhere.com`.

## 5. Add the M-Pesa credentials

The setup script left them blank on purpose — secrets never go through git.
Open `/home/<username>/Fashion-Shop/.env` (Files tab, or `nano` in the
console) and fill in from your local `.env`:

```
MPESA_CONSUMER_KEY=...
MPESA_CONSUMER_SECRET=...
MPESA_PASSKEY=...
```

`MPESA_CALLBACK_BASE_URL` is already set to your https host, so the callback
Safaricom posts to is:

```
https://<username>.pythonanywhere.com/payments/callback/<MPESA_CALLBACK_TOKEN>/
```

**Reload** the web app for the new values to take effect — editing `.env` on
its own does nothing until the workers restart.

## 6. Check that Daraja is reachable

Free accounts route outbound traffic through a proxy, so confirm the
allowlist really covers Safaricom before demoing. This asks the live site's
own code to fetch a real token, which tests the proxy, the allowlist and your
credentials in one go:

```bash
source ~/.virtualenvs/fashionshop/bin/activate
cd ~/Fashion-Shop
python manage.py shell -c "from payments.daraja import get_access_token; print(get_access_token())"
```

A 28-character token means everything is wired up. A `DarajaError` naming the
consumer key means the `.env` values did not take; a hang or a proxy error
means the host is blocked, and the fix is a paid account.

Then run a real STK push against a sandbox test number through the site.

---

## Free-tier limits worth planning around

- **Your site expires every month.** The Web tab shows a "Run until 1 month
  from today" button; click it or the site quietly goes offline. PythonAnywhere
  emails a warning a week before. Set a calendar reminder anyway — this is the
  single most likely reason the site is down when you next need it.
- **100 CPU-seconds per day.** Plenty for browsing and demos. Exhausting it
  does not take the site down, it just makes it slow.
- **512 MB disk.** This deployment uses roughly 160 MB (134 MB virtualenv,
  20 MB collected static, the rest code and media).
- **One web app**, on `<username>.pythonanywhere.com` only. No custom domains.
- **SQLite is fine here** but only because traffic is low; it serialises
  writes. Outgrowing it means paying: free accounts created after 2026-01-15
  cannot use MySQL at all (the Databases tab just offers an upgrade), and
  Postgres has always been paid-only.
- **No scheduled tasks** on free accounts created after 2026-01-15 either, so
  nothing in this deployment can rely on cron.

## Deploying changes later

```bash
cd ~/Fashion-Shop
git pull
source ~/.virtualenvs/fashionshop/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Then **Reload** on the Web tab. Code changes do not go live until you reload.

## When something breaks

The Web tab links three logs. The error log is the one that matters — a
traceback on startup is almost always a bad path in the WSGI file or a
missing package in the virtualenv.

A `DisallowedHost` error means `ALLOWED_HOSTS` in `.env` does not match the
host you browsed to. A CSRF failure on login or checkout means
`CSRF_TRUSTED_ORIGINS` is missing the `https://` scheme.
