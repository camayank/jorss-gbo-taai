output "alb_dns_name" {
  description = "ALB DNS name for the staging environment"
  value       = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL for pushing images"
  value       = aws_ecr_repository.app.repository_url
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (primary, us-east-1)"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "rds_replica_endpoint" {
  description = "RDS read replica endpoint (us-west-2)"
  value       = try(aws_db_instance.postgres_replica_usw2[0].endpoint, null)
  sensitive   = true
}

output "rds_backup_retention_days" {
  description = "RDS automated backup retention period"
  value       = aws_db_instance.postgres.backup_retention_period
}

output "rds_multi_az_enabled" {
  description = "RDS Multi-AZ enabled"
  value       = aws_db_instance.postgres.multi_az
}

output "s3_bucket_name" {
  description = "S3 bucket name for document storage"
  value       = aws_s3_bucket.documents.id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS app service name"
  value       = aws_ecs_service.app.name
}

output "ecs_worker_service_name" {
  description = "ECS Celery worker service name"
  value       = aws_ecs_service.worker.name
}
