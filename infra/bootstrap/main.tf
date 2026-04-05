# ===========================================================================
# Bootstrap: Terraform State Backend Infrastructure
# ===========================================================================
# PURPOSE: Run this ONCE before using infra/terraform/ for the first time.
#
# This config uses a LOCAL backend to create the S3 bucket and DynamoDB table
# that infra/terraform/ needs as its remote backend.
#
# After running this, infra/terraform/ can run `terraform init` successfully.
# The bootstrap state file (terraform.tfstate) should be committed to git or
# stored securely — it is the only record of these bootstrap resources.
#
# USAGE:
#   cd infra/bootstrap
#   terraform init
#   terraform apply -var="environment=dev"     # or staging, production
#
# ===========================================================================

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local backend — intentionally. This config creates the remote backend
  # resources so it cannot use them itself.
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      App         = var.app_name
      Environment = var.environment
      ManagedBy   = "terraform-bootstrap"
    }
  }
}

locals {
  prefix = "${var.app_name}-${var.environment}"
}

# ---------------------------------------------------------------------------
# S3 bucket for Terraform remote state
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "terraform_state" {
  bucket = "${local.prefix}-tf-state"

  # Prevent accidental deletion of this bucket which holds all Terraform state
  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name        = "${local.prefix}-terraform-state"
    Description = "Remote state storage for Terraform — managed by bootstrap"
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# DynamoDB table for Terraform state locking
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "${local.prefix}-tf-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name        = "${local.prefix}-terraform-locks"
    Description = "State locking table for Terraform — managed by bootstrap"
  }
}
