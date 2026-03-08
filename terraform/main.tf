terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }

  # Uncomment to store state in S3 (recommended for teams)
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "adverse-event-rag/terraform.tfstate"
  #   region = "us-east-1"
  #   encrypt = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "adverse-event-rag"
      Environment = var.environment
      ManagedBy   = "terraform"
      HIPAAScope  = "true"
    }
  }
}

# ── Random suffix to ensure globally unique S3 bucket names ──────────────────
resource "random_id" "suffix" {
  byte_length = 4
}

locals {
  suffix = random_id.suffix.hex
  name   = "${var.project_name}-${var.environment}"
}

# ── Modules ───────────────────────────────────────────────────────────────────

module "vpc" {
  source       = "./modules/vpc"
  name         = local.name
  environment  = var.environment
}

module "secrets" {
  source           = "./modules/secrets"
  name             = local.name
  anthropic_api_key = var.anthropic_api_key
  db_password      = var.db_password
  company_name     = var.company_name
  company_address  = var.company_address
  company_phone    = var.company_phone
}

module "s3" {
  source      = "./modules/s3"
  name        = local.name
  suffix      = local.suffix
  environment = var.environment
}

module "rds" {
  source             = "./modules/rds"
  name               = local.name
  vpc_id             = module.vpc.vpc_id
  subnet_ids         = module.vpc.private_subnet_ids
  db_password        = var.db_password
  lambda_sg_id       = module.lambda.security_group_id
  ecs_sg_id          = module.ecs.security_group_id
}

module "lambda" {
  source                    = "./modules/lambda"
  name                      = local.name
  vpc_id                    = module.vpc.vpc_id
  subnet_ids                = module.vpc.private_subnet_ids
  crm_intake_bucket         = module.s3.crm_intake_bucket
  pharma_docs_bucket        = module.s3.pharma_docs_bucket
  review_queue_bucket       = module.s3.review_queue_bucket
  reports_bucket            = module.s3.reports_bucket
  secrets_arn               = module.secrets.secret_arn
  db_host                   = module.rds.db_host
  db_name                   = module.rds.db_name
  aws_region                = var.aws_region
  bedrock_model_id          = var.bedrock_model_id
}

module "ecs" {
  source                = "./modules/ecs"
  name                  = local.name
  vpc_id                = module.vpc.vpc_id
  public_subnet_ids     = module.vpc.public_subnet_ids
  private_subnet_ids    = module.vpc.private_subnet_ids
  review_queue_bucket   = module.s3.review_queue_bucket
  reports_bucket        = module.s3.reports_bucket
  secrets_arn           = module.secrets.secret_arn
  db_host               = module.rds.db_host
  db_name               = module.rds.db_name
  aws_region            = var.aws_region
  ecr_image_uri         = var.ecr_image_uri
}

module "eventbridge" {
  source              = "./modules/eventbridge"
  name                = local.name
  pipeline_lambda_arn = module.lambda.pipeline_trigger_arn
  batch_time_utc      = var.batch_time_utc
}

module "cloudwatch" {
  source                    = "./modules/cloudwatch"
  name                      = local.name
  pipeline_lambda_name      = module.lambda.pipeline_trigger_name
  ingest_lambda_name        = module.lambda.pharma_ingest_name
  report_lambda_name        = module.lambda.report_generator_name
  ecs_cluster_name          = module.ecs.cluster_name
  alert_email               = var.alert_email
  log_retention_days        = 2555  # 7 years — 21 CFR Part 314
}
