# modules/eventbridge/main.tf
# Daily batch scheduler — triggers pipeline Lambda at 5PM ET (9PM UTC)

resource "aws_iam_role" "scheduler" {
  name = "${var.name}-scheduler-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "${var.name}-scheduler-policy"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = [var.pipeline_lambda_arn]
    }]
  })
}

resource "aws_scheduler_schedule" "daily_batch" {
  name        = "${var.name}-daily-batch"
  description = "Daily adverse event report batch — 5PM ET"

  flexible_time_window {
    mode                      = "FLEXIBLE"
    maximum_window_in_minutes = 5
  }

  schedule_expression          = var.batch_time_utc
  schedule_expression_timezone = "UTC"

  target {
    arn      = var.pipeline_lambda_arn
    role_arn = aws_iam_role.scheduler.arn

    input = jsonencode({
      source    = "eventbridge-daily-batch"
      batch_run = true
    })

    retry_policy {
      maximum_retry_attempts = 2
    }
  }
}
