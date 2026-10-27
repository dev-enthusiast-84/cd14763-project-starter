# Testing Guide

## Pre-Deployment Verification

Before running test scenarios, verify your setup is complete:

```bash
# Check 1: AWS credentials configured
aws sts get-caller-identity
# Expected: Your AWS account ID and IAM user/role

# Check 2: Gateway tools accessible
npx @modelcontextprotocol/inspector
# Expected: order_tracker and refund_processor tools listed

# Check 3: Knowledge Base working
# In Bedrock console → Knowledge Bases → Test
# Query: "What is the return policy for electronics?"
# Expected: 15-day return window mentioned

# Check 4: Dependencies installed
uv sync
# Expected: All packages resolve without errors
```

---

## Deployment

### Configure AgentCore

```bash
cd starter
uv run agentcore configure \
  --entrypoint main.py \
  --name customer-support-agent \
  --deployment-type direct_code_deploy \
  --runtime PYTHON_3_13 \
  --disable-memory
```

**Expected Output:**
- `.bedrock_agentcore.yaml` created
- Runtime execution role created
- Configuration accepted

### Deploy Agent

```bash
uv run agentcore deploy
```

**Expected Output:**
- Deployment package created
- Agent deployed to AgentCore
- Runtime ID displayed
- Status: Ready

### Setup Permissions

```bash
uv run setup_permissions.py
```

**Expected Output:**
- Policy created for agent role
- Knowledge Base access granted
- Memory access granted
- Browser access granted

---

## Test Scenarios

### Test 1: Order Tracking

**Command:**
```bash
agentcore invoke '{"prompt": "Can you track order ORD-001?", "customer_id": "CUST-123", "session_id": "t1"}'
```

**Expected Response:**
- ✓ Shipping status information
- ✓ Tracking number: TRK987654321
- ✓ Carrier: UPS
- ✓ Estimated delivery date
- ✓ Natural language explanation

**What's Tested:**
- MCPClient connection to Gateway
- order_tracker Lambda function integration
- Tool response parsing and formatting
- Agent tool selection and invocation

**Success Criteria:**
- Agent successfully retrieves order status
- Response includes all tracking details
- No errors in execution
- Response is natural and helpful

---

### Test 2: Refund Processing

**Command:**
```bash
agentcore invoke '{"prompt": "I want to return my Kindle Paperwhite (ORD-002). Please initiate a refund.", "customer_id": "CUST-123", "session_id": "t2"}'
```

**Expected Response:**
- ✓ Refund ID generated
- ✓ Status: APPROVED
- ✓ Processing timeline: "3-5 business days"
- ✓ Next steps explained

**What's Tested:**
- refund_processor Lambda integration
- Complex request understanding
- Tool schema validation
- Response formatting with structured data

**Success Criteria:**
- Refund initiated successfully
- All required fields present in response
- Clear timeline communicated
- No errors or timeouts

---

### Test 3: Knowledge Base (RAG)

**Command:**
```bash
agentcore invoke '{"prompt": "What are the benefits of the Platinum loyalty tier?", "customer_id": "CUST-123", "session_id": "t3"}'
```

**Expected Response:**
- ✓ Free same-day shipping mentioned
- ✓ 15% discount on all purchases
- ✓ Priority customer support
- ✓ Other Platinum-tier benefits

**What's Tested:**
- Knowledge Base retrieval
- Semantic search functionality
- RAG context integration
- Response grounding in KB data

**Success Criteria:**
- Information accurately retrieved from KB
- Benefits correctly listed
- Context is specific and relevant
- Response demonstrates RAG working

---

### Test 4: Long-Term Memory (Two Sessions)

#### Part A: Store Memory

**Command (Session A):**
```bash
agentcore invoke '{"prompt": "Hi, I am Jane. I prefer concise responses.", "customer_id": "CUST-123", "session_id": "s-A"}'
```

**Expected Response:**
- ✓ Agent acknowledges name: Jane
- ✓ Acknowledges preference for conciseness
- ✓ Response is brief (demonstrates understanding)

**Wait:** 30+ seconds for memory extraction to complete

#### Part B: Verify Recall

**Command (Session B):**
```bash
agentcore invoke '{"prompt": "Do you remember my name and communication preference?", "customer_id": "CUST-123", "session_id": "s-B"}'
```

**Expected Response:**
- ✓ Recalls name: "Jane"
- ✓ Recalls preference: "concise responses"
- ✓ Response is concise (shows understanding of preference)
- ✓ No prompt given - purely from memory

**What's Tested:**
- Memory Hook retrieval functionality
- Cross-session context persistence
- Memory strategy namespace usage
- Semantic memory extraction

**Success Criteria:**
- Agent successfully recalls information from Session A
- No explicit reminder needed
- Response demonstrates personalization
- Memory Hook working correctly

---

### Test 5: Loyalty Discount Calculation

**Command:**
```bash
agentcore invoke '{"prompt": "I am a Gold member with 4250 points. Calculate my discount on a $150 standard order.", "customer_id": "CUST-123", "session_id": "t5"}'
```

**Expected Response:**
- ✓ Points redeemed: 4000 points (800 value)
- ✓ Tier discount rate: 10% (Gold)
- ✓ Tier discount: $14.20
- ✓ Final total: $135.80
- ✓ Remaining points: 250
- ✓ Points earned: 150 (standard rate)

**What's Tested:**
- Code Interpreter sandbox execution
- Business rule calculation accuracy
- Pydantic validation of output
- Discount calculation algorithm
- Points redemption logic

**Calculation Breakdown:**
```
Original: $150.00
Points: 4250 available
  - Redeem 4000 points = $40.00 discount (2 x 500 point blocks)
  - After points: $110.00
Tier: Gold (10% discount)
  - Tier discount: $110.00 × 0.10 = $11.00
  - After tier: $99.00
Final: $99.00
Savings: $51.00
Points earned: 150 (1pt per $1 for standard)
Remaining: 250 + 150 = 400
```

**Success Criteria:**
- All calculations correct
- Response includes breakdown
- Structured output is valid
- Pydantic validation passes

---

### Test 6: Browser Tool

**Command:**
```bash
agentcore invoke '{"prompt": "Go to https://www.udacity.com and tell me the page title.", "customer_id": "CUST-123", "session_id": "t6"}'
```

**Expected Response:**
- ✓ Page title retrieved: "Udacity - Learn In-Demand Skills"
- ✓ Natural description of page content
- ✓ Links to relevant sections mentioned

**What's Tested:**
- AgentCoreBrowser initialization
- Web page navigation capability
- Content extraction from live pages
- Integration with agent reasoning

**Success Criteria:**
- Browser tool successfully navigates
- Page content accurately retrieved
- Title and key information extracted
- Response is natural and helpful

---

## Test Result Documentation

### Capture Output Format

For each test, capture:

```markdown
## Test X: [Test Name]

**Command:**
```bash
agentcore invoke '...'
```

**Response:**
```
[Full agent response here]
```

**Verification:**
- [ ] Expected element 1 present
- [ ] Expected element 2 present
- [ ] No errors in execution
- [ ] Response is natural and helpful

**Status:** ✅ PASSED / ❌ FAILED

**Notes:**
[Any observations or issues]
```

### Create Test Report

Create `test-results.md` with all 6 test outputs:

```bash
# Run all tests and capture output
agentcore invoke '...' > test1.txt
agentcore invoke '...' > test2.txt
# ... etc for all 6 tests

# Compile into test-results.md
cat test1.txt test2.txt > test-results.md
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **"Gateway connection failed"** | Invalid GATEWAY_URL | Verify URL in main.py matches console |
| **"KB_ID not configured"** | KB_ID is empty or invalid | Check main.py has 10-char KB_ID |
| **"Memory not found"** | Invalid MEMORY_ID | Verify Memory ID format and existence |
| **"Lambda timeout"** | Function execution slow | Check Lambda timeout settings |
| **"Tool not found"** | Gateway tools not loaded | Re-run setup_permissions.py |
| **"Pydantic validation error"** | Tool response malformed | Check tool implementation |

### Debug Commands

```bash
# Check agent logs
aws logs tail /aws/bedrock/agents/[agent-id] --follow

# Test knowledge base directly
aws bedrock-agent-runtime retrieve \
  --knowledge-base-id [KB_ID] \
  --retrieval-query '{"text": "test query"}'

# Test memory directly
aws bedrock-agentcore get-memory \
  --memory-id [MEMORY_ID] \
  --actor-id CUST-123

# Test Lambda function
aws lambda invoke \
  --function-name order-tracker \
  --payload '{"order_id": "ORD-001"}' \
  response.json
```

---

## Test Execution Timeline

**Estimated total time:** 15-20 minutes

```
Setup & Deploy:        5-10 minutes
  - agentcore deploy:  3-5 min
  - setup_permissions: 2 min

Test Scenarios:        10 minutes
  - Test 1 (order):    1 min
  - Test 2 (refund):   1 min
  - Test 3 (RAG):      1 min
  - Test 4a (memory):  1 min
  - Test 4b (recall):  1 min (+ 30 sec wait)
  - Test 5 (discount): 1 min
  - Test 6 (browser):  2 min
```

---

## Success Checklist

- [ ] All 6 test scenarios executed
- [ ] All expected outputs received
- [ ] No errors in any test
- [ ] Test results documented
- [ ] Screenshots captured for submission
- [ ] Agent responds naturally and helpfully
- [ ] Tool integrations working correctly
- [ ] Memory persisting across sessions
- [ ] RAG retrieving accurate information
- [ ] Code calculations correct

---

## Next Steps

Once testing is complete:
1. Document test results in `test-results.md`
2. Take screenshots of each test output
3. Verify reflection essay is complete
4. Review PROJECT_STATUS.md for submission checklist
5. Proceed to cleanup if tests are successful

See [Cleanup Guide](./CLEANUP.md) for resource cleanup instructions.
