# Terraform Remote State Setup

This directory uses AWS S3 and DynamoDB for remote state management, enabling team collaboration on infrastructure changes.

## Architecture

- **S3 Bucket**: `jorss-gbo-{environment}-tf-state` — stores Terraform state files with versioning enabled
- **DynamoDB Table**: `jorss-gbo-{environment}-tf-locks` — provides state locking to prevent concurrent modifications
- **Encryption**: All state is encrypted at rest using AES256
- **Versioning**: S3 versioning is enabled for state recovery

## Prerequisites

- AWS credentials configured locally (via `~/.aws/credentials` or environment variables)
- Terraform >= 1.6 installed
- Appropriate IAM permissions to create S3 buckets and DynamoDB tables

## Initial Setup (First Time)

### Step 1: Create the Backend Infrastructure

The backend infrastructure (S3 bucket + DynamoDB table) is defined in `backend.tf`. You must create these resources first using local state:

```bash
# From infra/terraform directory
cd infra/terraform

# Initialize Terraform with local state (temporary)
terraform init

# Plan and apply the backend infrastructure
terraform plan -target='aws_s3_bucket.terraform_state' \
                -target='aws_s3_bucket_versioning.terraform_state' \
                -target='aws_s3_bucket_server_side_encryption_configuration.terraform_state' \
                -target='aws_s3_bucket_public_access_block.terraform_state' \
                -target='aws_dynamodb_table.terraform_locks'

terraform apply -target='aws_s3_bucket.terraform_state' \
                -target='aws_s3_bucket_versioning.terraform_state' \
                -target='aws_s3_bucket_server_side_encryption_configuration.terraform_state' \
                -target='aws_s3_bucket_public_access_block.terraform_state' \
                -target='aws_dynamodb_table.terraform_locks'
```

### Step 2: Migrate to Remote State

Once the S3 bucket and DynamoDB table are created:

```bash
# Initialize Terraform with remote backend
terraform init

# When prompted "Do you want to copy existing state to the new backend?", answer: yes
# This migrates your local state to S3
```

### Step 3: Verify Remote State

```bash
# Show that state is now remote
terraform show

# List state files in S3
aws s3 ls s3://jorss-gbo-dev-tf-state/ --region us-east-1

# Verify DynamoDB table was created
aws dynamodb describe-table --table-name jorss-gbo-dev-tf-locks --region us-east-1
```

## Ongoing Team Workflow

### Pulling Latest State

Before making changes, ensure you have the latest state:

```bash
# Refresh state from S3 (automatic on plan/apply)
terraform refresh
```

### Making Changes

Standard workflow for infrastructure changes:

```bash
# Pull latest state and review changes
terraform plan -out=tfplan

# Review the plan carefully
cat tfplan  # (shows binary plan, use plan output above)

# Apply only if plan looks correct
terraform apply tfplan
```

### State Locking

- State locking is automatic via DynamoDB
- If a `terraform apply` is interrupted, the lock may persist
- To remove a stuck lock:

```bash
# List locks
aws dynamodb scan --table-name jorss-gbo-dev-tf-locks --region us-east-1

# Force release (use cautiously)
aws dynamodb delete-item \
  --table-name jorss-gbo-dev-tf-locks \
  --key '{"LockID": {"S": "jorss-gbo-dev-tf-state/infra/terraform.tfstate-aws.amazonaws.com"}}' \
  --region us-east-1
```

## State Backup & Recovery

### Automatic Versioning

S3 versioning is enabled on the state bucket. To recover a previous state version:

```bash
# List state file versions
aws s3api list-object-versions \
  --bucket jorss-gbo-dev-tf-state \
  --prefix infra/terraform.tfstate \
  --region us-east-1

# Download a specific version
aws s3api get-object \
  --bucket jorss-gbo-dev-tf-state \
  --key infra/terraform.tfstate \
  --version-id <version-id> \
  --region us-east-1 \
  terraform.tfstate.backup
```

### Manual Backup

Before major changes, create a backup:

```bash
# Download current state
aws s3 cp s3://jorss-gbo-dev-tf-state/infra/terraform.tfstate \
         ./terraform.tfstate.backup \
         --region us-east-1

# Store backup securely (e.g., in git with .gitignored state files, or secure storage)
```

## Troubleshooting

### Issue: "Error acquiring the state lock"

**Cause**: Another team member is running `terraform apply`.

**Solution**: Wait for them to finish, or check if they crashed and released the lock.

### Issue: "AccessDenied" when pulling state

**Cause**: Missing IAM permissions for S3 or DynamoDB.

**Solution**: Ensure your IAM user/role has:
- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on `arn:aws:s3:::jorss-gbo-dev-tf-state/*`
- `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:DeleteItem` on the locks table

### Issue: State becomes corrupted

**Solution**: Use versioning to restore a previous good version.

## Environment-Specific Configuration

For different environments (dev, staging, production):

- Dev: `jorss-gbo-dev-tf-state` bucket, `jorss-gbo-dev-tf-locks` table
- Staging: `jorss-gbo-staging-tf-state` bucket, `jorss-gbo-staging-tf-locks` table
- Production: `jorss-gbo-prod-tf-state` bucket, `jorss-gbo-prod-tf-locks` table (with stricter access controls)

Configure which environment to use via `variables.tf`:

```bash
terraform apply -var="environment=staging"
```

## Enabling MFA Delete (Production Only)

For production, you can enable MFA-protected delete operations. This prevents accidental state deletion:

```bash
# 1. Enable MFA device on your AWS account
# 2. Uncomment the MFA delete section in backend.tf
# 3. Apply with MFA:
terraform apply -var-file="prod.tfvars"
```

## References

- [Terraform S3 Backend Documentation](https://www.terraform.io/language/settings/backends/s3)
- [AWS S3 Versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html)
- [AWS DynamoDB Point-in-Time Recovery](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/pointintimerecovery_howitworks.html)
