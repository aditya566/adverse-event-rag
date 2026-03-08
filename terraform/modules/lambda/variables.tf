# modules/lambda/variables.tf
variable "name"                  { type = string }
variable "vpc_id"                { type = string }
variable "subnet_ids"            { type = list(string) }
variable "crm_intake_bucket"     { type = string }
variable "pharma_docs_bucket"    { type = string }
variable "review_queue_bucket"   { type = string }
variable "reports_bucket"        { type = string }
variable "secrets_arn"           { type = string }
variable "db_host"               { type = string }
variable "db_name"               { type = string }
variable "aws_region"            { type = string }
variable "bedrock_model_id"      { type = string }

# modules/lambda/outputs.tf
output "pipeline_trigger_arn"  { value = aws_lambda_function.pipeline_trigger.arn }
output "pipeline_trigger_name" { value = aws_lambda_function.pipeline_trigger.function_name }
output "pharma_ingest_arn"     { value = aws_lambda_function.pharma_doc_ingest.arn }
output "pharma_ingest_name"    { value = aws_lambda_function.pharma_doc_ingest.function_name }
output "report_generator_arn"  { value = aws_lambda_function.report_generator.arn }
output "report_generator_name" { value = aws_lambda_function.report_generator.function_name }
output "security_group_id"     { value = aws_security_group.lambda.id }
