# infra/

Infrastructure-as-Code for the GBO CPA Tax AI Platform.

## Structure

```
infra/
  bootstrap/      — One-time setup: creates S3 + DynamoDB for Terraform backend
  terraform/      — Main AWS infrastructure (ECS, RDS, S3, ECR, VPC, ALB, CloudWatch)
  scripts/        — Operational scripts
  docs/           — Runbooks and guides
```

## Prerequisites

- Terraform >= 1.6
- AWS CLI configured with a profile that has permissions to manage ECS, RDS, S3, ECR, VPC, IAM, DynamoDB
- An existing AWS account

## First-Time Setup (New Environment)

The main Terraform config uses an S3 bucket + DynamoDB table as its remote state
backend. These resources must exist before `terraform init` can run — they cannot
be created by the same Terraform config that uses them.

**Run the bootstrap script once per environment:**

```bash
# Creates the S3 bucket + DynamoDB table, then initialises main Terraform
bash infra/scripts/bootstrap-tf-backend.sh dev
# or: staging, production
```

This script:
1. Runs `infra/bootstrap/` (local backend) to create `jorss-gbo-<env>-tf-state` and `jorss-gbo-<env>-tf-locks`
2. Runs `terraform init -migrate-state` in `infra/terraform/` to connect to the new backend

After bootstrap, you never need to run it again for that environment.

## Deploy

```bash
cd infra/terraform

# Copy and fill in the vars file
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set db_password, container_image, environment

terraform plan  -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

## Day-to-Day Operations

```bash
# Pull latest remote state and review changes
terraform plan -var-file=terraform.tfvars

# Apply changes
terraform apply -var-file=terraform.tfvars

# Destroy (use with caution — will prompt for confirmation)
terraform destroy -var-file=terraform.tfvars
```

## Troubleshooting

See `infra/terraform/BACKEND_SETUP.md` for state locking, state recovery, and
environment-specific backend configuration details.
