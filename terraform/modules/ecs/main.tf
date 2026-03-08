# modules/ecs/main.tf
# ECS Fargate — FastAPI review UI
# 0.25 vCPU / 0.5GB RAM — ~$9/mo
# Behind an ALB with HTTPS

# ── ECR Repository ────────────────────────────────────────────────────────────
resource "aws_ecr_repository" "review" {
  name                 = "${var.name}-review"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }

  tags = { Name = "${var.name}-ecr" }
}

# ── ECS Cluster ───────────────────────────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "${var.name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = { Name = "${var.name}-cluster" }
}

# ── IAM Role for ECS Tasks ────────────────────────────────────────────────────
resource "aws_iam_role" "ecs_task" {
  name = "${var.name}-ecs-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task" {
  name = "${var.name}-ecs-task-policy"
  role = aws_iam_role.ecs_task.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.review_queue_bucket}",
          "arn:aws:s3:::${var.review_queue_bucket}/*",
          "arn:aws:s3:::${var.reports_bucket}",
          "arn:aws:s3:::${var.reports_bucket}/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.secrets_arn]
      },
      {
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role" "ecs_execution" {
  name = "${var.name}-ecs-execution-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ── Security Groups ───────────────────────────────────────────────────────────
resource "aws_security_group" "alb" {
  name        = "${var.name}-alb-sg"
  description = "ALB — allow HTTPS inbound"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]  # Redirect to HTTPS
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.name}-alb-sg" }
}

resource "aws_security_group" "ecs" {
  name        = "${var.name}-ecs-sg"
  description = "ECS tasks — allow from ALB only"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${var.name}-ecs-sg" }
}

# ── Application Load Balancer ─────────────────────────────────────────────────
resource "aws_lb" "main" {
  name               = "${var.name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids
  tags               = { Name = "${var.name}-alb" }
}

resource "aws_lb_target_group" "review" {
  name        = "${var.name}-review-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn  # Set to "" to use HTTP only for dev

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.review.arn
  }
}

# ── ECS Task Definition ───────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.name}-review"
  retention_in_days = 2555
}

resource "aws_ecs_task_definition" "review" {
  family                   = "${var.name}-review"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256   # 0.25 vCPU
  memory                   = 512   # 0.5 GB
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "review-api"
    image     = var.ecr_image_uri != "" ? var.ecr_image_uri : "${aws_ecr_repository.review.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]

    environment = [
      { name = "AWS_REGION_NAME",      value = var.aws_region },
      { name = "REVIEW_QUEUE_BUCKET",  value = var.review_queue_bucket },
      { name = "REPORTS_BUCKET",       value = var.reports_bucket },
      { name = "DB_HOST",              value = var.db_host },
      { name = "DB_NAME",              value = var.db_name },
    ]

    secrets = [{
      name      = "APP_SECRETS"
      valueFrom = var.secrets_arn
    }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])
}

# ── ECS Service ───────────────────────────────────────────────────────────────
resource "aws_ecs_service" "review" {
  name            = "${var.name}-review"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.review.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.review.arn
    container_name   = "review-api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.https]
}
