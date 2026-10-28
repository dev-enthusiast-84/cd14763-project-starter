---
layout: default
title: System Architecture
---

# System Architecture

## Overview

The Customer Support AI Agent is built on a microservices architecture leveraging AWS managed services:

```
┌─────────────────────────────────────────────────────────┐
│                 User Request (AgentCore)                 │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────▼────────────┐
        │   BedrockAgentCoreApp   │
        │   (Agent Runtime)       │
        └────────────┬────────────┘
                     │
         ┌───────────┼───────────────────┐
         │           │                   │
    ┌────▼──┐   ┌────▼──┐   ┌──────────▼──────────┐
    │  RAG  │   │Memory │   │  External Tools     │
    │  KB   │   │Service│   │  (Gateway + MCP)    │
    └───────┘   └───────┘   │                     │
         │           │      │  ┌─────────────┐    │
         │      ┌────▼──┐   ├──┤ Order Track │    │
         │      │ DDB   │   │  │ Refund Proc │    │
         │      └───────┘   │  └─────────────┘    │
         │           │      └──────────┬──────────┘
    ┌────▼──────┬────▼───────────────▼────┐
    │  S3 KB    │   Memory DB              │  Lambda
    │  Source   │   (Semantic, Pref)       │  Functions
    └───────────┴─────────────────────────┘
```

## Components

### 1. Agent Runtime (BedrockAgentCoreApp)
- **Role:** Central orchestrator for all agent logic
- **Language:** Python 3.13+
- **Framework:** Strands Agents with Bedrock integration
- **Deployment:** AWS Bedrock AgentCore (managed runtime)
- **Scalability:** Auto-scales with concurrent requests

**Key Methods:**
- `invoke()` - Main entrypoint for customer queries
- Tool registration and execution
- Hook integration for memory and validation

### 2. Knowledge Base (RAG)
- **Service:** Amazon Bedrock Managed Knowledge Base
- **Data Source:** Product catalog in S3
- **Embedding Model:** Bedrock embedding model
- **Search Type:** Semantic vector search
- **Tool:** `search_knowledge_base()`

**Capabilities:**
- Retrieves product info, policies, FAQs
- Returns top-k relevant chunks with metadata
- Automatic chunking and embedding

### 3. Memory Service (Cross-Session)
- **Service:** Amazon Bedrock AgentCore Memory
- **Strategies:** 
  - SEMANTIC: Vector embeddings of facts
  - USER_PREFERENCE: User preferences and rules
- **Storage:** Managed database with TTL
- **Namespaces:** Organized by actor_id and strategy

**Implementation:**
- `MemoryHook` class with two functions:
  - `retrieve_customer_context()` - Fetch relevant memories
  - `save_support_interaction()` - Persist interactions

### 4. Code Interpreter (Sandboxed Execution)
- **Service:** AgentCore Code Interpreter
- **Isolation:** Complete sandbox isolation
- **Language:** Python
- **Tool:** `calculate_loyalty_discount()`

**Features:**
- No system access
- No state persistence between executions
- Timeout protection
- Error isolation

### 5. External Tools (MCP Gateway)
- **Protocol:** Model Context Protocol (MCP)
- **Gateway:** Bedrock AgentCore Gateway (HTTP)
- **Authorization:** None (development), API Key (production)

**Tools:**
- `order_tracker` - Lambda function for order status
- `refund_processor` - Lambda function for refund processing

### 6. Browser Tool
- **Service:** AgentCore Browser
- **Capabilities:** Navigate websites, extract content
- **Use Cases:** Real-time shipping info, policy updates

## Data Flow

### Query Processing Flow
```
1. User sends prompt
   ↓
2. Agent receives via invoke()
   ↓
3. Memory Hook retrieves context (customer history)
   ↓
4. Agent analyzes query and selects tools
   ↓
5. Tool Execution (parallel where possible):
   - Knowledge Base search (if product question)
   - Memory lookup (if personalization needed)
   - Code calculation (if discount needed)
   - Lambda call (if order status needed)
   - Browser (if real-time info needed)
   ↓
6. Responses collected and validated (Pydantic)
   ↓
7. Agent generates response with context
   ↓
8. Memory Hook saves interaction
   ↓
9. Response returned to user
```

### Memory Lifecycle
```
Session 1:
├─ User: "I prefer email"
├─ Agent saves to SEMANTIC: "customer_email_preference"
└─ Agent saves to USER_PREFERENCE: "email=true"

Session 2 (same customer):
├─ Memory Hook retrieves prefences
├─ Agent knows customer prefers email
└─ Personalizes response accordingly
```

## Technologies & Frameworks

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Agent** | Strands Agents | Agent framework |
| **Model** | Amazon Nova 2 Lite | LLM inference |
| **Runtime** | Bedrock AgentCore | Deployment & orchestration |
| **Knowledge** | Bedrock KB | RAG engine |
| **Memory** | Bedrock Memory | Cross-session storage |
| **Compute** | Code Interpreter | Secure code execution |
| **Integration** | MCP Gateway | External tool integration |
| **Browser** | AgentCore Browser | Web access |
| **Validation** | Pydantic | Output validation |
| **Language** | Python 3.13 | Implementation |

## Scalability Considerations

### Horizontal Scaling
- AgentCore handles concurrent invocations
- Memory service scales automatically
- Knowledge Base scales to large document sets
- Lambda functions auto-scale with queue

### Vertical Optimization
- Conversation summarization for long sessions
- Token budget management
- Efficient embedding reuse
- Caching for repeated queries

### Cost Optimization
- Use appropriate model size (Nova 2 Lite)
- Monitor token consumption
- Implement request batching
- S3 lifecycle policies for old data

## Reliability & Fault Tolerance

### Error Handling
- Code Interpreter: Try-except with fallback
- Gateway tools: Retry logic with exponential backoff
- Memory: Graceful degradation if unavailable
- Knowledge Base: Default response if empty

### Monitoring
- CloudWatch logs for all invocations
- Error tracking and alerting
- Performance metrics dashboard
- Cost tracking and alerts

## Security Architecture

### Credential Protection
- No hardcoded AWS IDs in code
- Environment-based configuration
- .gitignore protection
- IAM role assumption (not keys)

### Data Protection
- Encryption in transit (TLS)
- Encrypted at rest (S3, DDB)
- VPC endpoints for private access
- Customer data isolation by actor_id

### Access Control
- IAM roles follow least privilege
- Resource-level permissions
- API Gateway authentication
- Lambda execution role restrictions

### Audit & Compliance
- CloudTrail logging of all API calls
- Agent interaction logs
- Memory audit trail
- Compliance with data retention policies

---

**Related Documents:**
- [Setup Guide](./SETUP.md) - Deployment instructions
- [API Documentation](./API.md) - Tool specifications
- [Security Guide](./SECURITY.md) - Security best practices
