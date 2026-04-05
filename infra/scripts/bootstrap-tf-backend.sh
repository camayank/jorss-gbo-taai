#!/usr/bin/env bash
# ===========================================================================
# bootstrap-tf-backend.sh
# ===========================================================================
# Creates the S3 bucket and DynamoDB table required by infra/terraform/ as
# its remote state backend, then initialises the main Terraform config and
# migrates any local state into S3.
#
# Run this ONCE per environment before using infra/terraform/ for the first time.
#
# Usage:
#   bash infra/scripts/bootstrap-tf-backend.sh dev
#   bash infra/scripts/bootstrap-tf-backend.sh staging
#   bash infra/scripts/bootstrap-tf-backend.sh production
#
# Requirements:
#   - Terraform >= 1.6  (terraform --version)
#   - AWS CLI configured with credentials that can create S3 + DynamoDB resources
# ===========================================================================

set -euo pipefail

ENVIRONMENT="${1:-}"

if [[ -z "$ENVIRONMENT" ]]; then
  echo "ERROR: environment argument required (dev | staging | production)"
  echo "Usage: $0 <environment>"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BOOTSTRAP_DIR="$REPO_ROOT/infra/bootstrap"
TERRAFORM_DIR="$REPO_ROOT/infra/terraform"

echo "============================================================"
echo "  Bootstrap Terraform backend for environment: $ENVIRONMENT"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Run bootstrap Terraform to create S3 + DynamoDB
# ---------------------------------------------------------------------------
echo "[1/3] Initialising bootstrap Terraform (local backend)..."
cd "$BOOTSTRAP_DIR"
terraform init -input=false

echo ""
echo "[2/3] Applying bootstrap resources (S3 bucket + DynamoDB table)..."
terraform apply \
  -var="environment=$ENVIRONMENT" \
  -input=false \
  -auto-approve

BUCKET_NAME=$(terraform output -raw state_bucket_name)
TABLE_NAME=$(terraform output -raw locks_table_name)

echo ""
echo "  Created S3 bucket:     $BUCKET_NAME"
echo "  Created DynamoDB table: $TABLE_NAME"

# ---------------------------------------------------------------------------
# Step 2: Verify main.tf backend config matches what was just created
# ---------------------------------------------------------------------------
echo ""
echo "[3/3] Initialising main Terraform and migrating state to S3..."
cd "$TERRAFORM_DIR"

# terraform init will detect the S3 backend and prompt to migrate local state.
# -migrate-state answers "yes" automatically.
terraform init \
  -migrate-state \
  -input=false \
  -backend-config="bucket=$BUCKET_NAME" \
  -backend-config="dynamodb_table=$TABLE_NAME"

echo ""
echo "============================================================"
echo "  Bootstrap complete!"
echo ""
echo "  Terraform state is now stored in:"
echo "    s3://$BUCKET_NAME/infra/terraform.tfstate"
echo ""
echo "  State locking via DynamoDB table:"
echo "    $TABLE_NAME"
echo ""
echo "  Next steps:"
echo "    cd infra/terraform"
echo "    terraform plan -var-file=terraform.tfvars"
echo "    terraform apply -var-file=terraform.tfvars"
echo "============================================================"
