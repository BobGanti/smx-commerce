# smx-commerce Deployment to Google Cloud Run

This guide deploys a **client Flask app that uses `smx-commerce`** to Google Cloud Run.

Production rule:

> **Do not use SQLite for production.**
>
> SQLite is only for local development or a very small single-instance sandbox. Production Cloud Run deployment should use **Cloud SQL for PostgreSQL** for commerce data.

For production:

- Commerce database: **Cloud SQL PostgreSQL**
- Uploaded logo/favicon/assets: **Cloud Storage mounted into Cloud Run**
- Secrets: **Secret Manager**
- Runtime: **Cloud Run**
- Container image: **Artifact Registry**

---

## 0. Expected client project structure

Local project example:

```text
smx-commerce-demo/
  app.py
  requirements.txt
  Dockerfile
  smxcommerce/
    __init__.py
    smx_commerce_setup.py
    .smx_commerce_example.env
    .smx_commerce.env              # local only, do not commit
    data/                          # local SQLite dev only
      smx_commerce_dev.db
    assets/
      logo.png
      favicon.png
```

Production will not use `smxcommerce/data/smx_commerce_dev.db`.

Production will use:

```text
Cloud SQL PostgreSQL
```

The `smxcommerce/assets/` folder can be mounted from Cloud Storage so admin-uploaded logo/favicon survive Cloud Run restarts and revisions.

---

## 1. Define every variable

Run these commands in **PowerShell**.

Change the values to your own project.

```powershell
# Google Cloud project
$PROJECT_ID = "YOUR_GCP_PROJECT_ID"

# Region for Cloud Run, Artifact Registry, Cloud SQL, and bucket
$REGION = "europe-west1"

# Artifact Registry
$REPO_ID = "smx-commerce-repo"

# Cloud Run service
$SERVICE = "smx-commerce-demo"

# Image tag
$IMAGE_TAG = "latest"

# Full image URI
$IMAGE_URI = "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO_ID/$SERVICE`:$IMAGE_TAG"

# Cloud SQL PostgreSQL
$CLOUD_SQL_INSTANCE = "smx-commerce-postgres"
$CLOUD_SQL_CONNECTION_NAME = "$PROJECT_ID`:$REGION`:$CLOUD_SQL_INSTANCE"

# Database details
$DB_NAME = "smx_commerce"
$DB_USER = "smx_commerce_app"

# Secret names
$DATABASE_URL_SECRET = "smx-commerce-database-url"
$ADMIN_API_KEY_SECRET = "smx-commerce-admin-api-key"
$FLASK_SECRET_KEY_SECRET = "smx-commerce-flask-secret-key"

# Cloud Storage bucket for persistent smxcommerce assets
# Bucket names must be globally unique.
$BUCKET = "$PROJECT_ID-smx-commerce-assets"

# Path inside the Cloud Run container where the bucket is mounted
$SMXCOMMERCE_MOUNT_PATH = "/app/smxcommerce"

# Asset directory used by smx-commerce
$SMX_COMMERCE_ASSETS_DIR = "$SMXCOMMERCE_MOUNT_PATH/assets"

# Public asset URLs served by smx-commerce
$SMX_COMMERCE_LOGO_URL = "/commerce/assets/logo.png"
$SMX_COMMERCE_FAVICON_URL = "/commerce/assets/favicon.png"

# Branding
$SMX_COMMERCE_SITE_TITLE = "SyntaxMatrix"
$SMX_COMMERCE_MODULE_TITLE = "smxCommerce"
$SMX_COMMERCE_PROJECT_HOME_URL = "/"

# Cloud Run scaling
$MIN_INSTANCES = "0"
$MAX_INSTANCES = "3"

# Cloud Run runtime
$PORT = "8080"

# Service account
$SERVICE_ACCOUNT_NAME = "smx-commerce-runner"
$SERVICE_ACCOUNT_EMAIL = "$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

# Public access to the web app.
# Use "true" for public website/app access.
# Use "false" if you want private/internal access only.
$ALLOW_UNAUTHENTICATED = "true"
```

Check variables:

```powershell
Write-Host "PROJECT_ID=$PROJECT_ID"
Write-Host "REGION=$REGION"
Write-Host "REPO_ID=$REPO_ID"
Write-Host "SERVICE=$SERVICE"
Write-Host "IMAGE_URI=$IMAGE_URI"
Write-Host "CLOUD_SQL_CONNECTION_NAME=$CLOUD_SQL_CONNECTION_NAME"
Write-Host "BUCKET=$BUCKET"
Write-Host "SERVICE_ACCOUNT_EMAIL=$SERVICE_ACCOUNT_EMAIL"
```

---

## 2. Select project and enable APIs

```powershell
gcloud config set project $PROJECT_ID

gcloud services enable `
  run.googleapis.com `
  cloudbuild.googleapis.com `
  artifactregistry.googleapis.com `
  sqladmin.googleapis.com `
  secretmanager.googleapis.com `
  storage.googleapis.com `
  iam.googleapis.com
```

---

## 3. Create Artifact Registry repository

```powershell
gcloud artifacts repositories create $REPO_ID `
  --repository-format=docker `
  --location=$REGION `
  --description="Docker repository for smx-commerce demo" `
  --project=$PROJECT_ID
```

If it already exists, that is fine.

---

## 4. Create Cloud Storage bucket for uploaded logo/favicon/assets

This bucket is for persistent `smxcommerce/assets/`.

It is **not** for the production database.

```powershell
gcloud storage buckets create "gs://$BUCKET" `
  --location=$REGION `
  --project=$PROJECT_ID `
  --uniform-bucket-level-access
```

Create the assets folder marker:

```powershell
"assets folder" | Out-File -Encoding utf8 .\assets-placeholder.txt

gcloud storage cp .\assets-placeholder.txt "gs://$BUCKET/assets/.keep"

Remove-Item .\assets-placeholder.txt -Force
```

Optional: upload local default logo/favicon before first deploy:

```powershell
gcloud storage cp ".\smxcommerce\assets\logo.png" "gs://$BUCKET/assets/logo.png"
gcloud storage cp ".\smxcommerce\assets\favicon.png" "gs://$BUCKET/assets/favicon.png"
```

---

## 5. Create Cloud SQL PostgreSQL instance

Use Cloud SQL PostgreSQL for production commerce data.

Choose a small tier for testing. Increase the tier for production load.

```powershell
gcloud sql instances create $CLOUD_SQL_INSTANCE `
  --database-version=POSTGRES_16 `
  --region=$REGION `
  --tier=db-custom-1-3840 `
  --storage-type=SSD `
  --storage-size=10GB `
  --availability-type=zonal `
  --project=$PROJECT_ID
```

Create database:

```powershell
gcloud sql databases create $DB_NAME `
  --instance=$CLOUD_SQL_INSTANCE `
  --project=$PROJECT_ID
```

Generate DB password:

```powershell
$DB_PASSWORD = python -c "import secrets; print(secrets.token_urlsafe(32))"
Write-Host $DB_PASSWORD
```

Create DB user:

```powershell
gcloud sql users create $DB_USER `
  --instance=$CLOUD_SQL_INSTANCE `
  --password=$DB_PASSWORD `
  --project=$PROJECT_ID
```

---

## 6. Create secrets

Generate app secrets:

```powershell
$ADMIN_API_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
$FLASK_SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"

Write-Host "ADMIN_API_KEY=$ADMIN_API_KEY"
Write-Host "FLASK_SECRET_KEY=$FLASK_SECRET_KEY"
```

Create the Cloud SQL SQLAlchemy URL.

This uses the Cloud SQL Unix socket exposed to Cloud Run through `--add-cloudsql-instances`.

```powershell
$DATABASE_URL = "postgresql+psycopg://$DB_USER`:$DB_PASSWORD@/$DB_NAME`?host=/cloudsql/$CLOUD_SQL_CONNECTION_NAME"

Write-Host $DATABASE_URL
```

Create secrets:

```powershell
$DATABASE_URL | gcloud secrets create $DATABASE_URL_SECRET `
  --data-file=- `
  --project=$PROJECT_ID

$ADMIN_API_KEY | gcloud secrets create $ADMIN_API_KEY_SECRET `
  --data-file=- `
  --project=$PROJECT_ID

$FLASK_SECRET_KEY | gcloud secrets create $FLASK_SECRET_KEY_SECRET `
  --data-file=- `
  --project=$PROJECT_ID
```

If a secret already exists and you want to rotate it:

```powershell
$DATABASE_URL | gcloud secrets versions add $DATABASE_URL_SECRET --data-file=- --project=$PROJECT_ID
$ADMIN_API_KEY | gcloud secrets versions add $ADMIN_API_KEY_SECRET --data-file=- --project=$PROJECT_ID
$FLASK_SECRET_KEY | gcloud secrets versions add $FLASK_SECRET_KEY_SECRET --data-file=- --project=$PROJECT_ID
```

---

## 7. Create service account and grant permissions

Create service account:

```powershell
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME `
  --display-name="smx-commerce Cloud Run service account" `
  --project=$PROJECT_ID
```

Allow the service to connect to Cloud SQL:

```powershell
gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" `
  --role="roles/cloudsql.client"
```

Allow the service to read secrets:

```powershell
gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" `
  --role="roles/secretmanager.secretAccessor"
```

Allow the service to read/write the asset bucket:

```powershell
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" `
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" `
  --role="roles/storage.objectAdmin"
```

---

## 8. Requirements for the client app

Your `requirements.txt` should include a PostgreSQL driver.

Example:

```text
Flask
gunicorn
smx-commerce
psycopg[binary]
```

For local editable development:

```text
Flask
gunicorn
-e ../smx-commerce
psycopg[binary]
```

---

## 9. Dockerfile

Example `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120"]
```

Important:

- Do not hardcode port `5055` in production.
- Cloud Run provides `$PORT`.
- The app must listen on `0.0.0.0:$PORT`.

---

## 10. Build the image

From the client project root:

```powershell
gcloud builds submit `
  --tag $IMAGE_URI `
  --project $PROJECT_ID
```

---

## 11. Deploy to Cloud Run

This deploys with:

- Cloud SQL connection
- Secret Manager values
- Cloud Storage volume mounted at `/app/smxcommerce`
- normal non-secret branding env vars

```powershell
$DEPLOY_FLAGS = @(
  "run", "deploy", $SERVICE,
  "--image", $IMAGE_URI,
  "--region", $REGION,
  "--project", $PROJECT_ID,
  "--platform", "managed",
  "--service-account", $SERVICE_ACCOUNT_EMAIL,
  "--add-cloudsql-instances", $CLOUD_SQL_CONNECTION_NAME,
  "--add-volume", "name=smxcommerce-assets,type=cloud-storage,bucket=$BUCKET",
  "--add-volume-mount", "volume=smxcommerce-assets,mount-path=$SMXCOMMERCE_MOUNT_PATH",
  "--set-env-vars", "SMX_COMMERCE_SITE_TITLE=$SMX_COMMERCE_SITE_TITLE,SMX_COMMERCE_MODULE_TITLE=$SMX_COMMERCE_MODULE_TITLE,SMX_COMMERCE_PROJECT_HOME_URL=$SMX_COMMERCE_PROJECT_HOME_URL,SMX_COMMERCE_ASSETS_DIR=$SMX_COMMERCE_ASSETS_DIR,SMX_COMMERCE_LOGO_URL=$SMX_COMMERCE_LOGO_URL,SMX_COMMERCE_FAVICON_URL=$SMX_COMMERCE_FAVICON_URL,SMX_COMMERCE_PAYMENT_PROVIDER=none,SMX_COMMERCE_EMAIL_PROVIDER=none",
  "--set-secrets", "SMX_COMMERCE_DATABASE_URL=$DATABASE_URL_SECRET`:latest,SMX_COMMERCE_ADMIN_API_KEY=$ADMIN_API_KEY_SECRET`:latest,SMX_COMMERCE_FLASK_SECRET_KEY=$FLASK_SECRET_KEY_SECRET`:latest",
  "--min-instances", $MIN_INSTANCES,
  "--max-instances", $MAX_INSTANCES,
  "--port", $PORT
)

if ($ALLOW_UNAUTHENTICATED -eq "true") {
  $DEPLOY_FLAGS += "--allow-unauthenticated"
} else {
  $DEPLOY_FLAGS += "--no-allow-unauthenticated"
}

gcloud @DEPLOY_FLAGS
```

---

## 12. Get the service URL

```powershell
$SERVICE_URL = gcloud run services describe $SERVICE `
  --region $REGION `
  --project $PROJECT_ID `
  --format "value(status.url)"

Write-Host $SERVICE_URL
```

Open:

```text
$SERVICE_URL/commerce
```

Admin:

```text
$SERVICE_URL/commerce/admin
```

Use the value generated into:

```text
$ADMIN_API_KEY
```

If you lost it, rotate the secret instead of trying to recover it.

---

## 13. Initialize database schema

If your app calls:

```python
setup_commerce(app, init_schema=True)
```

then schema is created during startup.

For production, you may later move schema creation to a controlled migration/init command. For the first deployment, `init_schema=True` is acceptable if your package uses SQLAlchemy `create_all` safely.

---

## 14. Verify deployment

Health:

```powershell
Invoke-RestMethod "$SERVICE_URL/commerce/health"
```

Public commerce:

```text
$SERVICE_URL/commerce
```

Admin dashboard:

```text
$SERVICE_URL/commerce/admin
```

Upload logo/favicon from Admin Dashboard.

Then verify:

```text
$SERVICE_URL/commerce/assets/logo.png
$SERVICE_URL/commerce/assets/favicon.png
```

---

## 15. Production notes

### Database

Use:

```text
Cloud SQL PostgreSQL
```

Do not use:

```text
SQLite in Cloud Run production
SQLite on Cloud Storage volume
SQLite inside container filesystem
```

SQLite remains useful for:

```text
local development
quick demos
unit tests
```

### Assets

Use:

```text
Cloud Storage mounted into Cloud Run
```

for:

```text
smxcommerce/assets/logo.png
smxcommerce/assets/favicon.png
```

### Secrets

Use Secret Manager for:

```text
SMX_COMMERCE_DATABASE_URL
SMX_COMMERCE_ADMIN_API_KEY
SMX_COMMERCE_FLASK_SECRET_KEY
```

Do not commit:

```text
smxcommerce/.smx_commerce.env
```

---

## 16. Troubleshooting

### Cloud Run says container failed to listen on PORT

Check Dockerfile. It must use:

```text
${PORT:-8080}
```

not a hardcoded local port.

### Database connection fails

Check:

```powershell
gcloud run services describe $SERVICE --region $REGION --project $PROJECT_ID
```

Verify:

```text
--add-cloudsql-instances
SMX_COMMERCE_DATABASE_URL secret
roles/cloudsql.client on service account
```

### Logo/favicon disappear after redeploy

Check the Cloud Storage mount:

```text
/app/smxcommerce/assets
```

and verify the bucket has:

```text
gs://BUCKET/assets/logo.png
gs://BUCKET/assets/favicon.png
```

### Admin login fails

Check:

```text
SMX_COMMERCE_ADMIN_API_KEY
SMX_COMMERCE_FLASK_SECRET_KEY
```

They must be set from Secret Manager.

---

## 17. Reference docs

- Cloud Run deployment: https://docs.cloud.google.com/run/docs/deploying
- Cloud Run to Cloud SQL PostgreSQL: https://docs.cloud.google.com/sql/docs/postgres/connect-run
- Cloud Storage volume mounts for Cloud Run: https://docs.cloud.google.com/run/docs/configuring/services/cloud-storage-volume-mounts
- Secret Manager: https://cloud.google.com/security/products/secret-manager
