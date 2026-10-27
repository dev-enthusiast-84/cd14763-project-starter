# API Documentation

## Agent Invocation

### Main Entrypoint

**Function:** `invoke(payload, context=None)`

```python
async def invoke(payload: dict, context=None) -> str:
    """
    Main handler called by AgentCore for every incoming request.
    
    Args:
        payload: Dictionary with keys:
            - prompt (str, required): Customer's message
            - customer_id (str, optional): Unique customer identifier
            - session_id (str, optional): Session ID (auto-generated if absent)
        context: AgentCore context object (unused in current implementation)
    
    Returns:
        str: Agent's response to the customer
    """
```

### Request Format

```json
{
  "prompt": "What's your return policy?",
  "customer_id": "CUST-12345",
  "session_id": "session-abc123"
}
```

### Response Format

```json
{
  "response": "We accept returns within 30 days of purchase..."
}
```

## Tools API

### 1. search_knowledge_base()

Retrieves information from the product knowledge base.

**Signature:**
```python
@tool
def search_knowledge_base(query: str) -> str:
    """Search the Amazon product catalog and support knowledge base."""
```

**Parameters:**
- `query` (str): The search query (product name, policy topic, warranty question)

**Returns:**
- (str): Formatted retrieved chunks joined with `\n---\n`
- Empty result: `"No relevant information found in the knowledge base."`

**Example:**
```python
# Input
result = search_knowledge_base("return policy for electronics")

# Output
"30-day return policy for all electronics purchases with original receipt.\n---\n
Returns must be initiated through the customer portal.\n---\n
Refund processing takes 5-7 business days."
```

### 2. calculate_loyalty_discount()

Calculates loyalty rewards and discount breakdown.

**Signature:**
```python
@tool
def calculate_loyalty_discount(
    loyalty_points: int,
    tier: str,
    order_total: float,
    product_category: str = "standard"
) -> str:
```

**Parameters:**
- `loyalty_points` (int): Customer's current loyalty points
- `tier` (str): Tier level - "Silver", "Gold", or "Platinum"
- `order_total` (float): Order subtotal in USD
- `product_category` (str): One of "standard", "device", "fresh" (default: "standard")

**Returns:**
- (str): JSON string with discount breakdown

**Output Schema:**
```json
{
  "original_total": 100.00,
  "points_redeemed": 1000,
  "points_discount": 10.00,
  "tier_discount_rate": 0.10,
  "tier_discount": 9.00,
  "final_total": 81.00,
  "total_savings": 19.00,
  "points_earned": 100,
  "remaining_points": 2900
}
```

**Business Rules:**
- Points: 500 points = $5.00 redemption
- Max redemption: 50% of order total
- Tier discounts:
  - Silver: 0%
  - Gold: 10%
  - Platinum: 15%
- Earn rates:
  - standard: 1 point per $1
  - device: 2 points per $1
  - fresh: 5 points per $1

**Example:**
```python
result = calculate_loyalty_discount(
    loyalty_points=2000,
    tier="Gold",
    order_total=100.0,
    product_category="standard"
)
# Returns: JSON with calculated discount
```

### 3. Memory Hook Tools

#### retrieve_customer_context()

Automatically called on each message. Retrieves and prepends customer context.

**Trigger:** MessageAddedEvent (before agent processes message)

**Behavior:**
1. Queries memory for all strategy types
2. Tags memories by strategy type
3. Prepends context block to user message
4. Format: `[STRATEGY_TYPE] memory_content`

**Example:**
```
Customer Context:
[SEMANTIC] Prefers email communication
[SEMANTIC] Ordered product X last month
[USER_PREFERENCE] Silver tier member

<original customer message>
```

#### save_support_interaction()

Automatically called after agent responds.

**Trigger:** AfterInvocationEvent (after agent generates response)

**Behavior:**
1. Extracts last user query
2. Extracts last assistant response
3. Saves both to memory with interaction timestamp
4. Persists across sessions for the same customer_id

**Data Saved:**
```
{
  "memory_id": "CustomerSupportMemory-...",
  "actor_id": "CUST-12345",
  "session_id": "session-abc123",
  "messages": [
    ("What's the return policy?", "USER"),
    ("We accept returns within 30 days...", "ASSISTANT")
  ]
}
```

### 4. External Tools (via MCP Gateway)

#### order_tracker (Lambda)

Returns current order status.

**Input:**
```json
{
  "order_id": "ORD-12345"
}
```

**Output:**
```json
{
  "order_id": "ORD-12345",
  "status": "In Transit",
  "tracking_number": "TRK-999",
  "estimated_delivery": "2024-10-30"
}
```

#### refund_processor (Lambda)

Initiates or checks refund status.

**Input:**
```json
{
  "order_id": "ORD-12345",
  "action": "initiate|status"
}
```

**Output:**
```json
{
  "order_id": "ORD-12345",
  "refund_status": "Approved|Pending|Completed",
  "amount": 99.99,
  "estimated_completion": "2024-11-05"
}
```

### 5. Browser Tool

Agent can access live web information.

**Capabilities:**
- Navigate to URLs
- Extract page content
- Follow links
- Fill forms

**Example Use Cases:**
- Check current shipping rates
- Verify policy changes on website
- Get live product availability

## Configuration

### Environment Variables

```bash
GATEWAY_URL=https://your-gateway.../mcp
KB_ID=XXXXXXXXXX
REGION=us-east-1
MEMORY_ID=YourMemory-XXXXXXXXXX
```

### BedrockModel

```python
model = BedrockModel(model_id="global.amazon.nova-2-lite-v1:0")
```

### Clients

```python
memory_client = MemoryClient(region_name="us-east-1")
_bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name="us-east-1")
```

## Error Handling

### Knowledge Base Errors
```python
if not KB_ID:
    return "Knowledge base not configured."

if not results:
    return "No relevant information found in the knowledge base."
```

### Code Interpreter Errors
```python
try:
    # Execute code via code_session
except Exception as e:
    # Fallback: tier discount only
    return json.dumps({
        "tier_discount": ...,
        "note": f"Code Interpreter unavailable ({e})"
    })
```

### Memory Errors
Gracefully handled - conversations continue without cross-session context if memory service is unavailable.

## Output Validation

All tool outputs are validated using Pydantic models:

```python
class DiscountResult(BaseModel):
    original_total: float
    points_redeemed: int
    tier_discount_rate: float
    final_total: float
    total_savings: float
    points_earned: int
    remaining_points: int
```

Validation ensures:
- Type correctness
- Required fields present
- Numeric ranges valid
- Graceful handling of invalid data

---

**Related:**
- [Architecture](./ARCHITECTURE.md) - System design
- [Setup](./SETUP.md) - Configuration instructions
- [Security](./SECURITY.md) - Data protection
