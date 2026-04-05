# ===========================================================================
# Terraform State Backend — NOTE
# ===========================================================================
# The S3 bucket and DynamoDB table used by this backend are created by the
# BOOTSTRAP config at infra/bootstrap/, NOT managed here.
#
# Why: Terraform cannot manage the resources it uses as its own state backend.
# Running `terraform apply` here to create an S3 bucket while Terraform is
# already configured to use that same bucket as its backend is a circular
# dependency — `terraform init` fails before any resources can be created.
#
# Solution: infra/bootstrap/ uses a local backend to create the S3 bucket
# and DynamoDB table once. After that, this main config can use them.
#
# To set up for a new environment, run:
#   bash infra/scripts/bootstrap-tf-backend.sh <environment>
#
# Backend configuration is in main.tf (terraform { backend "s3" { ... } }).
# ===========================================================================

# Output the backend bucket name for reference in CI/CD and documentation
output "terraform_state_bucket" {
  description = "S3 bucket name for Terraform state (created by infra/bootstrap)"
  value       = "${var.app_name}-${var.environment}-tf-state"
}

output "terraform_locks_table" {
  description = "DynamoDB table name for Terraform state locks (created by infra/bootstrap)"
  value       = "${var.app_name}-${var.environment}-tf-locks"
}
