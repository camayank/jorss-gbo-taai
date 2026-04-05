# ===========================================================================
# AWS Secrets Manager — IRS Credentials (EFIN/ETIN) + MeF API credentials
# ===========================================================================
# This file manages secrets for IRS e-File credentials which have manual
# rotation requirements and sensitive access logging needs.

# Secrets for production environment only
locals {
  # Secrets paths follow: {env}/irs/{credential_type}
  secrets_config = {
    efin = {
      name        = "prod/irs/efin"
      description = "IRS EFIN (Electronic File Identification Number) for e-File platform authorization"
    }
    etin = {
      name        = "prod/irs/etin"
      description = "IRS ETIN (Electronic Transmitter Identification Number) for e-File platform authorization"
    }
    mef_api = {
      name        = "prod/mef/api-credentials"
      description = "MeF (My e-File) API credentials for IRS e-File submission"
    }
  }
}

# ===========================================================================
# Secrets Manager — IRS EFIN
# ===========================================================================
resource "aws_secretsmanager_secret" "irs_efin" {
  name                    = "prod/irs/efin"
  description             = local.secrets_config.efin.description
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.secrets.id

  tags = {
    Name        = "prod-irs-efin"
    Service     = "e-file"
    Sensitivity = "high"
    RotationPolicySoftware::Manual = "true"
  }

  depends_on = [aws_kms_key.secrets]
}

# ===========================================================================
# Secrets Manager — IRS ETIN
# ===========================================================================
resource "aws_secretsmanager_secret" "irs_etin" {
  name                    = "prod/irs/etin"
  description             = local.secrets_config.etin.description
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.secrets.id

  tags = {
    Name        = "prod-irs-etin"
    Service     = "e-file"
    Sensitivity = "high"
    RotationPolicy = "Manual"
  }

  depends_on = [aws_kms_key.secrets]
}

# ===========================================================================
# Secrets Manager — MeF API Credentials
# ===========================================================================
resource "aws_secretsmanager_secret" "mef_api_credentials" {
  name                    = "prod/mef/api-credentials"
  description             = local.secrets_config.mef_api.description
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.secrets.id

  tags = {
    Name        = "prod-mef-api-credentials"
    Service     = "e-file"
    Sensitivity = "high"
    RotationPolicy = "Manual"
  }

  depends_on = [aws_kms_key.secrets]
}

# ===========================================================================
# KMS Key for Secrets Manager encryption (at-rest)
# ===========================================================================
resource "aws_kms_key" "secrets" {
  description             = "KMS key for encrypting secrets in AWS Secrets Manager"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Allow Secrets Manager to use this key
      {
        Sid    = "Allow Secrets Manager"
        Effect = "Allow"
        Principal = {
          Service = "secretsmanager.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      # Allow ECS task execution role to decrypt secrets
      {
        Sid    = "Allow ECS Task Execution Role"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.ecs_task_execution.arn
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      # Allow account root for administrative access
      {
        Sid    = "Enable IAM Root"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      }
    ]
  })

  tags = { Name = "prod-secrets-key" }
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/prod-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# ===========================================================================
# Data source — current AWS account
# ===========================================================================
data "aws_caller_identity" "current" {}

# ===========================================================================
# CloudTrail for Secrets Manager audit logging
# ===========================================================================
# S3 bucket for CloudTrail logs
resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket = "${local.prefix}-cloudtrail-logs"

  tags = { Name = "${local.prefix}-cloudtrail-logs" }
}

resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket                  = aws_s3_bucket.cloudtrail_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.cloudtrail_logs.arn
      },
      {
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.cloudtrail_logs.arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      }
    ]
  })
}

# ===========================================================================
# CloudTrail trail for Secrets Manager API calls
# ===========================================================================
resource "aws_cloudtrail" "secrets_audit" {
  name                          = "${local.prefix}-secrets-audit"
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true
  depends_on                    = [aws_s3_bucket_policy.cloudtrail_logs]

  # Log all events for secrets (data events)
  event_selector {
    read_write_type           = "All"
    include_management_events = true

    # Track GetSecretValue, PutSecretValue, DeleteSecret, UpdateSecret, etc.
    data_resource {
      type   = "AWS::SecretsManager::Secret"
      values = ["arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:prod/*"]
    }
  }

  tags = { Name = "${local.prefix}-secrets-audit" }
}

# ===========================================================================
# IAM Policy — Allow ECS to read IRS secrets from Secrets Manager
# ===========================================================================
resource "aws_iam_role_policy" "ecs_secrets_manager" {
  name = "${local.prefix}-ecs-secrets-manager"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetIRSSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.irs_efin.arn,
          aws_secretsmanager_secret.irs_etin.arn,
          aws_secretsmanager_secret.mef_api_credentials.arn
        ]
      },
      {
        Sid    = "DecryptSecrets"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.secrets.arn
      }
    ]
  })
}

# ===========================================================================
# CloudWatch Log Group for Secrets Manager events
# ===========================================================================
resource "aws_cloudwatch_log_group" "secrets_events" {
  name              = "/aws/secretsmanager/${local.prefix}"
  retention_in_days = 90

  tags = { Name = "${local.prefix}-secrets-events" }
}

# ===========================================================================
# EventBridge Rule — Alert on secret access (audit)
# ===========================================================================
resource "aws_cloudwatch_event_rule" "secrets_access" {
  name        = "${local.prefix}-secrets-access-audit"
  description = "Log all Secrets Manager GetSecretValue calls for IRS credentials"

  event_pattern = jsonencode({
    source      = ["aws.secretsmanager"]
    detail-type = ["AWS API Call via CloudTrail"]
    detail = {
      eventName = ["GetSecretValue", "UpdateSecret", "DeleteSecret"]
      requestParameters = {
        secretId = [
          aws_secretsmanager_secret.irs_efin.name,
          aws_secretsmanager_secret.irs_etin.name,
          aws_secretsmanager_secret.mef_api_credentials.name
        ]
      }
    }
  })
}

resource "aws_cloudwatch_event_target" "secrets_access_log" {
  rule      = aws_cloudwatch_event_rule.secrets_access.name
  target_id = "SecretsAuditLog"
  arn       = aws_cloudwatch_log_group.secrets_events.arn
}

# ===========================================================================
# CloudWatch Alarm — Unauthorized secret access attempt
# ===========================================================================
resource "aws_cloudwatch_log_metric_filter" "secrets_unauthorized_access" {
  name           = "${local.prefix}-secrets-unauthorized-access"
  log_group_name = aws_cloudwatch_log_group.secrets_events.name
  filter_pattern = "{ $.errorCode = \"AccessDenied*\" || $.errorCode = \"UnauthorizedOperation\" }"

  metric_transformation {
    name          = "UnauthorizedSecretAccess"
    namespace     = "SecretsManager/Security"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "secrets_unauthorized_access" {
  alarm_name          = "${local.prefix}-secrets-unauthorized-access"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "UnauthorizedSecretAccess"
  namespace           = "SecretsManager/Security"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Alert on unauthorized attempt to access IRS credentials"
  alarm_actions       = [aws_sns_topic.critical_alerts.arn]
  treat_missing_data  = "notBreaching"
}

# ===========================================================================
# Outputs
# ===========================================================================
output "secrets_arns" {
  description = "ARNs of created Secrets Manager secrets"
  value = {
    efin              = aws_secretsmanager_secret.irs_efin.arn
    etin              = aws_secretsmanager_secret.irs_etin.arn
    mef_api_creds     = aws_secretsmanager_secret.mef_api_credentials.arn
  }
  sensitive = true
}

output "cloudtrail_s3_bucket" {
  description = "S3 bucket for CloudTrail logs (for audit trail review)"
  value       = aws_s3_bucket.cloudtrail_logs.id
}

output "kms_key_id" {
  description = "KMS key ID used for secrets encryption"
  value       = aws_kms_key.secrets.key_id
}
