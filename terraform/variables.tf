variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used as prefix for all resources"
  type        = string
  default     = "adverse-event"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "prod"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Must be dev, staging, or prod."
  }
}

variable "anthropic_api_key" {
  description = "Anthropic API key (stored in Secrets Manager, not in state)"
  type        = string
  sensitive   = true
  default     = ""  # Leave empty if using Bedrock instead
}

variable "db_password" {
  description = "RDS PostgreSQL master password"
  type        = string
  sensitive   = true
}

variable "company_name" {
  description = "Insurance company name (printed on MedWatch reports)"
  type        = string
}

variable "company_address" {
  description = "Insurance company address"
  type        = string
}

variable "company_phone" {
  description = "Insurance company phone"
  type        = string
}

variable "bedrock_model_id" {
  description = "Amazon Bedrock Claude model ID"
  type        = string
  default     = "anthropic.claude-sonnet-4-5-20251001"
}

variable "ecr_image_uri" {
  description = "ECR image URI for the FastAPI review service"
  type        = string
  # Set after building and pushing your Docker image:
  # e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/adverse-event-review:latest
}

variable "alert_email" {
  description = "Email address for CloudWatch pipeline error alerts"
  type        = string
}

variable "batch_time_utc" {
  description = "Cron expression for daily batch in UTC (default 5PM ET = 21:00 UTC)"
  type        = string
  default     = "cron(0 21 * * ? *)"
}
