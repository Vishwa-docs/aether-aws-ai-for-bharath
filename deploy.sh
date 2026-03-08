#!/bin/bash
# AETHER CareOps — AWS Deployment Script
# Deploys full app (FastAPI + React) to ECS Fargate
set -e

REGION="ap-south-1"
ACCOUNT_ID="841666121555"
ECR_REPO_NAME="aether-careops"
ECS_CLUSTER="aether-cluster"
ECS_SERVICE="aether-service"
ECS_TASK_FAMILY="aether-task"
CONTAINER_NAME="aether-app"
IMAGE_TAG="latest"
PORT=8080
ALB_DNS="aether-alb-1978968670.ap-south-1.elb.amazonaws.com"
TG_ARN="arn:aws:elasticloadbalancing:ap-south-1:841666121555:targetgroup/aether-tg/0bdca02f26471493"

echo "═══════════════════════════════════════════"
echo "  AETHER CareOps — AWS Deployment"
echo "═══════════════════════════════════════════"

# ── Step 1: Create ECR Repository ──────────────────────────
echo "▸ Creating ECR repository..."
aws ecr create-repository \
  --repository-name "$ECR_REPO_NAME" \
  --region "$REGION" \
  --image-scanning-configuration scanOnPush=false \
  2>/dev/null || echo "  (repository already exists)"

ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO_NAME"

# ── Step 2: Login to ECR ──────────────────────────────────
echo "▸ Logging in to ECR..."
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# ── Step 3: Build Docker Image ─────────────────────────────
echo "▸ Building Docker image..."
cd "$(dirname "$0")"
docker build --platform linux/amd64 -t "$ECR_REPO_NAME:$IMAGE_TAG" .

# ── Step 4: Tag and Push ───────────────────────────────────
echo "▸ Pushing to ECR..."
docker tag "$ECR_REPO_NAME:$IMAGE_TAG" "$ECR_URI:$IMAGE_TAG"
docker push "$ECR_URI:$IMAGE_TAG"

# ── Step 5: Create IAM Role for ECS Task ───────────────────
echo "▸ Setting up IAM roles..."
TASK_ROLE_NAME="aether-ecs-task-role"
EXEC_ROLE_NAME="aether-ecs-execution-role"

# Task execution role (for pulling images from ECR)
aws iam create-role \
  --role-name "$EXEC_ROLE_NAME" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "  (execution role already exists)"

aws iam attach-role-policy \
  --role-name "$EXEC_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy \
  2>/dev/null || true

# Task role (for accessing DynamoDB, Bedrock, Polly, S3)
aws iam create-role \
  --role-name "$TASK_ROLE_NAME" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "  (task role already exists)"

# Attach policies for DynamoDB, Bedrock, Polly, S3
aws iam attach-role-policy \
  --role-name "$TASK_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBReadOnlyAccess \
  2>/dev/null || true

aws iam attach-role-policy \
  --role-name "$TASK_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess \
  2>/dev/null || true

aws iam attach-role-policy \
  --role-name "$TASK_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonPollyReadOnlyAccess \
  2>/dev/null || true

aws iam attach-role-policy \
  --role-name "$TASK_ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess \
  2>/dev/null || true

# Bedrock access (custom inline policy)
aws iam put-role-policy \
  --role-name "$TASK_ROLE_NAME" \
  --policy-name "BedrockAccess" \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": "*"
    }]
  }' 2>/dev/null || true

# Wait for roles to propagate
echo "  Waiting for IAM propagation..."
sleep 10

# ── Step 6: Create ECS Cluster ─────────────────────────────
echo "▸ Creating ECS cluster..."
aws ecs create-cluster \
  --cluster-name "$ECS_CLUSTER" \
  --region "$REGION" \
  --capacity-providers FARGATE \
  --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
  2>/dev/null || echo "  (cluster already exists)"

# ── Step 7: Get Default VPC + Subnets ──────────────────────
echo "▸ Getting VPC configuration..."
DEFAULT_VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' --output text)

SUBNET_IDS=$(aws ec2 describe-subnets --region "$REGION" \
  --filters "Name=vpc-id,Values=$DEFAULT_VPC_ID" \
  --query 'Subnets[*].SubnetId' --output text | tr '\t' ',')

# Create security group
SG_NAME="aether-ecs-sg"
SG_ID=$(aws ec2 describe-security-groups --region "$REGION" \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$DEFAULT_VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  SG_ID=$(aws ec2 create-security-group --region "$REGION" \
    --group-name "$SG_NAME" \
    --description "AETHER ECS Security Group" \
    --vpc-id "$DEFAULT_VPC_ID" \
    --query 'GroupId' --output text)

  aws ec2 authorize-security-group-ingress --region "$REGION" \
    --group-id "$SG_ID" \
    --protocol tcp --port "$PORT" --cidr 0.0.0.0/0
fi

echo "  VPC: $DEFAULT_VPC_ID"
echo "  Security Group: $SG_ID"

# ── Step 8: Register Task Definition ──────────────────────
echo "▸ Registering task definition..."
EXEC_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${EXEC_ROLE_NAME}"
TASK_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${TASK_ROLE_NAME}"

aws ecs register-task-definition \
  --region "$REGION" \
  --family "$ECS_TASK_FAMILY" \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu 512 \
  --memory 1024 \
  --execution-role-arn "$EXEC_ROLE_ARN" \
  --task-role-arn "$TASK_ROLE_ARN" \
  --container-definitions "[{
    \"name\": \"$CONTAINER_NAME\",
    \"image\": \"$ECR_URI:$IMAGE_TAG\",
    \"portMappings\": [{\"containerPort\": $PORT, \"protocol\": \"tcp\"}],
    \"essential\": true,
    \"environment\": [
      {\"name\": \"PORT\", \"value\": \"$PORT\"},
      {\"name\": \"AWS_REGION\", \"value\": \"$REGION\"},
      {\"name\": \"BEDROCK_MODEL_ID\", \"value\": \"apac.amazon.nova-lite-v1:0\"}
    ],
    \"logConfiguration\": {
      \"logDriver\": \"awslogs\",
      \"options\": {
        \"awslogs-group\": \"/ecs/aether\",
        \"awslogs-region\": \"$REGION\",
        \"awslogs-stream-prefix\": \"ecs\",
        \"awslogs-create-group\": \"true\"
      }
    }
  }]" > /dev/null

# ── Step 9: Create/Update ECS Service ─────────────────────
echo "▸ Deploying ECS service..."

# Check if service already exists
EXISTING=$(aws ecs describe-services --region "$REGION" \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE" \
  --query 'services[?status==`ACTIVE`].serviceName' \
  --output text 2>/dev/null)

if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  echo "  Updating existing service..."
  aws ecs update-service \
    --region "$REGION" \
    --cluster "$ECS_CLUSTER" \
    --service "$ECS_SERVICE" \
    --force-new-deployment \
    --task-definition "$ECS_TASK_FAMILY" > /dev/null
else
  echo "  Creating new service with ALB..."
  aws ecs create-service \
    --region "$REGION" \
    --cluster "$ECS_CLUSTER" \
    --service-name "$ECS_SERVICE" \
    --task-definition "$ECS_TASK_FAMILY" \
    --desired-count 1 \
    --launch-type FARGATE \
    --load-balancers "targetGroupArn=$TG_ARN,containerName=$CONTAINER_NAME,containerPort=$PORT" \
    --network-configuration "awsvpcConfiguration={
      subnets=[$(echo $SUBNET_IDS | sed 's/,/,/g')],
      securityGroups=[$SG_ID],
      assignPublicIp=ENABLED
    }" > /dev/null
fi

# ── Step 10: Wait and verify via ALB ──────────────────────
echo ""
echo "▸ Waiting for task to start and register with ALB..."
sleep 30

for i in $(seq 1 12); do
  HEALTH=$(aws elbv2 describe-target-health --region "$REGION" \
    --target-group-arn "$TG_ARN" \
    --query 'TargetHealthDescriptions[0].TargetHealth.State' \
    --output text 2>/dev/null)

  if [ "$HEALTH" = "healthy" ]; then
    echo ""
    echo "═══════════════════════════════════════════"
    echo "  ✅ AETHER CareOps is LIVE!"
    echo ""
    echo "  🌐 Dashboard:  http://$ALB_DNS"
    echo "  📡 API Docs:   http://$ALB_DNS/docs"
    echo "  💡 Health:     http://$ALB_DNS/api/health"
    echo "═══════════════════════════════════════════"
    exit 0
  fi

  echo "  Waiting for health check... ($((i*10))s) [status: $HEALTH]"
  sleep 10
done

echo ""
echo "⏳ Service is still starting. Check:"
echo "   http://$ALB_DNS"
echo "   https://$REGION.console.aws.amazon.com/ecs/home?region=$REGION#/clusters/$ECS_CLUSTER/services/$ECS_SERVICE"
