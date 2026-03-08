output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "crm_intake_bucket" {
  description = "Drop CRM chart note exports here"
  value       = module.s3.crm_intake_bucket
}

output "pharma_docs_bucket" {
  description = "Admin uploads pharma PDFs here"
  value       = module.s3.pharma_docs_bucket
}

output "review_queue_bucket" {
  description = "Classification results land here"
  value       = module.s3.review_queue_bucket
}

output "reports_bucket" {
  description = "Generated MedWatch PDFs stored here"
  value       = module.s3.reports_bucket
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint (pgvector)"
  value       = module.rds.db_host
  sensitive   = true
}

output "review_ui_url" {
  description = "URL for the advocate review dashboard"
  value       = module.ecs.load_balancer_url
}

output "pipeline_lambda_arn" {
  description = "ARN of the pipeline trigger Lambda"
  value       = module.lambda.pipeline_trigger_arn
}

output "secrets_arn" {
  description = "Secrets Manager ARN"
  value       = module.secrets.secret_arn
  sensitive   = true
}
