output "state_bucket_name" {
  description = "S3 bucket name — use this as backend.bucket in infra/terraform/main.tf"
  value       = aws_s3_bucket.terraform_state.id
}

output "locks_table_name" {
  description = "DynamoDB table name — use this as backend.dynamodb_table in infra/terraform/main.tf"
  value       = aws_dynamodb_table.terraform_locks.name
}

output "next_step" {
  description = "What to do after bootstrap completes"
  value       = "cd ../terraform && terraform init (state migrates automatically to s3://${aws_s3_bucket.terraform_state.id})"
}
