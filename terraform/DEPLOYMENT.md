# AWS Deployment Guide
# Adverse Event RAG — Terraform

## Prerequisites
- Terraform >= 1.6 installed (`brew install terraform` or https://developer.hashicorp.com/terraform/install)
- AWS CLI configured (`aws configure`) with an IAM user that has AdministratorAccess
- Docker installed (for building the review API image)

---

## Step 1 — Sign the AWS HIPAA BAA (do this first)
```
AWS Console → My Account → AWS Artifact → Agreements
→ Find "AWS Business Associate Addendum" → Accept
```
This is free and takes 5 minutes. Required before storing any PHI.

---

## Step 2 — Enable Amazon Bedrock Claude access
```
AWS Console → Amazon Bedrock → Model access
→ Request access for: Anthropic Claude Sonnet
```
Takes ~10 minutes to approve.

---

## Step 3 — Build and push the review API Docker image

```bash
# From your adverse-event-rag project root
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1

# Create ECR repo (if not already created by Terraform)
aws ecr create-repository --repository-name adverse-event-review --region $REGION

# Authenticate Docker to ECR
aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# Build and push
docker build -t adverse-event-review .
docker tag adverse-event-review:latest \
  $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/adverse-event-review:latest
docker push \
  $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/adverse-event-review:latest

echo "ECR image URI:"
echo "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/adverse-event-review:latest"
```
Copy the ECR image URI — you'll need it in the next step.

---

## Step 4 — Configure Terraform variables

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` and fill in:
- `db_password` — strong password (32+ chars)
- `company_name`, `company_address`, `company_phone`
- `ecr_image_uri` — from Step 3
- `alert_email` — your team email for pipeline error alerts

---

## Step 5 — Deploy

```bash
cd terraform/

# Initialize providers and modules
terraform init

# Preview what will be created (always do this first)
terraform plan

# Deploy everything
terraform apply
```

Type `yes` when prompted. Takes ~10-15 minutes for RDS to come up.

After apply completes, you'll see outputs like:
```
crm_intake_bucket  = "adverse-event-prod-crm-intake-a1b2c3d4"
pharma_docs_bucket = "adverse-event-prod-pharma-docs-a1b2c3d4"
review_ui_url      = "https://adverse-event-prod-alb-123456.us-east-1.elb.amazonaws.com"
```

---

## Step 6 — Initialize the database (pgvector)

Connect to RDS via the AWS console Query Editor or a bastion/SSM session:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pharma_doc_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drug_name TEXT NOT NULL,
    manufacturer TEXT,
    doc_version TEXT,
    source_doc TEXT,
    section TEXT,
    page_num INTEGER,
    is_high_priority BOOLEAN DEFAULT FALSE,
    file_hash TEXT,
    content TEXT NOT NULL,
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pharma_chunks_embedding_idx
ON pharma_doc_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 50);

CREATE INDEX IF NOT EXISTS pharma_chunks_drug_idx
ON pharma_doc_chunks (drug_name);
```

---

## Step 7 — Deploy Lambda function code

```bash
# From project root — package and deploy each Lambda
pip install -r requirements.txt -t ./lambda_package/
cp -r . ./lambda_package/
cd lambda_package && zip -r ../lambda.zip . && cd ..

# Deploy pipeline-trigger
aws lambda update-function-code \
  --function-name adverse-event-prod-pipeline-trigger \
  --zip-file fileb://lambda.zip

# Deploy pharma-doc-ingest
aws lambda update-function-code \
  --function-name adverse-event-prod-pharma-doc-ingest \
  --zip-file fileb://lambda.zip

# Deploy report-generator
aws lambda update-function-code \
  --function-name adverse-event-prod-report-generator \
  --zip-file fileb://lambda.zip
```

---

## Step 8 — Test the pipeline end to end

```bash
# Upload a test chart note to S3
aws s3 cp sample_data/chart_notes/sample_chart_note_001.txt \
  s3://adverse-event-prod-crm-intake-XXXX/

# Watch the Lambda logs in real time
aws logs tail /aws/lambda/adverse-event-prod-pipeline-trigger --follow
```

---

## Step 9 — Upload your first pharma PDF (admin)

```bash
aws s3 cp lipitor_prescribing_info.pdf \
  s3://adverse-event-prod-pharma-docs-XXXX/lipitor/ \
  --metadata "drug_name=Lipitor,manufacturer=Pfizer,version=2024-09"
```

S3 automatically triggers the ingest Lambda. Watch logs:
```bash
aws logs tail /aws/lambda/adverse-event-prod-pharma-doc-ingest --follow
```

---

## Estimated Monthly Cost

| Service | Cost |
|---|---|
| RDS db.t4g.micro | ~$15 |
| ECS Fargate (0.25 vCPU) | ~$9 |
| Lambda (50 cases/day) | ~$0 (free tier) |
| S3 (all 4 buckets) | ~$1 |
| Bedrock Claude (50 cases) | ~$3–8 |
| NAT Gateway | ~$5 |
| Secrets Manager | ~$1 |
| CloudWatch | ~$2 |
| **Total** | **~$36–41/mo** |

---

## Tear Down (dev/staging only)

```bash
terraform destroy
```
⚠️ RDS has `deletion_protection = true` — disable it first in the console or set it to false in `modules/rds/main.tf` before destroying.
