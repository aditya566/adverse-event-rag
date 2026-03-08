# modules/lambda/main.tf
# Three Lambda functions:
#   1. pipeline-trigger   — fires on S3 CRM intake, runs classification
#   2. pharma-doc-ingest  — fires on S3 pharma-docs upload, indexes PDF
#   3. report-generator   — generates MedWatch 3500A PDF on demand

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── Shared IAM Role for all Lambda functions ──────────────────────────────────
resource "aws_iam_role" "lambda" {
  name = "${var.name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "${var.name}-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # CloudWatch Logs
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      },
      # S3 — read intake, write results
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.crm_intake_bucket}",
          "arn:aws:s3:::${var.crm_intake_bucket}/*",
          "arn:aws:s3:::${var.pharma_docs_bucket}",
          "arn:aws:s3:::${var.pharma_docs_bucket}/*",
          "arn:aws:s3:::${var.review_queue_bucket}",
          "arn:aws:s3:::${var.review_queue_bucket}/*",
          "arn:aws:s3:::${var.reports_bucket}",
          "arn:aws:s3:::${var.reports_bucket}/*",
        ]
      },
      # Secrets Manager
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.secrets_arn]
      },
      # Amazon Bedrock — invoke Claude
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
      },
      # VPC networking
      {
        Effect = "Allow"
        Action = ["ec2:CreateNetworkInterface", "ec2:DescribeNetworkInterfaces", "ec2:DeleteNetworkInterface"]
        Resource = "*"
      },
      # RDS connect via IAM auth
      {
        Effect   = "Allow"
        Action   = ["rds-db:connect"]
        Resource = "arn:aws:rds-db:${var.aws_region}:${data.aws_caller_identity.current.account_id}:dbuser:*/*"
      }
    ]
  })
}

# ── Security Group for Lambda functions ───────────────────────────────────────
resource "aws_security_group" "lambda" {
  name        = "${var.name}-lambda-sg"
  description = "Lambda functions security group"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.name}-lambda-sg" }
}

# ── Placeholder zip for initial deploy (real code deployed via CI/CD) ─────────
data "archive_file" "placeholder" {
  type        = "zip"
  output_path = "${path.module}/placeholder.zip"
  source {
    content  = "def handler(event, context): return {'statusCode': 200}"
    filename = "lambda_function.py"
  }
}

# ── Lambda 1: pipeline-trigger ────────────────────────────────────────────────
resource "aws_lambda_function" "pipeline_trigger" {
  function_name = "${var.name}-pipeline-trigger"
  role          = aws_iam_role.lambda.arn
  handler       = "lambda_handlers.pipeline_handler"
  runtime       = "python3.12"
  timeout       = 300  # 5 min
  memory_size   = 512

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      SECRETS_ARN          = var.secrets_arn
      DB_HOST              = var.db_host
      DB_NAME              = var.db_name
      REVIEW_QUEUE_BUCKET  = var.review_queue_bucket
      BEDROCK_MODEL_ID     = var.bedrock_model_id
      AWS_REGION_NAME      = var.aws_region
      ENABLE_PII_REDACTION = "true"
    }
  }

  tags = { Name = "${var.name}-pipeline-trigger" }
}

# Allow S3 to invoke this Lambda
resource "aws_lambda_permission" "s3_crm_intake" {
  statement_id  = "AllowS3CRMIntake"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pipeline_trigger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.crm_intake_bucket}"
}

# Allow EventBridge to invoke for daily batch
resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pipeline_trigger.function_name
  principal     = "scheduler.amazonaws.com"
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "pipeline_trigger" {
  name              = "/aws/lambda/${aws_lambda_function.pipeline_trigger.function_name}"
  retention_in_days = 2555
}

# ── Lambda 2: pharma-doc-ingest ───────────────────────────────────────────────
resource "aws_lambda_function" "pharma_doc_ingest" {
  function_name = "${var.name}-pharma-doc-ingest"
  role          = aws_iam_role.lambda.arn
  handler       = "lambda_handlers.ingest_handler"
  runtime       = "python3.12"
  timeout       = 900  # 15 min — PDF parsing can be slow
  memory_size   = 1024  # PDF parsing needs more memory

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      SECRETS_ARN      = var.secrets_arn
      DB_HOST          = var.db_host
      DB_NAME          = var.db_name
      PHARMA_DOCS_BUCKET = var.pharma_docs_bucket
      AWS_REGION_NAME  = var.aws_region
    }
  }

  tags = { Name = "${var.name}-pharma-doc-ingest" }
}

resource "aws_lambda_permission" "s3_pharma_docs" {
  statement_id  = "AllowS3PharmaDocsTrigger"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pharma_doc_ingest.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = "arn:aws:s3:::${var.pharma_docs_bucket}"
}

resource "aws_cloudwatch_log_group" "pharma_doc_ingest" {
  name              = "/aws/lambda/${aws_lambda_function.pharma_doc_ingest.function_name}"
  retention_in_days = 2555
}

# ── Lambda 3: report-generator ────────────────────────────────────────────────
resource "aws_lambda_function" "report_generator" {
  function_name = "${var.name}-report-generator"
  role          = aws_iam_role.lambda.arn
  handler       = "lambda_handlers.report_handler"
  runtime       = "python3.12"
  timeout       = 60
  memory_size   = 256

  filename         = data.archive_file.placeholder.output_path
  source_code_hash = data.archive_file.placeholder.output_base64sha256

  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      SECRETS_ARN    = var.secrets_arn
      REPORTS_BUCKET = var.reports_bucket
      AWS_REGION_NAME = var.aws_region
    }
  }

  tags = { Name = "${var.name}-report-generator" }
}

resource "aws_cloudwatch_log_group" "report_generator" {
  name              = "/aws/lambda/${aws_lambda_function.report_generator.function_name}"
  retention_in_days = 2555
}
