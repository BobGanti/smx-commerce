# smx-commerce

`smx-commerce` is an installable commerce package for SyntaxMatrix-based projects.

It plugs a complete commerce module into an existing host project and provides:

- Public storefront pages
- Product and category management
- Cart and checkout flow
- Stripe checkout and webhook integration
- Order administration
- Customer account login by magic link
- Customer entitlements and access-check helpers
- Branding/settings management
- Local scaffold files for client-owned configuration
- Production-ready environment variable structure

Current package version:

```text
0.2.0
```

---

## 1. What smx-commerce does

`smx-commerce` lets a SyntaxMatrix-based project add commerce features without building its own product, checkout, order, customer, and entitlement system from scratch.

The package remains installable and reusable, while the host project owns its local configuration through a generated `commerce/` folder.

The package owns the implementation.

The host project owns the generated configuration scaffold:

```text
commerce/
  __init__.py
  smx_commerce_setup.py
  .smx_commerce.env
  .smx_commerce_example.env
  .smx_commerce.deploy_example.env
  data/
  assets/
    logo.png
    favicon.png
    products/
    receipts/
```

---

## 2. Important route change in v0.2.0

From `0.2.0`, all public storefront routes are namespaced under `/commerce`.

Use:

```text
/commerce
/commerce/products
/commerce/products/<slug>
/commerce/cart
/commerce/checkout/start
/commerce/checkout/cart/start
/commerce/checkout/success
/commerce/checkout/cancel
/commerce/customer/login
/commerce/customer/account
```

Admin routes are under `/commerce/admin`:

```text
/commerce/admin
/commerce/admin/login
/commerce/admin/products
/commerce/admin/products/new
/commerce/admin/categories
/commerce/admin/categories/new
/commerce/admin/orders
/commerce/admin/customers
/commerce/admin/branding
/commerce/admin/settings
```

The generated client scaffold folder is:

```text
commerce/
```

not:

```text
smxcommerce/
```

---

## 3. Installation

Install from PyPI inside the host project’s virtual environment:

```bash
pip install smx-commerce
```

For a development install from source:

```bash
pip install -e .
```

---

## 4. Generate the commerce scaffold

From the root of the SyntaxMatrix-based host project, run:

```bash
python -c "from smx_commerce import ensure_commerce_scaffold; ensure_commerce_scaffold()"
```

This creates:

```text
commerce/
  __init__.py
  smx_commerce_setup.py
  .smx_commerce_example.env
  .smx_commerce.env
  .smx_commerce.deploy_example.env
  data/
  assets/
    logo.png
    favicon.png
    products/
    receipts/
```

The scaffold is safe to rerun.

Existing customer-owned files are not overwritten.

---

## 5. Local environment file

Local runtime config lives at:

```text
commerce/.smx_commerce.env
```

The generated local environment file includes values similar to:

```env
SMX_COMMERCE_DATABASE_URL=sqlite+pysqlite:///./commerce/data/smx_commerce_dev.db
SMX_COMMERCE_ADMIN_TOKEN=local-admin-token
SMX_COMMERCE_FLASK_SECRET_KEY=replace-with-a-strong-session-secret

SMX_COMMERCE_PAYMENT_PROVIDER=none
SMX_COMMERCE_EMAIL_PROVIDER=none

SMX_COMMERCE_HOST_SITE_TITLE=SyntaxMatrix
SMX_COMMERCE_SITE_TITLE=SyntaxMatrix
SMX_COMMERCE_HOST_HOME_URL=/
SMX_COMMERCE_PROJECT_HOME_URL=/

SMX_COMMERCE_STORE_TITLE=smxCommerce
SMX_COMMERCE_MODULE_TITLE=smxCommerce
SMX_COMMERCE_STORE_HOME_URL=/commerce

SMX_COMMERCE_ASSETS_DIR=./commerce/assets
SMX_COMMERCE_PRODUCTS_ASSETS_DIR=./commerce/assets/products
SMX_COMMERCE_RECEIPTS_DIR=./commerce/assets/receipts
SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png
```

The primary admin key is:

```env
SMX_COMMERCE_ADMIN_TOKEN
```

`SMX_COMMERCE_ADMIN_TOKEN` remains as a backward-compatible alias.

When both are present, keep them the same to avoid local login confusion.

---

## 6. Integrate into a SyntaxMatrix-based project

The scaffold creates:

```text
commerce/smx_commerce_setup.py
```

That file exposes:

```python
setup_commerce(app, *, init_schema=True)
register_commerce_plugin(app, *, init_schema=True)
```

Use the existing app object from your SyntaxMatrix project.

Example:

```python
from commerce.smx_commerce_setup import setup_commerce

setup_commerce(
    app,
    init_schema=True,
)
```

A fuller example:

```python
from pathlib import Path

import syntaxmatrix as smx
from commerce.smx_commerce_setup import setup_commerce


PROJECT_ROOT = Path(__file__).resolve().parent

app = smx.get_app()

setup_commerce(
    app,
    init_schema=True,
)
```

Use the exact app access pattern that your SyntaxMatrix host project already provides.

Do not copy package internals into the client project.

Do not edit files inside `src/smx_commerce` from the host project.

The client project should only own the generated `commerce/` folder and its own host application files.

---

## 7. Quick local run

After installation and integration, start your host project:

```bash
python app.py
```

Then open:

```text
http://localhost:5055/commerce
```

Admin:

```text
http://localhost:5055/commerce/admin
```

The exact port depends on the host SyntaxMatrix project.

---

## 8. Admin login

Admin entry point:

```text
/commerce/admin
```

If an admin token is configured, unauthenticated users are redirected to:

```text
/commerce/admin/login
```

For the generated local scaffold, the default token is:

```text
local-admin-token
```

Set a strong value before any real deployment.

Example:

```env
SMX_COMMERCE_ADMIN_TOKEN=replace-with-a-strong-admin-token
SMX_COMMERCE_ADMIN_TOKEN=replace-with-a-strong-admin-token
```

---

## 9. Public storefront routes

The public storefront is namespaced under `/commerce`.

Commerce home:

```text
/commerce
```

Product list:

```text
/commerce/products
```

Product detail:

```text
/commerce/products/<slug>
```

Cart:

```text
/commerce/cart
```

Start checkout for a product:

```text
/commerce/checkout/start
```

Start checkout from cart:

```text
/commerce/checkout/cart/start
```

Checkout return page:

```text
/commerce/checkout/success
```

Checkout cancellation page:

```text
/commerce/checkout/cancel
```

Customer login:

```text
/commerce/customer/login
```

Customer account:

```text
/commerce/customer/account
```

The checkout success page does not itself confirm payment. Payment confirmation should be trusted only after a verified payment webhook updates the order.

---

## 10. Admin routes

Admin dashboard:

```text
/commerce/admin
```

Products list:

```text
/commerce/admin/products
```

Create product:

```text
/commerce/admin/products/new
```

Product detail:

```text
/commerce/admin/products/<slug>
```

Edit product:

```text
/commerce/admin/products/<slug>/edit
```

Categories list:

```text
/commerce/admin/categories
```

Create category:

```text
/commerce/admin/categories/new
```

Orders:

```text
/commerce/admin/orders
```

Customers:

```text
/commerce/admin/customers
```

Branding/settings:

```text
/commerce/admin/branding
```

General settings:

```text
/commerce/admin/settings
```

---

## 11. Admin dashboard design

The admin dashboard is the control station.

It should contain summary cards, status information, and quick actions.

The dashboard should not duplicate forms that already have dedicated pages.

Correct structure:

```text
Dashboard:
  - Summary cards
  - Quick actions
  - Links to products, categories, orders, customers, branding/settings

Branding:
  /commerce/admin/branding

Create product:
  /commerce/admin/products/new

Create category:
  /commerce/admin/categories/new
```

---

## 12. Products

Products are managed from:

```text
/commerce/admin/products
```

Create a product from:

```text
/commerce/admin/products/new
```

Product fields include:

- Slug
- Name
- Kind
- Status
- Summary
- Description
- Categories
- Sort order
- Product media

A product can have one or more price options.

Public product pages are available at:

```text
/commerce/products/<slug>
```

---

## 13. Categories

Categories are managed from:

```text
/commerce/admin/categories
```

Create a category from:

```text
/commerce/admin/categories/new
```

Category fields include:

- Slug
- Name
- Parent category
- Status
- Description
- Sort order

Categories can be used to organize products.

---

## 14. Price options

Products can have price options.

Examples:

- One-time purchase
- Subscription-style pricing
- Multiple tiers
- Event registration price
- Course price
- Service package price

Price options are managed from product detail pages in the admin panel.

---

## 15. Orders

Orders are created through checkout.

Admin users can view and manage orders from:

```text
/commerce/admin/orders
```

Order status should not be manually forced to `paid` through the admin edit form.

Paid status must come from a verified payment event or trusted payment workflow.

This protects the order and entitlement lifecycle.

---

## 16. Customers

Customers are created from checkout identity or customer login identity.

Admin users can manage customers from:

```text
/commerce/admin/customers
```

Customer records support:

- Active/blocked status
- Session revocation
- Entitlement history
- Order history

Blocked customers cannot keep using active sessions.

---

## 17. Customer login

Customer login uses magic-link authentication.

Customer login route:

```text
/commerce/customer/login
```

Customer account route:

```text
/commerce/customer/account
```

The customer login email service must be configured for real email delivery.

For local development, email delivery may be disabled or replaced by a test sender depending on the host project configuration.

---

## 18. Entitlements and access checks

When a paid order grants access to a product, `smx-commerce` can create customer entitlements.

The package exports helper functions:

```python
from smx_commerce import (
    customer_has_active_entitlement,
    get_customer_active_entitlement,
)
```

Check whether a customer has access:

```python
from smx_commerce import customer_has_active_entitlement

has_access = customer_has_active_entitlement(
    customer_public_id="cus_...",
    product_slug="agentic-ai-bootcamp",
    config=config,
)
```

Optionally check a specific price code:

```python
has_access = customer_has_active_entitlement(
    customer_public_id="cus_...",
    product_slug="agentic-ai-bootcamp",
    price_code="standard",
    config=config,
)
```

Get the active entitlement object:

```python
from smx_commerce import get_customer_active_entitlement

entitlement = get_customer_active_entitlement(
    customer_public_id="cus_...",
    product_slug="agentic-ai-bootcamp",
    config=config,
)
```

Entitlement access checks account for:

- Customer ID
- Product slug
- Optional price code
- Active entitlement status
- Start date
- Expiry date
- Cancelled status
- Revoked access

---

## 19. Branding

Branding is managed from:

```text
/commerce/admin/branding
```

Branding config includes:

```env
SMX_COMMERCE_HOST_SITE_TITLE=SyntaxMatrix
SMX_COMMERCE_HOST_HOME_URL=/
SMX_COMMERCE_STORE_TITLE=smxCommerce
SMX_COMMERCE_STORE_HOME_URL=/commerce
SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png
```

Backward-compatible aliases:

```env
SMX_COMMERCE_SITE_TITLE=SyntaxMatrix
SMX_COMMERCE_PROJECT_HOME_URL=/
SMX_COMMERCE_MODULE_TITLE=smxCommerce
```

Preferred names:

```env
SMX_COMMERCE_HOST_SITE_TITLE
SMX_COMMERCE_HOST_HOME_URL
SMX_COMMERCE_STORE_TITLE
SMX_COMMERCE_STORE_HOME_URL
```

---

## 20. Local assets

Generated local assets live in:

```text
commerce/assets/
```

Default paths:

```text
commerce/assets/logo.png
commerce/assets/favicon.png
commerce/assets/products/
commerce/assets/receipts/
```

Default URLs:

```text
/commerce/assets/logo.png
/commerce/assets/favicon.png
```

---

## 21. Database

Local default database:

```env
SMX_COMMERCE_DATABASE_URL=sqlite+pysqlite:///./commerce/data/smx_commerce_dev.db
```

For local development, SQLite is sufficient.

For production, use PostgreSQL.

Example production database URL:

```env
SMX_COMMERCE_DATABASE_URL=postgresql+psycopg://user:password@host:5432/database
```

---

## 22. Schema initialization

When calling:

```python
setup_commerce(app, init_schema=True)
```

the package initializes missing database tables.

For production, treat schema creation and migrations carefully.

Do not rely on automatic table creation to alter existing production tables.

Use explicit migration/check commands when provided by the package.

---

## 23. Useful CLI commands

Depending on the installed version, the package may expose migration and check commands such as:

```bash
smx-commerce check-schema
smx-commerce migrate-product-public-ids
smx-commerce migrate-product-media-table
```

Use:

```bash
smx-commerce --help
```

to inspect available commands.

Before production deployment, run schema checks from a trusted environment.

---

## 24. Payment providers

Supported payment provider modes:

```env
SMX_COMMERCE_PAYMENT_PROVIDER=none
SMX_COMMERCE_PAYMENT_PROVIDER=local
SMX_COMMERCE_PAYMENT_PROVIDER=stripe
```

For local development without payments:

```env
SMX_COMMERCE_PAYMENT_PROVIDER=none
```

For Stripe:

```env
SMX_COMMERCE_PAYMENT_PROVIDER=stripe
SMX_COMMERCE_STRIPE_SECRET_KEY=sk_live_or_test_key
SMX_COMMERCE_STRIPE_WEBHOOK_SECRET=whsec_...
```

Do not commit Stripe secrets.

Use your hosting platform’s secret manager for production.

---

## 25. Stripe webhook

Stripe webhook endpoint:

```text
/commerce/webhooks/payments/stripe
```

Configure Stripe to send checkout/payment events to the deployed host URL.

Example:

```text
https://your-domain.com/commerce/webhooks/payments/stripe
```

Payment confirmation should be trusted only after webhook verification.

The checkout success page is only a browser return page.

---

## 26. Email configuration

Supported email modes:

```env
SMX_COMMERCE_EMAIL_PROVIDER=none
SMX_COMMERCE_EMAIL_PROVIDER=smtp
```

SMTP example:

```env
SMX_COMMERCE_EMAIL_PROVIDER=smtp
SMX_COMMERCE_SMTP_HOST=smtp.gmail.com
SMX_COMMERCE_SMTP_PORT=587
SMX_COMMERCE_SMTP_USERNAME=your-smtp-username
SMX_COMMERCE_SMTP_PASSWORD=your-smtp-password
SMX_COMMERCE_DEFAULT_FROM_EMAIL=sales@example.com
SMX_COMMERCE_SMTP_USE_TLS=1
```

Do not commit SMTP passwords.

Use secrets in production.

Email is used for:

- Customer login magic links
- Order confirmation messages
- Receipt-related messages where enabled

---

## 27. Production deployment variables

Production deployments should set environment variables and secrets through the hosting platform.

Common non-secret values:

```env
SMX_COMMERCE_PUBLIC_BASE_URL=https://your-domain.com
SMX_COMMERCE_AUTO_INIT=1
SMX_COMMERCE_PAYMENT_PROVIDER=stripe
SMX_COMMERCE_EMAIL_PROVIDER=smtp

SMX_COMMERCE_HOST_SITE_TITLE=Your Site
SMX_COMMERCE_HOST_HOME_URL=https://your-domain.com
SMX_COMMERCE_STORE_TITLE=Commerce
SMX_COMMERCE_STORE_HOME_URL=/commerce

SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png
```

Common secret values:

```env
SMX_COMMERCE_ADMIN_TOKEN
SMX_COMMERCE_FLASK_SECRET_KEY
SMX_COMMERCE_DB_PASSWORD
SMX_COMMERCE_STRIPE_SECRET_KEY
SMX_COMMERCE_STRIPE_WEBHOOK_SECRET
SMX_COMMERCE_SMTP_PASSWORD
```

---

## 28. Cloud Run notes

For Google Cloud Run deployments, keep secrets in Secret Manager.

Typical production asset paths when using a mounted client data source:

```env
SMX_CLIENT_DIR=/app/$LOCAL_DATA_SOURCE
GCS_MOUNT_PATH=/app/$LOCAL_DATA_SOURCE

SMX_COMMERCE_ASSETS_DIR=/app/$LOCAL_DATA_SOURCE/commerce/assets
SMX_COMMERCE_PRODUCTS_ASSETS_DIR=/app/$LOCAL_DATA_SOURCE/commerce/assets/products
SMX_COMMERCE_RECEIPTS_DIR=/app/$LOCAL_DATA_SOURCE/commerce/assets/receipts
```

Typical public URLs:

```env
SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png
```

For Cloud SQL PostgreSQL, set either a full database URL or the package-supported Cloud Run aliases.

Example aliases:

```env
SMX_COMMERCE_DB_USER=your_commerce_db_user
SMX_COMMERCE_DB_NAME=your_commerce_db_name
SMX_COMMERCE_INSTANCE_CONNECTION_NAME=your-project:your-region:your-cloudsql-instance
SMX_COMMERCE_DB_PASSWORD=from-secret-manager
```

---

## 29. Package exports

Common public imports:

```python
from smx_commerce import setup_commerce
from smx_commerce import init_commerce
from smx_commerce import init_commerce_from_env
from smx_commerce import ensure_commerce_scaffold
from smx_commerce import build_commerce_config_from_env
from smx_commerce import customer_has_active_entitlement
from smx_commerce import get_customer_active_entitlement
```

Recommended host integration:

```python
from commerce.smx_commerce_setup import setup_commerce

setup_commerce(app, init_schema=True)
```

Direct package integration:

```python
from smx_commerce import setup_commerce

setup_commerce(
    app,
    project_root=PROJECT_ROOT,
    init_schema=True,
)
```

Environment-based integration:

```python
from smx_commerce import init_commerce_from_env

init_commerce_from_env(
    app,
    env_file="commerce/.smx_commerce.env",
    init_schema=True,
)
```

---

## 30. Generated scaffold API

The generated file:

```text
commerce/smx_commerce_setup.py
```

contains:

```python
def setup_commerce(app, *, init_schema: bool = True):
    ...
```

and:

```python
def register_commerce_plugin(app, *, init_schema: bool = True):
    ...
```

`setup_commerce()` is the normal integration function.

`register_commerce_plugin()` is a compatibility alias for plugin-style host applications.

---

## 31. Upgrade notes from 0.1.x to 0.2.0

Version `0.2.0` changed the public route and scaffold contract.

Update old public links:

```text
/products                 -> /commerce/products
/products/<slug>          -> /commerce/products/<slug>
/cart                     -> /commerce/cart
/checkout/start           -> /commerce/checkout/start
/checkout/cart/start      -> /commerce/checkout/cart/start
/checkout/success         -> /commerce/checkout/success
/checkout/cancel          -> /commerce/checkout/cancel
```

Update old scaffold folder:

```text
smxcommerce/
```

to:

```text
commerce/
```

Update local env path:

```text
.env.smx-commerce
```

to:

```text
commerce/.smx_commerce.env
```

Use only this variable for admin authentication:```env
SMX_COMMERCE_ADMIN_TOKEN
```

---

## 32. Troubleshooting

### Admin login says “Invalid admin key”

Check the active local env file:

```text
commerce/.smx_commerce.env
```

Confirm:

```env
SMX_COMMERCE_ADMIN_TOKEN=...
```

If both are present, keep them the same:

```env
SMX_COMMERCE_ADMIN_TOKEN=local-admin-token
SMX_COMMERCE_ADMIN_TOKEN=local-admin-token
```

Restart the host application after changing the env file.

---

### I cannot find the admin page

Use:

```text
/commerce/admin
```

not:

```text
/admin
```

---

### I cannot find the products page

Use:

```text
/commerce/products
```

not:

```text
/products
```

---

### Checkout success page says payment is not confirmed

That is correct.

The browser return page is not proof of payment.

Payment is confirmed only after a verified payment webhook updates the order.

---

### Product/category forms are not on the list page

That is expected.

Use dedicated creation pages:

```text
/commerce/admin/products/new
/commerce/admin/categories/new
```

The list pages should stay clean and should not duplicate creation forms.

---

### Static logo or favicon does not appear

Check:

```env
SMX_COMMERCE_ASSETS_DIR=./commerce/assets
SMX_COMMERCE_LOGO_URL=/commerce/assets/logo.png
SMX_COMMERCE_FAVICON_URL=/commerce/assets/favicon.png
```

Also confirm the files exist:

```text
commerce/assets/logo.png
commerce/assets/favicon.png
```

---

### Stripe test tries to call the network

Ensure your test environment is not configured with a real Stripe provider unless you are explicitly testing Stripe integration.

For local non-payment testing:

```env
SMX_COMMERCE_PAYMENT_PROVIDER=none
```

---

## 33. Minimal local checklist

```text
1. Install package:
   pip install smx-commerce

2. Generate scaffold:
   python -c "from smx_commerce import ensure_commerce_scaffold; ensure_commerce_scaffold()"

3. Confirm local env:
   commerce/.smx_commerce.env

4. Integrate:
   from commerce.smx_commerce_setup import setup_commerce
   setup_commerce(app, init_schema=True)

5. Start host app.

6. Open:
   /commerce

7. Admin:
   /commerce/admin

8. Login token:
   SMX_COMMERCE_ADMIN_TOKEN
```

---

## 34. Development test command

For package development:

```bash
pytest -q
```

Expected at the `0.2.0` checkpoint:

```text
238 passed
```

---

## 35. Security notes

Do not commit real secrets.

Do not expose admin routes publicly without a strong admin token.

Use HTTPS in production.

Use verified webhooks for payment confirmation.

Do not manually mark orders as paid from admin forms.

Use Secret Manager or your hosting platform’s secret system for:

```text
SMX_COMMERCE_ADMIN_TOKEN
SMX_COMMERCE_FLASK_SECRET_KEY
SMX_COMMERCE_DB_PASSWORD
SMX_COMMERCE_STRIPE_SECRET_KEY
SMX_COMMERCE_STRIPE_WEBHOOK_SECRET
SMX_COMMERCE_SMTP_PASSWORD
```

---

## 36. License

Add your chosen license here.

---

## 37. Maintainer notes

`smx-commerce` is designed as a reusable installable package for SyntaxMatrix-based host projects.

The host project should stay minimal.

The package should own commerce behavior.

The generated `commerce/` folder should hold only client-owned configuration, local assets, and setup glue.
This is a minimal customer-facing demo app showing how a client project can install and initialize `smx-commerce`.

## Admin token and private admin entry point

Public visitors should not see an Admin button or Admin navigation on the commerce pages.

Admins enter the panel directly through:

```text
/commerce/admin
```

If the project has an admin key configured, the system redirects the admin to:

```text
/commerce/admin/login
```

The admin must then enter the configured admin key.

### Who creates the admin key?

The project owner creates the admin key. `smx-commerce` does not invent a hidden token.

For local development, copy:

```text
commerce/.smx_commerce_example.env
```

to:

```text
commerce/.smx_commerce.env
```

Then set:

```text
SMX_COMMERCE_ADMIN_TOKEN
SMX_COMMERCE_ADMIN_TOKEN=<your-admin-token>
SMX_COMMERCE_FLASK_SECRET_KEY=<your-session-secret>
```

Generate strong values with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Use one generated value for `SMX_COMMERCE_ADMIN_TOKEN
SMX_COMMERCE_ADMIN_TOKEN` and another generated value for `SMX_COMMERCE_FLASK_SECRET_KEY`.

### Local demo example

For this local demo, the admin page is:

```text
http://127.0.0.1:5055/commerce/admin
```

The local key is whatever you set in:

```text
commerce/.smx_commerce.env
```

### Cloud deployment

For cloud deployment, set the same values as environment variables or secrets in the hosting platform.

Example names:

```text
SMX_COMMERCE_ADMIN_TOKEN
SMX_COMMERCE_ADMIN_TOKEN
SMX_COMMERCE_FLASK_SECRET_KEY
```

Recommended practice:

```text
- Store them in a secret manager.
- Do not hardcode them in source code.
- Do not commit them to Git.
- Rotate the admin key if it is exposed.
```

After changing secrets, restart the app or service so the new values are loaded.

---

## AI support integration with host-built ai_profile

smx-commerce supports AI-assisted support workflows through a host-provided LLM profile.

The host project builds the profile. smx-commerce uses that profile to create its internal provider adapter, support agents, orchestration, schema handling, deterministic safety rules, and admin review workflow.

For Google/Gemini, the host project should provide an ai_profile dictionary with these fields:

    from google import genai

    ai_profile = {
        "provider": "google",
        "model": GEMINI_MODEL,
        "api_key": GEMINI_API_KEY,
        "client": genai.Client(api_key=GEMINI_API_KEY),
    }

Then pass the profile into the generated commerce setup function:

    from commerce.smx_commerce_setup import setup_commerce

    setup_commerce(
        app,
        init_schema=True,
        ai_profile=ai_profile,
    )

The client project should not create a custom smx_commerce_ai_client.py file.

The client project owns only:

- provider
- model
- api_key
- provider client instance

smx-commerce owns:

- provider adapter
- support agents
- parallel and sequential orchestration
- JSON/schema handling
- deterministic safety rules
- admin review workflow

If ai_profile is not provided, commerce still works, but AI support actions such as support analysis and reply drafting are not configured.

Future providers planned for this profile boundary include OpenAI Responses API, Anthropic, and OpenAI-compatible chat-completions providers such as Alibaba, DeepSeek, and Moonshot/Kimi.
