# modules/cloudwatch/variables.tf
variable "name"                  { type = string }
variable "pipeline_lambda_name"  { type = string }
variable "ingest_lambda_name"    { type = string }
variable "report_lambda_name"    { type = string }
variable "ecs_cluster_name"      { type = string }
variable "alert_email"           { type = string }
variable "log_retention_days"    { type = number; default = 2555 }
