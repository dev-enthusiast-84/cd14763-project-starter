# Submission #2 - Required Fixes

**Reviewer Feedback:** 5/7 requirements pass. Two focused fixes needed.  
**Timeline:** After fixes, retest and resubmit.

---

## 📋 Summary of Required Changes

| Fix | Issue | Impact | Priority |
|-----|-------|--------|----------|
| **Fix 1** | Points earned wrong | Test 5 fails | CRITICAL |
| **Fix 2** | Fallback not tier-only | Test 5 fails | CRITICAL |
| **Fix 3** | Refund missing order lookup | Test 2 fails | CRITICAL |

---

## 🔧 Fix 1: Loyalty Discount - Points Earned Calculation

### Problem
Current code calculates points earned on `order_total` ($150):
```python
points_earned = int(order_total * earn_rates.get(product_category, 1))
```

**Result (Wrong):** 150 earned, 400 remaining  
**Expected (Correct):** 99 earned, 349 remaining

### Root Cause
Points should be earned on the **amount actually paid** (after discounts), not the original total.

### Solution

**Location:** starter/main.py, in the code string execution (around line 495-510)

**Change:**
```python
# BEFORE (WRONG):
points_earned = int(order_total * earn_rates.get(product_category, 1))

# AFTER (CORRECT):
points_earned = int(final_total * earn_rates.get(product_category, 1))
```

### Why This Matters
- Customer earned 99 points by paying $99 (not $150)
- Remaining points: 4250 - 4000 + 99 = **349** (not 400)
- This aligns with real-world loyalty programs

### Verification
**Test 5 Input:**
- Gold member, 4250 points, $150 standard order

**Expected Output:**
```json
{
  "original_total": 150.00,
  "points_redeemed": 4000,
  "tier_discount_pct": 0.10,
  "final_total": 99.00,
  "total_savings": 51.00,
  "points_earned": 99,
  "remaining_points": 349
}
```

---

## 🔧 Fix 2: Loyalty Discount - Fallback Must Be Tier-Only

### Problem
Current fallback repeats the full calculation (including points):
```python
except Exception as e:
    # Repeats: points redemption, tier discount, etc.
    # This is wrong - should be tier-only
```

**Current Fallback Result (Wrong):**
- Points still redeemed
- Points balance still changes
- Full calculation still attempted

**Expected Fallback (Tier-Only):**
- 0 points redeemed
- Tier discount on original total only
- Points balance unchanged
- Graceful degradation

### Root Cause
The rubric specifies a "tier-only fallback" for when code interpreter is unavailable. This means:
- Skip points calculation entirely
- Apply only the tier discount
- Keep points balance unchanged

### Solution

**Location:** starter/main.py, calculate_loyalty_discount function (around line 526-558)

**Replace entire fallback block with:**
```python
except Exception as e:
    # Tier-only fallback when Code Interpreter is unavailable
    tier_rates = {"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}
    pct = tier_rates.get(tier, 0.0)
    tier_discount = round(order_total * pct, 2)
    final_total = round(order_total - tier_discount, 2)
    
    return json.dumps({
        "original_total": order_total,
        "points_redeemed": 0,
        "points_discount": 0.0,
        "tier_discount_pct": pct,
        "tier_discount": tier_discount,
        "final_total": final_total,
        "total_savings": tier_discount,
        "points_earned": 0,
        "remaining_points": loyalty_points,
        "note": f"Code Interpreter unavailable; tier discount only"
    })
```

### Key Differences
| Aspect | Full Calculation | Tier-Only Fallback |
|--------|------------------|-------------------|
| Points redeemed | Yes | **0** |
| Points discount | $X | **$0** |
| Tier discount | Applied to subtotal | **Applied to original total** |
| Points earned | Calculated | **0** |
| Points balance | Changes | **Unchanged** |

### Why This Matters
When the code interpreter fails, the system can still serve a reduced feature set:
- Always apply loyalty tier discount
- Never touch the points balance (safer)
- Clear note that it's a fallback

---

## 🔧 Fix 3: Gateway Refund Tool - Add Order Lookup

### Problem
Current refund tool directly processes refund without:
1. Looking up the order first
2. Using the order total as the refund amount
3. Returning complete refund details

**Current Result (Incomplete):**
- Refund initiated but details missing
- Amount unclear

**Expected (Complete):**
- Order looked up first
- Order total used as refund amount
- Refund ID, status, amount, timeline shown

### Root Cause
The refund process requires two steps:
1. Lookup: Get order details (including total)
2. Refund: Use order total to create refund

### Solution

**Location:** starter/lambda/refund_processor.py

**Implement two-step process:**
```python
def lambda_handler(event, context):
    # Step 1: Extract order ID from request
    order_id = event["order_id"]
    
    # Step 2: Look up order using order_tracker
    order = order_tracker.get_order(order_id)
    order_total = order["total"]
    
    # Step 3: Initiate refund with order total
    refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
    
    return {
        "refund_id": refund_id,
        "order_id": order_id,
        "amount": order_total,
        "status": "APPROVED",
        "timeline": "3-5 business days"
    }
```

### Test 2 Expected Output
**Input:**
```json
{
  "prompt": "I want to return my Kindle Paperwhite (ORD-002). Please initiate a refund.",
  "customer_id": "CUST-456",
  "session_id": "test-2-v2"
}
```

**Agent Response Should Include:**
- Refund ID (e.g., REF-ABC123XY)
- Status: APPROVED
- Amount: $139.99 (from ORD-002 lookup)
- Timeline: 3-5 business days

---

## ✅ Verification Checklist

### Before Redeployment
- [ ] Fix 1: Points earned uses `final_total`
- [ ] Fix 2: Fallback tier-only with 0 points
- [ ] Fix 3: Refund tool looks up order first
- [ ] All currency values rounded with round(..., 2)
- [ ] tier_discount_pct is decimal (0.10, not 10)

### Redeployment Steps
```bash
cd starter

# Verify changes
grep "final_total \* earn_rates" main.py  # Fix 1
grep "points_redeemed\": 0" main.py        # Fix 2
grep "order_tracker" lambda/refund_processor.py  # Fix 3

# Redeploy
uv run agentcore deploy
uv run setup_permissions.py
```

### Retesting
```bash
# Test 5: Loyalty Discount (Fix 1 & 2)
agentcore invoke '{"prompt": "I am a Gold member with 4250 points. Calculate my discount on a $150 standard order.", "customer_id": "CUST-TEST-5", "session_id": "test-5-v2"}'
# Expected: $99 final, 99 earned, 349 remaining

# Test 2: Refund (Fix 3)
agentcore invoke '{"prompt": "I want to return my Kindle Paperwhite (ORD-002). Please initiate a refund.", "customer_id": "CUST-TEST-2", "session_id": "test-2-v2"}'
# Expected: Refund ID, APPROVED, $139.99, 3-5 days
```

### Success Criteria
- [ ] Test 2 returns refund ID + APPROVED + amount + timeline
- [ ] Test 5 returns $99 final total + 99 earned + 349 remaining
- [ ] No errors in agentcore logs
- [ ] All other tests (1,3,4,6) still pass

---

## 🎯 Additional Improvements (Recommended by Reviewer)

### 1. Environment Variables for Configuration
**Current (Insecure):**
```python
GATEWAY_URL = "<gateway_url>"
KB_ID = "<kbid>"
```

**Recommended:**
```python
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
KB_ID = os.environ.get("KB_ID", "")
REGION = os.environ.get("REGION", "us-east-1")
MEMORY_ID = os.environ.get("MEMORY_ID", "")
```

**Set during deployment:**
```bash
export GATEWAY_URL="https://your-gateway.../mcp"
export KB_ID="B5XQCTQXRS"
export REGION="us-east-1"
export MEMORY_ID="CustomerSupportMemory-..."

uv run agentcore deploy
```

### 2. Return All Text Blocks
**Current (Unsafe):**
```python
if isinstance(content, list):
    return content[0].get("text", "")
```

**Better:**
```python
if isinstance(content, list):
    text_blocks = [block.get("text", "") for block in content if block.get("type") == "text"]
    return "\n".join(text_blocks)
return content
```

### 3. Consistent Currency Rounding
**Current (Inconsistent):**
```python
final_total = order_total - tier_discount
```

**Better:**
```python
tier_discount = round(order_total * pct, 2)
final_total = round(order_total - tier_discount, 2)
```

### 4. Memory Improvement
**Current:**
- Saves context-augmented message to memory

**Better:**
- Save original user query (not the prepended context)
- Prevents memory bloat and noise

---

## 📝 Submission #2 Checklist

### Code Changes
- [ ] Fix 1: Points earned on final_total
- [ ] Fix 2: Tier-only fallback implementation
- [ ] Fix 3: Refund order lookup
- [ ] (Optional) Load config from environment
- [ ] (Optional) Return all text blocks
- [ ] (Optional) Consistent rounding
- [ ] (Optional) Save original query to memory

### Testing
- [ ] Test 2 (Refund) - passes with order lookup
- [ ] Test 5 (Loyalty) - passes with correct amounts
- [ ] All other tests - still passing

### Resubmission
- [ ] Code changes deployed
- [ ] New test screenshots captured
- [ ] Updated test results documented
- [ ] Resubmit with same GitHub link

---

## 📚 Resources Recommended by Reviewer

- [AgentCore Gateway Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-integration-gateway.html) - For Lambda targets and input schemas
- [AgentCore Code Interpreter Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-code-interpreter.html) - For executeCode patterns
- [AWS Samples: AgentCore](https://github.com/aws-samples/amazon-bedrock-agentcore-samples) - End-to-end examples

---

## ✨ What the Reviewer Praised

Keep these strengths in Submission #2:
- ✅ Runtime deployment with proper async pattern
- ✅ RAG knowledge base retrieval accuracy
- ✅ Cross-session memory persistence
- ✅ Browser tool live web access
- ✅ Pydantic validation
- ✅ Reflection essay quality
- ✅ Debugging skills

---

## 🚀 Next Steps

1. **Make Fixes** (Estimated time: 30-45 minutes)
   - Apply Fix 1, 2, 3
   - Test locally if possible
   - Redeploy to AgentCore

2. **Retest** (Estimated time: 10 minutes)
   - Run Test 2 (Refund)
   - Run Test 5 (Loyalty)
   - Capture screenshots

3. **Resubmit** (Estimated time: 5 minutes)
   - Document updated test results
   - Submit same GitHub link
   - Include Submission #2 test artifacts

---

**Estimated Total Time:** 45-60 minutes  
**Expected Outcome:** 7/7 requirements pass ✅

Good luck with the fixes! The reviewer's confidence in your code is clear. 🚀
