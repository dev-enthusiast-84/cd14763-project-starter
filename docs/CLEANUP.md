---
layout: default
title: Cleanup Guide
---

# Cleanup Guide

**IMPORTANT:** Only run cleanup after you have:
1. ✅ Completed and submitted all project deliverables
2. ✅ Captured test screenshots for submission
3. ✅ Documented test results
4. ✅ Verified your reflection essay is complete

---

## Overview

This guide walks you through safely removing all AWS resources created for this project. Follow the steps in order to avoid orphaned resources and unexpected charges.

**Estimated cleanup time:** 10-15 minutes

---

## Step 1: Destroy AgentCore Deployment

### Command
```bash
cd starter
uv run agentcore destroy
```

### What This Does
- Removes the deployed agent from Bedrock AgentCore
- Deletes the runtime execution environment
- Cleans up associated Lambda layers
- Removes the deployment package from S3

### Verification
```bash
# Check that agent no longer exists
aws bedrock-agentcore list-agents --region us-east-1
# Expected: agent no longer listed
```

---

## Step 2: Delete Bedrock Resources

### 2.1 Delete Gateway

**In AWS Console:**
1. Navigate to **Amazon Bedrock** → **AgentCore** → **Gateways**
2. Find your gateway (e.g., `customer-support-gateway`)
3. Select it
4. Click **Delete**
5. Confirm deletion

**Via CLI:**
```bash
aws bedrock-agentcore delete-gateway \
  --gateway-id <your-gateway-id> \
  --region us-east-1
```

**Verification:**
- Gateway status changes to DELETING then disappears
- No charges accumulate for gateway

### 2.2 Delete Memory Resource

**In AWS Console:**
1. Navigate to **Amazon Bedrock** → **AgentCore** → **Memory**
2. Find your memory (e.g., `CustomerSupportMemory`)
3. Select it
4. Click **Delete**
5. Confirm deletion

**Via CLI:**
```bash
aws bedrock-agentcore delete-memory \
  --memory-id <your-memory-id> \
  --region us-east-1
```

**Verification:**
- Memory resource deleted
- No more storage charges

### 2.3 Delete Knowledge Base

**In AWS Console:**
1. Navigate to **Amazon Bedrock** → **Knowledge bases**
2. Find your knowledge base (e.g., `CustomerSupportKB`)
3. Click on it
4. Click **Delete** button
5. Confirm deletion

**Via CLI:**
```bash
aws bedrock-agent delete-knowledge-base \
  --knowledge-base-id <your-kb-id> \
  --region us-east-1
```

**Verification:**
- Knowledge Base deleted
- Status shows deletion in progress

---

## Step 3: Delete Vector Database & S3

### CRITICAL: OpenSearch Serverless Can Be Expensive
Deleting the Knowledge Base does NOT automatically delete the OpenSearch Serverless collection. This can incur significant charges if left running.

### 3.1 Delete OpenSearch Collection

**In AWS Console:**
1. Navigate to **OpenSearch Service** → **Serverless** → **Collections**
2. Look for a collection named something like `<kb-id>-collection`
3. Select it
4. Click **Delete**
5. Confirm deletion
6. **Wait for deletion to complete** (may take 2-3 minutes)

**Via CLI:**
```bash
# List collections
aws opensearchserverless list-collections --region us-east-1

# Delete collection
aws opensearchserverless delete-collection \
  --id <collection-id> \
  --region us-east-1
```

**Verification:**
- Collection disappears from OpenSearch console
- No more hourly charges from OpenSearch

### 3.2 Delete S3 Bucket

**In AWS Console:**
1. Navigate to **S3** → **Buckets**
2. Find the bucket you created (e.g., `customer-support-kb-bucket`)
3. **First: Empty the bucket**
   - Select the bucket
   - Click **Empty**
   - Type `permanently delete`
   - Click **Empty**
4. **Then: Delete the bucket**
   - Select the bucket
   - Click **Delete**
   - Type the bucket name
   - Click **Delete**

**Via CLI:**
```bash
# List buckets
aws s3 ls

# Empty bucket
aws s3 rm s3://your-bucket-name --recursive

# Delete bucket
aws s3 rb s3://your-bucket-name
```

**Verification:**
- Bucket disappears from S3 console
- No storage charges

---

## Step 4: Delete API Gateway and Lambda

### 4.1 Delete REST API Gateway

**In AWS Console:**
1. Navigate to **API Gateway**
2. Find your API (e.g., `customer-support-api`)
3. Click on it
4. Go to **Settings** or select **Delete API** option
5. Confirm deletion

**Via CLI:**
```bash
# List APIs
aws apigateway get-rest-apis --region us-east-1

# Delete API
aws apigateway delete-rest-api \
  --rest-api-id <api-id> \
  --region us-east-1
```

**Verification:**
- API disappears from console
- Endpoint URL no longer works

### 4.2 Delete Lambda Functions

**In AWS Console:**
1. Navigate to **AWS Lambda** → **Functions**
2. Find both functions:
   - `order-tracker`
   - `refund-processor`
3. For each function:
   - Click on it
   - Click **Actions** → **Delete**
   - Confirm deletion
   - Click **Delete function**

**Via CLI:**
```bash
# Delete order-tracker
aws lambda delete-function \
  --function-name order-tracker \
  --region us-east-1

# Delete refund-processor
aws lambda delete-function \
  --function-name refund-processor \
  --region us-east-1
```

**Verification:**
- Both functions disappear from Lambda console
- No compute charges

---

## Step 5: Clean Up IAM Roles (Optional)

If you want a completely clean slate, delete the execution roles:

### 5.1 Find Roles

**In AWS Console:**
1. Navigate to **IAM** → **Roles**
2. Look for roles created by this project:
   - `bedrock-kb-execution-role`
   - `bedrock-agent-execution-role`
   - `lambda-basic-execution-role`
   - OpenSearch service role

### 5.2 Delete Roles

For each role:
1. Click on it
2. Click **Delete role**
3. Confirm deletion

**Via CLI:**
```bash
# List roles (filter for your project)
aws iam list-roles --region us-east-1 | grep bedrock

# Delete role (must detach policies first)
aws iam delete-role --role-name <role-name>
```

**Important:** Only delete roles you created for this project. Be careful not to delete other application roles.

---

## Cleanup Checklist

- [ ] **AgentCore Deployment** - Destroyed with `agentcore destroy`
- [ ] **Gateway** - Deleted from Bedrock console
- [ ] **Memory Resource** - Deleted from Bedrock console
- [ ] **Knowledge Base** - Deleted from Bedrock console
- [ ] **OpenSearch Collection** - Deleted (IMPORTANT!)
- [ ] **S3 Bucket** - Emptied and deleted
- [ ] **API Gateway** - Deleted
- [ ] **Lambda Functions** - Both deleted
- [ ] **IAM Roles** - Deleted (optional)

---

## Verification Steps

### Check Nothing Is Left

```bash
# List all Bedrock resources
aws bedrock-agentcore list-agents --region us-east-1
aws bedrock-agentcore list-gateways --region us-east-1
aws bedrock-agentcore list-memories --region us-east-1
aws bedrock-agent list-knowledge-bases --region us-east-1

# Check Lambda functions
aws lambda list-functions --region us-east-1 | grep -E "order-tracker|refund-processor"

# Check API Gateways
aws apigateway get-rest-apis --region us-east-1

# Check S3 buckets
aws s3 ls | grep customer-support

# All should return empty or no results
```

### Check Billing

```bash
# Check for remaining charges
aws ce get-cost-and-usage \
  --time-period Start=2026-10-01,End=2026-10-28 \
  --granularity DAILY \
  --metrics "BlendedCost" \
  --region us-east-1
```

---

## Cost Summary

### What You Shouldn't Be Charged For
✓ AgentCore agent runtime  
✓ Gateway endpoint  
✓ Memory storage  
✓ Knowledge Base  
✓ Lambda function executions  
✓ OpenSearch Serverless  
✓ S3 storage  
✓ API Gateway usage  

### What You Might See Charges For
- **Knowledge Base retrieval API calls** - If you ran many tests
- **Lambda invocations** - From test runs
- **OpenSearch** - If you didn't delete the collection (THIS IS EXPENSIVE!)
- **API Gateway requests** - From agent invocations

**Typical project cost:** $5-15 USD (depending on test intensity)

---

## Troubleshooting Cleanup

### "Cannot delete because resource is in use"

**Solution:** Wait a few minutes then retry. Some services take time to fully clean up.

### "OpenSearch Collection still exists"

**Solution:**
1. Verify you deleted the Knowledge Base first
2. Wait 5 minutes for Knowledge Base deletion to complete
3. Then delete the OpenSearch collection

### "S3 bucket not empty"

**Solution:**
1. Go to S3 console
2. Select bucket
3. Click "Empty" (not Delete)
4. Type "permanently delete"
5. Wait for emptying to complete
6. Then delete the bucket

### Unexpected Charges

If you see charges after cleanup:
1. Check CloudBill to see what's being charged
2. Most likely: OpenSearch collection still running
3. Delete the collection immediately
4. Contact AWS Support about the charge

---

## Final Verification

After cleanup, verify your AWS account is clean:

```bash
# Should return no resources
aws bedrock-agentcore list-agents --region us-east-1
aws bedrock-agentcore list-gateways --region us-east-1
aws lambda list-functions --region us-east-1 | grep "order-tracker\|refund-processor"
aws apigateway get-rest-apis --region us-east-1
aws opensearchserverless list-collections --region us-east-1

# S3 buckets should not include yours
aws s3 ls | grep customer-support
```

---

## Important Notes

### Before Cleanup
- ✅ Save test screenshots
- ✅ Document test results
- ✅ Complete reflection essay
- ✅ Verify submission is ready

### Cost Prevention
- ⚠️ **DELETE OPENSEARCH COLLECTION** - This is the most expensive resource
- ⚠️ Empty S3 before deleting (important!)
- ⚠️ Delete all Lambda functions

### Project Preservation
- **GitHub repository** - Keep, this is your portfolio
- **Local code** - Keep, this is your work
- **Documentation** - Keep, publish on GitHub Pages
- **AWS resources** - Delete to avoid ongoing charges

---

## After Cleanup

Once cleanup is complete:
1. Your AWS account is clean (no project resources)
2. No ongoing charges accumulating
3. GitHub repository preserved with full documentation
4. You have a portfolio project to showcase

**Congratulations on completing the AWS AI Engineering Nanodegree Capstone Project!** 🎉

---

See [Testing Guide](./TESTING.md) if you need to re-run tests before cleanup.
