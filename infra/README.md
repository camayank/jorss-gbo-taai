# infra/

Infrastructure-as-Code for the GBO CPA Tax AI Platform.

## Structure
- `infra/terraform/` — AWS resources: ECS, RDS, S3, ECR, VPC

## Prerequisites
- Terraform >= 1.6
- AWS CLI configured with a profile that has permissions to manage ECS, RDS, S3, ECR, VPC, IAM
- An existing AWS account and region set in `infra/terraform/terraform.tfvars`

## Deploy
```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```
