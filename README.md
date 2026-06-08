# smx-commerce

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
SMX_COMMERCE_ADMIN_API_KEY=<your-admin-token>
SMX_COMMERCE_FLASK_SECRET_KEY=<your-session-secret>
```

Generate strong values with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Use one generated value for `SMX_COMMERCE_ADMIN_TOKEN
SMX_COMMERCE_ADMIN_API_KEY` and another generated value for `SMX_COMMERCE_FLASK_SECRET_KEY`.

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
SMX_COMMERCE_ADMIN_API_KEY
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
