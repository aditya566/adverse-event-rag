# modules/ecs/variables.tf
variable "name"                { type = string }
variable "vpc_id"              { type = string }
variable "public_subnet_ids"   { type = list(string) }
variable "private_subnet_ids"  { type = list(string) }
variable "review_queue_bucket" { type = string }
variable "reports_bucket"      { type = string }
variable "secrets_arn"         { type = string }
variable "db_host"             { type = string }
variable "db_name"             { type = string }
variable "aws_region"          { type = string }
variable "ecr_image_uri"       { type = string; default = "" }
variable "acm_certificate_arn" { type = string; default = "" }

# modules/ecs/outputs.tf
output "cluster_name"      { value = aws_ecs_cluster.main.name }
output "load_balancer_url" { value = "https://${aws_lb.main.dns_name}" }
output "ecr_repo_url"      { value = aws_ecr_repository.review.repository_url }
output "security_group_id" { value = aws_security_group.ecs.id }
