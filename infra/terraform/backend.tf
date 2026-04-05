# ===========================================================================
# Terraform State Backend Infrastructure
# ===========================================================================
# This file creates the S3 bucket and DynamoDB table for remote state
# management, enabling team collaboration on infrastructure.

# S3 bucket for Terraform state
resource "aws_s3_bucket" "terraform_state" {
  bucket = "${local.prefix}-tf-state"

  tags = {
    Name        = "${local.prefix}-terraform-state"
    Description = "Remote state storage for Terraform"
  }
}

# Enable versioning on state bucket for recovery
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status     = "Enabled"
    mfa_delete = "Disabled"
  }
}

# Server-side encryption for state at rest
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all public access to state bucket
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable MFA delete protection (requires bucket owner to enable in AWS console)
# resource "aws_s3_bucket_versioning" "terraform_state_mfa" {
#   bucket = aws_s3_bucket.terraform_state.id
#   versioning_configuration {
#     status     = "Enabled"
#     mfa_delete = "Enabled"  # Requires MFA for delete operations
#   }
# }

# DynamoDB table for state locking
resource "aws_dynamodb_table" "terraform_locks" {
  name           = "${local.prefix}-tf-locks"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery_specification {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Name        = "${local.prefix}-terraform-locks"
    Description = "State locking table for Terraform"
  }
}

# State backup policy: keep old versions in S3
# (versioning handles this automatically)

# Output the S3 bucket name for documentation
output "terraform_state_bucket" {
  description = "S3 bucket name for Terraform state"
  value       = aws_s3_bucket.terraform_state.id
  sensitive   = false
}

output "terraform_locks_table" {
  description = "DynamoDB table name for Terraform state locks"
  value       = aws_dynamodb_table.terraform_locks.name
  sensitive   = false
}
