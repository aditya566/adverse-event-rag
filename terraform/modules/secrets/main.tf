# modules/secrets/main.tf
resource "aws_secretsmanager_secret" "main" {
  name                    = "${var.name}/app-secrets"
  description             = "Adverse Event RAG application secrets"
  recovery_window_in_days = 7
  tags                    = { Name = "${var.name}-secrets" }
}

resource "aws_secretsmanager_secret_version" "main" {
  secret_id = aws_secretsmanager_secret.main.id
  secret_string = jsonencode({
    ANTHROPIC_API_KEY = var.anthropic_api_key
    DB_PASSWORD       = var.db_password
    COMPANY_NAME      = var.company_name
    COMPANY_ADDRESS   = var.company_address
    COMPANY_PHONE     = var.company_phone
  })
}
