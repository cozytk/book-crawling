#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Cloud Run Deployment Script
# ============================================================
# Free tier guardrails:
#   - max-instances=1  (no runaway scaling)
#   - min-instances=0  (scale to zero when idle)
#   - cpu-throttling   (billed only during request processing)
#   - 512Mi memory     (conservative allocation)
#   - Budget alert at $1 with email notifications
# ============================================================

# --- Configuration ---
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
REGION="${CLOUD_RUN_REGION:-asia-northeast3}"
SERVICE_NAME="book-crawler"
REPO_NAME="book-crawler"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/api"

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  echo "Error: GCP project not set."
  echo "Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo "=== Cloud Run Deploy ==="
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# --- Step 1: Enable APIs ---
echo "[1/5] Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --quiet

# --- Step 2: Artifact Registry ---
echo "[2/5] Setting up Artifact Registry..."
gcloud artifacts repositories create "${REPO_NAME}" \
  --repository-format=docker \
  --location="${REGION}" \
  --quiet 2>/dev/null || true

# --- Step 3: Build ---
echo "[3/5] Building container image..."
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions="_REGION=${REGION},_REPO=${REPO_NAME}" \
  --quiet

# --- Step 4: Deploy with free tier guardrails ---
echo "[4/5] Deploying to Cloud Run..."

# Read .env and build env vars string (KEY=VALUE,KEY=VALUE)
ENV_VARS=""
if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    key="${line%%=*}"
    value="${line#*=}"
    # Skip lines without =
    [[ "$key" == "$line" ]] && continue
    key="$(echo "$key" | tr -d '[:space:]')"
    [ -z "$key" ] && continue
    ENV_VARS="${ENV_VARS:+${ENV_VARS},}${key}=${value}"
  done < .env
  echo "  Loaded $(echo "$ENV_VARS" | tr ',' '\n' | wc -l | tr -d ' ') env vars from .env"
fi

DEPLOY_ARGS=(
  --image="${IMAGE}"
  --region="${REGION}"
  --platform=managed
  --allow-unauthenticated
  --min-instances=0
  --max-instances=1
  --memory=512Mi
  --cpu=1
  --timeout=300
  --cpu-throttling
  --port=8080
)
[ -n "$ENV_VARS" ] && DEPLOY_ARGS+=(--update-env-vars="${ENV_VARS}")

gcloud run deploy "${SERVICE_NAME}" "${DEPLOY_ARGS[@]}"

# Get service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --format="value(status.url)")

echo ""
echo "=== Deployed ==="
echo "URL:    ${SERVICE_URL}"
echo "Health: ${SERVICE_URL}/health"

# --- Step 5: Budget Alert ---
echo ""
echo "[5/5] Setting up budget alert..."
setup_budget() {
  gcloud services enable billingbudgets.googleapis.com --quiet

  BILLING_ACCOUNT=$(gcloud billing projects describe "${PROJECT_ID}" \
    --format="value(billingAccountName)" 2>/dev/null | sed 's|billingAccounts/||')

  if [ -z "$BILLING_ACCOUNT" ]; then
    echo "  Warning: Could not find billing account."
    echo "  Set up budget manually: https://console.cloud.google.com/billing/budgets"
    return
  fi

  # Create $1 budget with alerts at 50%, 90%, 100%
  gcloud billing budgets create \
    --billing-account="${BILLING_ACCOUNT}" \
    --display-name="Cloud Run Free Tier Guard" \
    --budget-amount=1.00USD \
    --threshold-rule=percent=0.5,basis=current-spend \
    --threshold-rule=percent=0.9,basis=current-spend \
    --threshold-rule=percent=1.0,basis=current-spend \
    --filter-services="services/run.googleapis.com" \
    --quiet \
    && echo "  Budget alert created: \$1 limit with notifications at 50%, 90%, 100%" \
    || echo "  Budget creation failed. Set up manually: https://console.cloud.google.com/billing/budgets"
}
setup_budget 2>/dev/null || echo "  Budget setup skipped. Set up manually: https://console.cloud.google.com/billing/budgets"

# --- Post-deploy notes ---
echo ""
echo "=== Next Steps ==="
echo "1. Verify health: curl ${SERVICE_URL}/health"
echo ""
echo "2. If SUPABASE_URL/KEY are not in .env, add them:"
echo "   gcloud run services update ${SERVICE_NAME} --region=${REGION} \\"
echo "     --update-env-vars=SUPABASE_URL=your_url,SUPABASE_KEY=your_key"
echo ""
echo "3. Update frontend env:"
echo "   NEXT_PUBLIC_API_URL=${SERVICE_URL}"
echo ""
echo "=== Free Tier Limits (monthly) ==="
echo "  Requests:  2,000,000"
echo "  vCPU:      180,000 seconds (~50 hours)"
echo "  Memory:    360,000 GB-seconds (~200 hours at 512Mi)"
echo "  Egress:    1 GB"
echo "  Current:   max-instances=1, cpu-throttling=on, min-instances=0"
