# Setup & Deployment Guide

## Prerequisites

### AWS Account Requirements
- Active AWS account with us-east-1 region
- IAM permissions to create:
  - Bedrock resources (Knowledge Base, AgentCore, Memory)
  - Lambda functions
  - API Gateway
  - S3 buckets (for Knowledge Base)
  - IAM roles and policies

### Local Development
- Python 3.13 or higher
- [uv](https://docs.astral.sh/uv/) - Python package manager
- [AWS CLI](https://aws.amazon.com/cli/) v2
- AgentCore CLI (installed via dependencies)
- Node.js 18+ (for MCP Inspector, optional)

### Model Access
Enable in [Amazon Bedrock Console](https://us-east-1.console.aws.amazon.com/bedrock):
- **Amazon Nova 2 Lite** (`amazon.nova-2-lite-v1:0`)

## Step 1: Initial Setup

### 1.1 Clone and Environment Setup
```bash
cd starter
uv sync --python 3.13
```

This installs all dependencies from `pyproject.toml`:
- bedrock-agentcore>=1.4.1
- strands-agents>=1.28.0
- boto3
- playwright
- mcp
- strands-tools
- Other required packages

### 1.2 AWS Credentials
```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Set region to: us-east-1
# Set output format: json
```

## Step 2: AWS Infrastructure

### 2.1 Initialize AgentCore Project
```bash
uv run agentcore init
```

Follow prompts to:
- Name your agent
- Select runtime type
- Configure AWS region

### 2.2 Create Knowledge Base

**In AWS Console (us-east-1):**
1. Go to **Amazon Bedrock** → **Knowledge bases**
2. Click **Create knowledge base**
3. Configure:
   - Name: `customer-support-kb`
   - Embedding model: Default
   - S3 bucket: Create new
4. Upload `product_catalog.txt` as data source
5. Copy the **Knowledge Base ID** (10-character code)

### 2.3 Create Memory Resource

**In AWS Console:**
1. Go to **Amazon Bedrock** → **Memory**
2. Click **Create Memory**
3. Configure:
   - Name: `CustomerSupportMemory`
   - Add strategies: SEMANTIC, USER_PREFERENCE
4. Copy the **Memory ID** (format: Name-10chars)

### 2.4 Create Gateway (MCP Integration)

**In AWS Console:**
1. Go to **Bedrock AgentCore** → **Gateway**
2. Click **Create gateway**
3. Configure:
   - Name: `customer-support-gateway`
   - Authorizer: NONE (for development)
4. Copy the **Gateway URL** (ends with `/mcp`)

### 2.5 Deploy Lambda Functions

**Order Tracker:**
```bash
cd starter/lambda
zip order_tracker.zip order_tracker.py
aws lambda create-function \
  --function-name order-tracker \
  --runtime python3.13 \
  --role <your-lambda-role-arn> \
  --handler order_tracker.lambda_handler \
  --zip-file fileb://order_tracker.zip
```

**Refund Processor:**
```bash
zip refund_processor.zip refund_processor.py
aws lambda create-function \
  --function-name refund-processor \
  --runtime python3.13 \
  --role <your-lambda-role-arn> \
  --handler refund_processor.lambda_handler \
  --zip-file fileb://refund_processor.zip
```

### 2.6 Create API Gateway

**In AWS Console:**
1. Go to **API Gateway**
2. Create REST API
3. Add resources and methods pointing to Lambda functions
4. Deploy and copy the invoke URL

## Step 3: Agent Configuration

### 3.1 Update main.py

Fill in the placeholders:
```python
GATEWAY_URL = "<your-gateway-url>/mcp"
KB_ID = "<your-kb-id>"
REGION = "us-east-1"
MEMORY_ID = "<your-memory-id>"
```

**Important:** These values should be kept in a local `.env` file (see .env.example) or environment variables in production. Never commit them to version control.

### 3.2 Configure AgentCore

```bash
uv run agentcore configure
```

Follow prompts to link:
- Knowledge Base ID
- Memory ID
- Lambda functions via Gateway

## Step 4: Deployment

### 4.1 Deploy Agent

```bash
uv run agentcore deploy
```

This packages and deploys your agent to Amazon Bedrock AgentCore.

### 4.2 Setup Permissions

After deployment, configure IAM permissions:
```bash
uv run setup_permissions.py
```

This script:
- Reads configuration from main.py
- Creates an IAM policy for the agent role
- Grants access to Knowledge Base, Memory, and Lambda functions

## Step 5: Testing

### 5.1 Local Testing
```bash
uv run main.py '{"prompt": "What products do you have?", "customer_id": "CUST-001", "session_id": "test-1"}'
```

### 5.2 Deployed Testing
```bash
uv run agentcore invoke '{"prompt": "What products do you have?", "customer_id": "CUST-001", "session_id": "test-1"}'
```

### 5.3 Test Scenarios

**Test 1: Knowledge Base RAG**
```
Prompt: "Tell me about your return policy"
Expected: Agent retrieves from KB and explains policy
```

**Test 2: Loyalty Discount**
```
Prompt: "I have 2000 points and I'm a Gold member. What's my discount on a $100 order?"
Expected: Agent calculates discount and shows breakdown
```

**Test 3: Cross-Session Memory**
```
Session 1: "I prefer email communication"
Session 2: (same customer_id) "How would you contact me?"
Expected: Agent remembers preference from session 1
```

**Test 4: External Tools**
```
Prompt: "What's the status of my order #12345?"
Expected: Agent calls Lambda, returns order status
```

**Test 5: Web Browsing**
```
Prompt: "Check our website for current shipping rates"
Expected: Agent opens website, extracts shipping info
```

## Troubleshooting

### Common Issues

**"KB_ID not configured"**
- Verify KB_ID is set in main.py or environment
- Check Knowledge Base exists in Bedrock console

**"Gateway connection failed"**
- Verify GATEWAY_URL is correct
- Check Gateway is deployed and running
- Verify authorizer settings (should be NONE for development)

**"Memory service error"**
- Confirm Memory ID format: `Name-10chars`
- Check Memory resource exists in console
- Verify strategies are properly configured

**"Lambda invocation failed"**
- Check Lambda functions are deployed
- Verify API Gateway is pointing to Lambda
- Check Lambda execution role has proper permissions

**"Model not available"**
- Ensure Amazon Nova 2 Lite is enabled in Model access
- Use correct model ID: `global.amazon.nova-2-lite-v1:0`

## Production Considerations

### Cost Optimization
- Monitor token usage via Bedrock console
- Implement conversation summarization for long sessions
- Use appropriate model sizing
- Set up CloudWatch alarms for cost thresholds

### Scaling
- Agent handles concurrent requests via AgentCore
- Memory service scales automatically
- Knowledge Base supports large documents
- Lambda functions auto-scale with concurrent executions

### Security
- Never commit AWS credentials
- Use IAM roles instead of access keys
- Enable CloudTrail for audit logging
- Encrypt data in transit and at rest
- Review and minimize IAM permissions

### Monitoring
- CloudWatch logs for agent invocations
- AgentCore monitoring dashboard
- Lambda performance metrics
- Knowledge Base search quality

---

**Next Steps:**
- Review [Architecture](./ARCHITECTURE.md) for system design
- Check [API Documentation](./API.md) for integration details
- See [Security Guide](./SECURITY.md) for best practices
