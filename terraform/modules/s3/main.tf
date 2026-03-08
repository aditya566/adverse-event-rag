# modules/s3/main.tf

locals {
  buckets = {
    crm_intake   = "${var.name}-crm-intake-${var.suffix}"
    pharma_docs  = "${var.name}-pharma-docs-${var.suffix}"
    review_queue = "${var.name}-review-queue-${var.suffix}"
    reports      = "${var.name}-reports-${var.suffix}"
  }
}

resource "aws_s3_bucket" "buckets" {
  for_each = local.buckets
  bucket   = each.value
  tags     = { Name = each.value, Purpose = each.key }
}

# Block ALL public access on every bucket
resource "aws_s3_bucket_public_access_block" "buckets" {
  for_each = aws_s3_bucket.buckets

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# SSE-S3 encryption on all buckets
resource "aws_s3_bucket_server_side_encryption_configuration" "buckets" {
  for_each = aws_s3_bucket.buckets
  bucket   = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Versioning on all buckets
resource "aws_s3_bucket_versioning" "buckets" {
  for_each = aws_s3_bucket.buckets
  bucket   = each.value.id
  versioning_configuration { status = "Enabled" }
}

# Lifecycle: auto-move old reports to Glacier after 90 days, delete after 7 years
resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.buckets["reports"].id

  rule {
    id     = "archive-reports"
    status = "Enabled"
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    expiration {
      days = 2555  # 7 years
    }
  }
}

# Lifecycle: clean up processed CRM notes after 30 days
resource "aws_s3_bucket_lifecycle_configuration" "crm_intake" {
  bucket = aws_s3_bucket.buckets["crm_intake"].id

  rule {
    id     = "cleanup-processed-notes"
    status = "Enabled"
    expiration { days = 30 }
  }
}

# S3 event notification: trigger Lambda when CRM note uploaded
resource "aws_s3_bucket_notification" "crm_intake" {
  bucket = aws_s3_bucket.buckets["crm_intake"].id

  lambda_function {
    lambda_function_arn = var.pipeline_lambda_arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".txt"
  }

  lambda_function {
    lambda_function_arn = var.pipeline_lambda_arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".csv"
  }

  depends_on = [var.pipeline_lambda_arn]
}

# S3 event notification: trigger Lambda when admin uploads pharma PDF
resource "aws_s3_bucket_notification" "pharma_docs" {
  bucket = aws_s3_bucket.buckets["pharma_docs"].id

  lambda_function {
    lambda_function_arn = var.ingest_lambda_arn
    events              = ["s3:ObjectCreated:*"]
    filter_suffix       = ".pdf"
  }

  depends_on = [var.ingest_lambda_arn]
}
