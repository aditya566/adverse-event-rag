# modules/cloudwatch/main.tf
# Log groups (7-year retention) + pipeline error alerting

# ── SNS Topic for alerts ──────────────────────────────────────────────────────
resource "aws_sns_topic" "alerts" {
  name = "${var.name}-pipeline-alerts"
  tags = { Name = "${var.name}-alerts" }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── CloudWatch Alarms ─────────────────────────────────────────────────────────

# Alert if pipeline Lambda errors
resource "aws_cloudwatch_metric_alarm" "pipeline_errors" {
  alarm_name          = "${var.name}-pipeline-errors"
  alarm_description   = "Pipeline Lambda threw an error — check for failed classifications"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = { FunctionName = var.pipeline_lambda_name }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# Alert if ingest Lambda errors (PDF ingestion failed)
resource "aws_cloudwatch_metric_alarm" "ingest_errors" {
  alarm_name          = "${var.name}-ingest-errors"
  alarm_description   = "Pharma doc ingest Lambda failed — PDF may not have been indexed"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"

  dimensions = { FunctionName = var.ingest_lambda_name }
  alarm_actions = [aws_sns_topic.alerts.arn]
}

# Alert if RDS CPU > 80% (shouldn't happen at small scale, but good to know)
resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${var.name}-rds-high-cpu"
  alarm_description   = "RDS CPU usage is high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts.arn]
}

# ── CloudWatch Dashboard ──────────────────────────────────────────────────────
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title  = "Lambda Invocations & Errors"
          period = 3600
          stat   = "Sum"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.pipeline_lambda_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.pipeline_lambda_name],
            ["AWS/Lambda", "Invocations", "FunctionName", var.ingest_lambda_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.ingest_lambda_name],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "Lambda Duration (ms)"
          period = 3600
          stat   = "Average"
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.pipeline_lambda_name],
            ["AWS/Lambda", "Duration", "FunctionName", var.ingest_lambda_name],
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title   = "RDS CPU & Connections"
          period  = 300
          metrics = [
            ["AWS/RDS", "CPUUtilization"],
            ["AWS/RDS", "DatabaseConnections"],
          ]
        }
      }
    ]
  })
}
