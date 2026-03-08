# modules/s3/variables.tf
variable "name"               { type = string }
variable "suffix"             { type = string }
variable "environment"        { type = string }
variable "pipeline_lambda_arn" { type = string, default = "" }
variable "ingest_lambda_arn"   { type = string, default = "" }

# modules/s3/outputs.tf
output "crm_intake_bucket"   { value = aws_s3_bucket.buckets["crm_intake"].bucket }
output "pharma_docs_bucket"  { value = aws_s3_bucket.buckets["pharma_docs"].bucket }
output "review_queue_bucket" { value = aws_s3_bucket.buckets["review_queue"].bucket }
output "reports_bucket"      { value = aws_s3_bucket.buckets["reports"].bucket }
output "crm_intake_arn"      { value = aws_s3_bucket.buckets["crm_intake"].arn }
output "pharma_docs_arn"     { value = aws_s3_bucket.buckets["pharma_docs"].arn }
output "review_queue_arn"    { value = aws_s3_bucket.buckets["review_queue"].arn }
output "reports_arn"         { value = aws_s3_bucket.buckets["reports"].arn }
