# modules/secrets/variables.tf
variable "name"              { type = string }
variable "anthropic_api_key" { type = string; sensitive = true; default = "" }
variable "db_password"       { type = string; sensitive = true }
variable "company_name"      { type = string }
variable "company_address"   { type = string }
variable "company_phone"     { type = string }

# modules/secrets/outputs.tf
output "secret_arn"  { value = aws_secretsmanager_secret.main.arn }
output "secret_name" { value = aws_secretsmanager_secret.main.name }
