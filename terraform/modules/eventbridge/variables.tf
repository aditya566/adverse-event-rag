# modules/eventbridge/variables.tf
variable "name"                { type = string }
variable "pipeline_lambda_arn" { type = string }
variable "batch_time_utc"      { type = string }
