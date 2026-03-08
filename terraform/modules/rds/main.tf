# modules/rds/main.tf
# PostgreSQL 16 with pgvector extension
# t4g.micro (~$15/mo) in private subnet — no public access

resource "aws_db_subnet_group" "main" {
  name       = "${var.name}-db-subnet-group"
  subnet_ids = var.subnet_ids
  tags       = { Name = "${var.name}-db-subnet-group" }
}

resource "aws_security_group" "rds" {
  name        = "${var.name}-rds-sg"
  description = "Allow PostgreSQL from Lambda and ECS only"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from Lambda"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.lambda_sg_id]
  }

  ingress {
    description     = "PostgreSQL from ECS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.ecs_sg_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.name}-rds-sg" }
}

resource "aws_db_instance" "main" {
  identifier = "${var.name}-postgres"

  # Engine
  engine               = "postgres"
  engine_version       = "16.3"
  instance_class       = "db.t4g.micro"  # ~$15/mo

  # Storage
  allocated_storage     = 20
  max_allocated_storage = 100  # Auto-scaling up to 100GB
  storage_type          = "gp3"
  storage_encrypted     = true  # Required for HIPAA

  # Database
  db_name  = "adverse_events"
  username = "dbadmin"
  password = var.db_password

  # Network
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false  # Never expose to internet

  # Backups — 7 days automated, required for HIPAA
  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  # HIPAA requirements
  deletion_protection      = true
  skip_final_snapshot      = false
  final_snapshot_identifier = "${var.name}-final-snapshot"
  copy_tags_to_snapshot    = true

  # Performance Insights (free tier, useful for debugging)
  performance_insights_enabled = true

  tags = { Name = "${var.name}-postgres" }
}

# ── pgvector setup via SSM Run Command (runs once after DB creation) ──────────
# Note: Run this SQL manually after first apply, or via a Lambda custom resource:
#
# CREATE EXTENSION IF NOT EXISTS vector;
#
# CREATE TABLE IF NOT EXISTS pharma_doc_chunks (
#     id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
#     drug_name TEXT NOT NULL,
#     manufacturer TEXT,
#     doc_version TEXT,
#     source_doc TEXT,
#     section TEXT,
#     page_num INTEGER,
#     is_high_priority BOOLEAN DEFAULT FALSE,
#     file_hash TEXT,
#     content TEXT NOT NULL,
#     embedding vector(768),
#     created_at TIMESTAMPTZ DEFAULT NOW()
# );
#
# CREATE INDEX IF NOT EXISTS pharma_chunks_embedding_idx
# ON pharma_doc_chunks USING ivfflat (embedding vector_cosine_ops)
# WITH (lists = 50);
#
# CREATE INDEX IF NOT EXISTS pharma_chunks_drug_idx
# ON pharma_doc_chunks (drug_name);
#
# See docs/DB_SETUP.md for the full setup script.
