# Module 3 Demo Runbook — Models & Databases

Every command below has been run against this project and produces the output
shown. Work top to bottom. Two terminals help: one for the shell demos, one
left running the server for Lesson 3.3.

```bash
source .venv/bin/activate
```

---

## Lesson 3.1 — Database Design

### Talking point: where the models live

This project splits models by app instead of one big `models.py`:

| File | Models |
|---|---|
| `shop/models.py` | `Category`, `Product`, `ProductImage` |
| `orders/models.py` | `Coupon`, `Order`, `OrderItem` |
| `accounts/models.py` | `Profile`, `Address` |

Open `shop/models.py` on screen and point at:

- `Category.save()` — auto-slugs from the name, so nobody types slugs by hand
- `Product.category` — `ForeignKey(..., related_name='products')`
- `Product.Meta.indexes` — indexed `slug` and `-created` because both are queried on every page
- `Product.in_stock` — a `@property`, computed not stored

Then `orders/models.py`:

- `Order.Status` — `TextChoices`, the modern form of the lesson's `STATUS_CHOICES` list
- `Order.user` is `SET_NULL` — **orders outlive deleted users so history stays auditable**
- `OrderItem.price` — price is frozen at purchase time, never re-read from the product
- `OrderItem.product` is `PROTECT` — you cannot delete a product that has been sold

### Demo: the three relationship types

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
c.products.count()     # 4   <- this is related_name at work
[p.name for p in c.products.all()[:3]]

# ---- Reverse direction ----
p = Product.objects.first()
p.category.name        # 'Accessories'

# ---- One-to-One: User -> Profile ----
u = get_user_model().objects.first()
u.profile              # <Profile: Profile for admin>

# ---- Many-to-Many through a model ----
[f.name for f in OrderItem._meta.fields]
# ['id', 'order', 'product', 'price', 'quantity']
# Order <-> Product is many-to-many, but routed through OrderItem
# so each line can carry its own price and quantity.

# ---- Best practices, visible ----
str(p)                 # 'Polarised Sunglasses'   <- __str__
p.get_absolute_url()   # '/shop/polarised-sunglasses/'
p.in_stock             # True
Order.Status.choices   # [('pending', 'Pending'), ('processing', 'Processing'), ...]
```

### If asked about the `Transaction` model

The course notes include an M-Pesa `Transaction` model. This project removed
the Daraja integration (commit `8a9d41a`) — checkout collects delivery details
and the order is settled off-site, so there is no payment to log. Say that
plainly; it's a design decision, not a gap.

Same for `total_price`: the lesson stores it on `Order`, this project computes
it with `get_subtotal()` / `get_discount()` / `get_total()` from the frozen
line prices. That's the safer design.

---

## Lesson 3.2 — Django ORM Setup

### Step 1: the config

Show `myproject/settings.py` line 108:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

### Step 2: current state

```bash
python manage.py showmigrations shop orders accounts
```

```
shop
 [X] 0001_initial
 [X] 0002_remove_review_one_review_per_user_per_product_and_more
orders
 [X] 0001_initial
 [X] 0002_remove_order_paid_remove_order_stock_applied_and_more
accounts
 [X] 0001_initial
```

```bash
python manage.py makemigrations --check --dry-run
# No changes detected
```

**Say why that matters:** "No changes detected" means the models and the
migration files agree — there is no drift. It's the first thing to check when
a project misbehaves.

### Step 3: see the SQL without running it

```bash
python manage.py sqlmigrate shop 0001 | head -20
```

Shows the actual `CREATE TABLE` statements. Good moment to point out that the
ORM is generating SQL for you, not replacing it.

### Step 4: the live change → migrate → rollback loop

This is the part worth rehearsing. In `shop/models.py`, add one line to
`Product` right under `is_active`:

```python
    featured = models.BooleanField(default=False)
```

```bash
python manage.py makemigrations shop
```
```
Migrations for 'shop':
  shop/migrations/0003_product_featured.py
    + Add field featured to product
```

Open the generated file — it's short, show the `AddField` operation and the
`dependencies` list pointing at `0002`.

```bash
python manage.py migrate shop
#   Applying shop.0003_product_featured... OK

python manage.py migrate shop 0002        # <- rollback
#   Unapplying shop.0003_product_featured... OK

python manage.py showmigrations shop
# [X] 0001_initial
# [X] 0002_remove_review_...
# [ ] 0003_product_featured     <- unchecked
```

**Clean up before moving on** (otherwise you leave the repo dirty):

```bash
rm shop/migrations/0003_product_featured.py
# then remove the `featured` line from shop/models.py
python manage.py makemigrations --check --dry-run   # No changes detected
```

### Step 5: verify the tables

```bash
python manage.py shell
```
```python
from django.db import connection
[t for t in connection.introspection.table_names() if t.startswith(('shop_','orders_','accounts_'))]
# ['accounts_address', 'accounts_profile', 'shop_category',
#  'shop_product', 'shop_productimage',
#  'orders_coupon', 'orders_order', 'orders_orderitem']
```

---

## Lesson 3.3 — Admin Interface

### Step 1: superuser

Already exists — `admin` / `admin12345`. If you need to show the command:

```bash
python manage.py createsuperuser
```

(Don't actually run it in class unless you want a second account; just show it.)

### Step 2: the registration code

Open `shop/admin.py`. Point out this project uses the `@admin.register(Model)`
decorator rather than `admin.site.register(Model, ModelAdmin)` at the bottom —
same result, less repetition.

### Step 3: run it

```bash
python manage.py runserver
```

Go to <http://127.0.0.1:8000/admin/> and log in.

### Step 4: what to click, in order

All of these were verified returning HTTP 200.

**Categories** (`/admin/shop/category/`)
- `list_display` shows a **`product_count` column** — that's a custom method on
  the admin class, not a model field
- Click "Add category", type a name, watch **`prepopulated_fields`** fill the
  slug live as you type. This is the best single visual in the whole module.

**Products** (`/admin/shop/product/`)
- `list_filter` sidebar — filter by category / active / created
- **`list_editable`** — change price and stock straight from the list, then Save.
  Most demos never show this.
- **`date_hierarchy`** — the date drill-down bar across the top
- Open any product: the **`ProductImageInline`** lets you add gallery images on
  the parent page. Explain that inlines are how you edit a `ForeignKey`'s
  reverse side.
- `search_fields` — search a product name

**Orders** (`/admin/orders/order/`)
- `OrderItemInline` with `raw_id_fields` on product — a magnifying-glass picker
  instead of a dropdown, which is what you need once you have thousands of products
- `total_display` — custom column formatting `KES 1,234.00`
- `readonly_fields` on `created` / `updated` — open an order and show the
  greyed-out timestamps

**Profiles / Addresses** (`/admin/accounts/`)
- `search_fields` spans the relationship: `user__email` — double underscore
  traverses the FK

### Step 5: CRUD through the admin

Create a category, edit a product's price, then delete the test category.
That's Create / Read / Update / Delete without writing a view — which is
exactly the bridge into Lesson 3.4.

---

## Pre-flight checklist (run 10 minutes before class)

```bash
source .venv/bin/activate
python manage.py makemigrations --check --dry-run    # -> No changes detected
python manage.py migrate                             # -> No migrations to apply
python manage.py seed                                # -> Seed complete.
python manage.py runserver
```

Then log into `/admin/` once to confirm the password works.
