variable "aws_region" {
  description = "AWS region to create backend resources in"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (dev | staging | production)"
  type        = string
}

variable "app_name" {
  description = "Application name used in resource naming"
  type        = string
  default     = "jorss-gbo"
}
