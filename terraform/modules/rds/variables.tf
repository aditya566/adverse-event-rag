# modules/rds/variables.tf
variable "name"          { type = string }
variable "vpc_id"        { type = string }
variable "subnet_ids"    { type = list(string) }
variable "db_password"   { type = string; sensitive = true }
variable "lambda_sg_id"  { type = string }
variable "ecs_sg_id"     { type = string }

# modules/rds/outputs.tf
output "db_host"              { value = aws_db_instance.main.address }
output "db_name"              { value = aws_db_instance.main.db_name }
output "db_port"              { value = aws_db_instance.main.port }
output "rds_security_group_id" { value = aws_security_group.rds.id }
