"""
Customer Support AI Agent — Starter Code
==========================================
Your task is to complete this file by implementing all sections marked
with # TODO comments.

Reference the step-by-step solution files and INSTRUCTIONS.md for guidance.
Do NOT copy the solution directly — work through each section yourself.

Run locally (after filling in config values):
  uv run main.py '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'

Deploy to AgentCore:
  agentcore deploy

Invoke deployed agent:
  agentcore invoke '{"prompt": "Hello", "customer_id": "CUST-123", "session_id": "s1"}'
"""

# ── Imports ───────────────────────────────────────────────────────────────────
# These imports are provided. Do not remove them.
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.memory import MemoryClient
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamable_http_client
import argparse, json
import os, asyncio, boto3
from pathlib import Path
from strands.hooks import (
    HookProvider, AfterInvocationEvent, HookRegistry, MessageAddedEvent,
)
import logging
import uuid
from typing import Dict
from bedrock_agentcore.tools.code_interpreter_client import code_session
from strands_tools.browser import AgentCoreBrowser
from pydantic import BaseModel, Field, ValidationError


from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env.agent")

_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, _log_level, logging.INFO))
logger = logging.getLogger("CSAI_Agent")

# ── TODO 1 — App Initialisation ───────────────────────────────────────────────
# Create a BedrockAgentCoreApp instance.
# This registers the ASGI server for AgentCore deployment.
# There must be exactly one instance per deployment.
#
# Hint: app = BedrockAgentCoreApp()

# TODO: Create the BedrockAgentCoreApp instance
app = BedrockAgentCoreApp()  # Replace this line


# Suppress interactive tool-consent prompts (required in headless deployments).
os.environ["BYPASS_TOOL_CONSENT"] = "true"


# ── TODO 2 — Configuration ────────────────────────────────────────────────────
# Replace the placeholder strings with your actual AWS resource values.
# You collected these in Part 1 of the INSTRUCTIONS.
#
# GATEWAY_URL format: https://<alias>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp
# KB_ID       format: 10-character alphanumeric string from the KB console
# REGION:     your AWS region, e.g. "us-east-1"
# MEMORY_ID   format: shown in the AgentCore Memory console

GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
KB_ID       = os.environ.get("KB_ID", "")
REGION      = os.environ.get("REGION", "us-east-1")
MEMORY_ID   = os.environ.get("MEMORY_ID", "")


# ── TODO 3 — Model and Clients ────────────────────────────────────────────────
# Create:
#   1. A BedrockModel using model_id "global.amazon.nova-2-lite-v1:0"
#   2. A MemoryClient with region_name=REGION
#   3. A boto3 client for the "bedrock-agent-runtime" service in REGION
#
# Hint: model = BedrockModel(model_id=model_id)

model_id = "global.amazon.nova-2-lite-v1:0"

# TODO: Create the BedrockModel instance
model = BedrockModel(model_id=model_id)  # Replace this line

# TODO: Create the MemoryClient instance
memory_client = MemoryClient(region_name=REGION)  # Replace this line

# TODO: Create the boto3 bedrock-agent-runtime client
_bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)  # Replace this line


# ── Pydantic Output Models ─────────────────────────────────────────────────────
class DiscountResult(BaseModel):
    """Validated output structure for calculate_loyalty_discount.

    Enforces business-rule constraints on the discount breakdown so that
    malformed or out-of-range values are caught before being returned to the
    caller or the LLM.
    """

    original_total: float
    points_redeemed: int
    points_discount: float
    tier_discount_pct: float
    tier_discount: float
    final_total: float = Field(..., ge=0, description="Must be non-negative")
    total_savings: float = Field(..., ge=0, description="Must be non-negative")
    points_earned: int = Field(..., ge=0, description="Must be non-negative")
    remaining_points: int


# ── TODO 4 — Namespace Helper ─────────────────────────────────────────────────
# Implement get_namespaces() to return a dict mapping strategy type to
# namespace template string. 
#
# Steps:
#   1. Call mem_client.get_memory_strategies(memory_id) to get strategy list
#   2. Return a dict: { strategy["type"]: strategy["namespaces"][0] for each strategy }
#
# Example output:
#   { "SEMANTIC": "cs_agent/{actorId}/facts",
#     "USER_PREFERENCE": "cs_agent/{actorId}/preferences" }

def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Return a dict mapping strategy type → namespace template string."""
    strategies = mem_client.get_memory_strategies(memory_id)
    result = {}
    for strategy in strategies:
        # Support both new namespaceTemplates field and legacy namespaces field
        ns_list = strategy.get("namespaceTemplates") or strategy.get("namespaces") or []
        if ns_list:
            result[strategy["type"]] = ns_list[0]
    return result


# ── TODO 5 — Memory Hook ──────────────────────────────────────────────────────
# Implement MemoryHook, a HookProvider subclass that adds long-term memory.
#
# The class needs:
#   __init__(self, actor_id, session_id, memory_client, memory_id)
#     — store all four as instance attributes
#     — call get_namespaces() and store the result as self.namespaces
#
#   retrieve_customer_context(self, event: MessageAddedEvent)
#     — only runs for plain-text user messages (not tool results)
#     — for each strategy namespace, call memory_client.retrieve_memories(
#          memory_id, namespace (formatted with actorId), query, top_k=5)
#     — collect non-empty memory texts tagged with their strategy type
#     — if any memories found, prepend them to the user message as:
#          "Customer Context:\n<memories>\n\n<original_message>"
#
#   save_support_interaction(self, event: AfterInvocationEvent)
#     — walk the message list backwards to find the last plain-text user
#       query and the last assistant response
#     — call memory_client.create_event(memory_id, actor_id, session_id,
#          messages=[(customer_query, "USER"), (agent_response, "ASSISTANT")])
#
#   register_hooks(self, registry: HookRegistry)
#     — register retrieve_customer_context on MessageAddedEvent
#     — register save_support_interaction on AfterInvocationEvent

class MemoryHook(HookProvider):
    """Long-term memory hook for the customer support agent."""

    def __init__(
        self,
        actor_id: str,
        session_id: str,
        memory_client: MemoryClient,
        memory_id: str,
    ):
        self.actor_id = actor_id
        self.session_id = session_id
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.namespaces = get_namespaces(memory_client, memory_id)

    def retrieve_customer_context(self, event: MessageAddedEvent):
        """Retrieve relevant memories and prepend them to the user message."""
        # TODO: Implement memory retrieval
        # Steps:
        #   1. Get the last message from event.agent.messages
        #   2. Check it is a user message and not a tool result
        #   3. Extract the user query text
        #   4. For each namespace in self.namespaces, call retrieve_memories()
        #   5. Collect non-empty memory texts with strategy type tags
        #   6. If any found, prepend them to the user message

        # Step 1: Get the last message from event.agent.messages
        messages = event.agent.messages
        if not messages:
            return
        last_message = messages[-1]

        # Step 2: Check it is a user message and not a tool result
        if last_message.get("role") != "user":
            return
        content = last_message.get("content", "")
        if isinstance(content, list):
            if any("toolResult" in block for block in content):
                return

        # Step 3: Extract the user query text
            query = " ".join(b.get("text", "") for b in content if "text" in b)
        else:
            query = content

        if not query.strip():
            return

        # Step 4: For each namespace in self.namespaces, call retrieve_memories()
        memory_texts = []
        for strategy_type, namespace_template in self.namespaces.items():
            namespace = namespace_template.format(actorId=self.actor_id)
            results = self.memory_client.retrieve_memories(
                self.memory_id, namespace, query, top_k=5
            )
            # Step 5: Collect non-empty memory texts with strategy type tags
            for mem in results:
                text = mem.get("content", {}).get("text", "").strip()
                if text:
                    memory_texts.append(f"[{strategy_type}] {text}")

        # Step 6: If any found, prepend them to the user message
        if memory_texts:
            context_block = (
                "Customer Context (background only — answer the current request below, not these memories):\n"
                + "\n".join(memory_texts)
            )
            last_message["content"] = [{"text": f"{context_block}\n\nCurrent request: {query}"}]

    def save_support_interaction(self, event: AfterInvocationEvent):
        """Save the completed turn to memory after the agent responds."""
        # TODO: Implement memory saving
        # Steps:
        #   1. Get messages from event.agent.messages
        #   2. Walk backwards to find the last user query (plain text)
        #      and the last assistant response
        #   3. Call memory_client.create_event() with both messages

        # Step 1: Get messages from event.agent.messages
        messages = event.agent.messages
        customer_query = None
        agent_response = None

        # Step 2: Walk backwards to find the last user query (plain text) and assistant response
        for msg in reversed(messages):
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "assistant" and agent_response is None:
                if isinstance(content, str) and content.strip():
                    agent_response = content
                elif isinstance(content, list):
                    text = " ".join(b.get("text", "") for b in content if "text" in b)
                    if text.strip():
                        agent_response = text
            elif role == "user" and customer_query is None:
                if isinstance(content, str) and content.strip():
                    customer_query = content
                elif isinstance(content, list):
                    if not any("toolResult" in b for b in content):
                        text = " ".join(b.get("text", "") for b in content if "text" in b)
                        if text.strip():
                            # Strip context augmentation added by retrieve_customer_context
                            # so we save only the original query, not the memory-augmented form.
                            marker = "Current request: "
                            idx = text.find(marker)
                            customer_query = text[idx + len(marker):] if idx != -1 else text
            if customer_query and agent_response:
                break

        # Step 3: Call memory_client.create_event() with both messages
        if customer_query and agent_response:
            self.memory_client.create_event(
                self.memory_id,
                self.actor_id,
                self.session_id,
                messages=[(customer_query, "USER"), (agent_response, "ASSISTANT")],
            )

    def register_hooks(self, registry: HookRegistry) -> None:  # type: ignore
        """Register both memory callbacks."""
        # TODO: Register retrieve_customer_context on MessageAddedEvent
        # TODO: Register save_support_interaction on AfterInvocationEvent
        registry.add_callback(MessageAddedEvent, self.retrieve_customer_context)
        registry.add_callback(AfterInvocationEvent, self.save_support_interaction)


# ── Conversation Summarization Hook ───────────────────────────────────────────
class SummarizationHook(HookProvider):
    """Summarize old turns when session history exceeds MAX_TURNS.

    Preserves context across long conversations while avoiding runaway token
    costs.  When the total user+assistant message count exceeds MAX_TURNS,
    the oldest messages (everything beyond the KEEP_RECENT most recent) are
    replaced with a single AI-generated summary injected as a user-role
    system note.  Recent turns are kept verbatim so the agent always has
    immediate context.
    """

    MAX_TURNS = 10   # Trigger threshold (user + assistant messages combined)
    KEEP_RECENT = 4  # Number of recent messages to preserve verbatim

    def __init__(self) -> None:
        self._bedrock = boto3.client("bedrock-runtime", region_name=REGION)

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_text(content) -> str:
        if isinstance(content, list):
            return " ".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and "text" in b
            )
        return str(content) if content else ""

    @staticmethod
    def _is_tool_result(content) -> bool:
        if isinstance(content, list):
            return any("toolResult" in b for b in content if isinstance(b, dict))
        return False

    def _turn_count(self, messages) -> int:
        return sum(1 for m in messages if m.get("role") in ("user", "assistant"))

    # ── hook callback ─────────────────────────────────────────────────────────

    def summarize_if_needed(self, event: MessageAddedEvent) -> None:
        """Collapse old turns into a summary block when history grows too long."""
        messages = event.agent.messages
        if self._turn_count(messages) <= self.MAX_TURNS:
            return

        cut = max(0, len(messages) - self.KEEP_RECENT)
        old_messages, recent_messages = messages[:cut], messages[cut:]

        # Build a plain-text transcript of the old turns (skip tool results)
        lines: list[str] = []
        for msg in old_messages:
            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = msg.get("content", "")
            if self._is_tool_result(content):
                continue
            text = self._extract_text(content).strip()
            if text:
                lines.append(f"{role.capitalize()}: {text}")

        if not lines:
            return  # Nothing useful to summarize

        prompt = (
            "Summarize the following customer support conversation in 3–5 sentences. "
            "Preserve any order numbers, product names, and stated customer preferences:\n\n"
            + "\n".join(lines)
        )
        try:
            resp = self._bedrock.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
            )
            summary_text = resp["output"]["message"]["content"][0]["text"]
            summary_msg: Dict = {
                "role": "user",
                "content": [{"text": f"[Earlier conversation summary]: {summary_text}"}],
            }
            # Replace the old section with the compact summary
            event.agent.messages[:] = [summary_msg] + list(recent_messages)
            logger.info("Summarised %d old messages into a single summary block.", len(old_messages))
        except Exception as exc:
            logger.warning("Conversation summarization skipped (%s): %s", type(exc).__name__, exc)

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(MessageAddedEvent, self.summarize_if_needed)


# ── TODO 6 — Knowledge Base Tool ─────────────────────────────────────────────
# Implement search_knowledge_base(query) using the @tool decorator.
#
# Steps:
#   1. Guard: if KB_ID is empty return "Knowledge base not configured."
#   2. Call _bedrock_runtime.retrieve(
#          knowledgeBaseId=KB_ID,
#          retrievalQuery={"text": query}
#      )
#   3. Extract resp["retrievalResults"]; return a message if empty
#   4. Join the text chunks with "\n---\n" and return the result
#
# The docstring is the tool description — the model uses it to decide when
# to call this tool, so keep it clear and accurate.

@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the Amazon product catalog and support knowledge base.
    Use this for product specifications, return policies, warranty
    information, loyalty program details, and order status definitions.

    Args:
        query: The question or topic to search for

    Returns:
        Relevant information retrieved from the knowledge base
    """
    # Step 1: Guard — if KB_ID is empty return a message
    if not KB_ID:
        return "Knowledge base not configured."

    # Step 2: Call _bedrock_runtime.retrieve()
    resp = _bedrock_runtime.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
    )

    # Step 3: Extract retrievalResults; return a message if empty
    results = resp.get("retrievalResults", [])
    if not results:
        return "No relevant information found in the knowledge base."

    # Step 4: Join the text chunks with "\n---\n" and return
    chunks = [r["content"]["text"] for r in results if r.get("content", {}).get("text")]
    return "\n---\n".join(chunks)


# ── TODO 7 — Loyalty Discount Tool (Code Interpreter) ────────────────────────
# Implement calculate_loyalty_discount() using the @tool decorator.
#
# The tool must:
#   1. Build a self-contained Python code string that:
#        • Defines earn_rates: {"standard": 1, "device": 2, "fresh": 5}
#        • Defines tier_rates: {"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}
#        • Calculates points_redeemed (floor to nearest 500, cap at 50% of order)
#        • Calculates tier_discount (applied to subtotal after points)
#        • Calculates final_total, total_savings, points_earned, remaining_points
#        • Prints a JSON result dict
#   2. Execute the code with code_session(REGION).invoke("executeCode", {...})
#      using language="python" and clearContext=True
#   3. Return the first result event as a JSON string
#   4. Include a fallback that computes only the tier discount if the
#      Code Interpreter is unavailable

@tool
def calculate_loyalty_discount(
    loyalty_points: int,
    tier: str,
    order_total: float,
    product_category: str = "standard",
) -> str:
    """
    Calculate the loyalty discount for a customer order using the
    AgentCore Code Interpreter. Runs exact arithmetic in a secure sandbox.

    Args:
        loyalty_points:   Customer's current points balance
        tier:             Customer tier — Silver, Gold, or Platinum
        order_total:      Order total in USD
        product_category: standard, device, or fresh

    Returns:
        Full discount breakdown and final price
    """
    # TODO: Build the code string (use an f-string to inject the arguments)
    code = f"""
import json

loyalty_points = {loyalty_points}
tier = "{tier}"
order_total = {order_total}
product_category = "{product_category}"

earn_rates = {{"standard": 1, "device": 2, "fresh": 5}}
tier_rates = {{"Silver": 0, "Gold": 10, "Platinum": 15}}

points_value = (loyalty_points // 500) * 5.0
max_redemption = order_total * 0.50
points_redeemed = round(min(points_value, max_redemption), 2)
points_used = int((points_redeemed / 5.0) * 500)

subtotal_after_points = round(order_total - points_redeemed, 2)
tier_discount_pct = tier_rates.get(tier, 0)
tier_discount = round(subtotal_after_points * (tier_discount_pct / 100), 2)
final_total = round(subtotal_after_points - tier_discount, 2)

total_savings = order_total - final_total
points_earned = int(final_total * earn_rates.get(product_category, 1))
remaining_points = loyalty_points - points_used + points_earned

print(json.dumps({{
    "original_total": order_total,
    "points_redeemed": points_used,
    "points_discount": points_redeemed,
    "tier_discount_pct": tier_discount_pct,
    "tier_discount": tier_discount,
    "final_total": round(final_total, 2),
    "total_savings": round(total_savings, 2),
    "points_earned": points_earned,
    "remaining_points": remaining_points,
}}))
"""

    # TODO: Execute the code using code_session and return the result
    try:
        with code_session(REGION) as session:
            response = session.invoke("executeCode", {
                "language": "python",
                "code": code,
                "clearContext": True,
            })
            stream = response.get("stream")
            events = list(stream)
            if events:
                result = events[0].get("result", {})
                structured = result.get("structuredContent", {})
                if structured.get("exitCode", 1) == 0:
                    raw = structured.get("stdout", "")
                    try:
                        validated = DiscountResult.model_validate_json(raw)
                        return validated.model_dump_json(indent=2)
                    except ValidationError as ve:
                        logger.warning("DiscountResult validation failed: %s", ve)
                        return raw
                return json.dumps({"error": structured.get("stderr", "Execution failed")})
            return json.dumps({"error": "No output from code interpreter"})

    except Exception as e:
        logger.warning(f"Code Interpreter unavailable, using tier-only fallback ({type(e).__name__}): {e}")
        tier_rates = {"Silver": 0, "Gold": 10, "Platinum": 15}
        pct = tier_rates.get(tier, 0)
        tier_discount = round(order_total * (pct / 100), 2)
        final_total = round(order_total - tier_discount, 2)
        raw = json.dumps({
            "original_total": order_total,
            "points_redeemed": 0,
            "points_discount": 0.0,
            "tier_discount_pct": pct,
            "tier_discount": tier_discount,
            "final_total": final_total,
            "total_savings": tier_discount,
            "points_earned": 0,
            "remaining_points": loyalty_points,
        })
        try:
            validated = DiscountResult.model_validate_json(raw)
            return validated.model_dump_json(indent=2)
        except ValidationError as ve:
            logger.warning("DiscountResult validation failed in fallback: %s", ve)
            return raw


# ── TODO 8 — Agent Entrypoint ─────────────────────────────────────────────────
# Implement the invoke() function decorated with @app.entrypoint.
#
# Steps:
#   1. Extract user_input, actor_id, and session_id from the payload
#      (generate a UUID if session_id is missing)
#   2. Instantiate MemoryHook for this actor/session
#   3. Instantiate AgentCoreBrowser(region=REGION)
#   4. Build the tools list: [search_knowledge_base, calculate_loyalty_discount,
#                              agent_core_browser.browser]
#   5. Connect to the Gateway via MCPClient, load gateway_tools, extend tools list
#   6. Create and invoke the Agent with all tools, hooks, and system_prompt
#   7. Return the text from the first content block of the response
#   8. Handle exceptions gracefully

@app.entrypoint
async def invoke(payload, context=None):
    """
    Main handler called by AgentCore for every incoming request.

    Expected payload keys:
      prompt      (str, required) — the customer's message
      customer_id (str, optional) — unique customer identifier
      session_id  (str, optional) — session identifier; generated if absent
    """
    # TODO: Implement the agent invocation
    # Step 1: Extract user_input, actor_id, and session_id from the payload
    try:
        user_input = payload.get("prompt", "")
        actor_id = payload.get("customer_id", "anonymous")
        session_id = payload.get("session_id") or str(uuid.uuid4())

        # Step 2: Instantiate MemoryHook for this actor/session
        memory_hook = MemoryHook(
            actor_id=actor_id,
            session_id=session_id,
            memory_client=memory_client,
            memory_id=MEMORY_ID,
        )

        # Step 3: Instantiate AgentCoreBrowser
        agent_core_browser = AgentCoreBrowser(region=REGION)

        # Step 4: Build the tools list
        tools = [search_knowledge_base, calculate_loyalty_discount, agent_core_browser.browser]

        # Step 5: Connect to the Gateway via MCPClient and extend tools list
        with MCPClient(
            lambda: streamable_http_client(GATEWAY_URL)
        ) as gateway_client:
            try:
                gateway_tools = gateway_client.list_tools_sync()
                tools.extend(gateway_tools)

                logger.info(
                    "Gateway connected successfully. Loaded %d tools.",
                    len(gateway_tools),
                )

            except TimeoutError:
                logger.exception("Gateway tool loading timed out")

            except ConnectionError:
                logger.exception("Gateway connection failed")

            except Exception as exc:
                logger.exception(
                    "Gateway tool loading failed: %s", exc
                )

            # Step 6: Create and invoke the Agent
            system_prompt = (
                "You are a helpful customer support agent for an e-commerce company. "
                "Use the available tools to answer customer questions accurately about "
                "products, orders, returns, warranties, and loyalty rewards. "
                "Always be polite, concise, and helpful. "
                "For a refund request: first look up the order with the order-tracking tool to get the order total, "
                "then call initiate_refund with the order_id, a reason, and amount set to the order total. "
                "Report the refund ID, APPROVED status, amount, and the 3-5 business day credit window to the customer. "
                "Never initiate the same refund twice. "
                "The browser tool requires multiple sequential calls to complete a task "
                "(init_session → navigate → get content → close) — always follow this sequence without skipping steps. "
                "Browser session names must use only lowercase letters, numbers, and hyphens "
                "(no underscores or spaces), and be between 10 and 36 characters long — "
                "for example 'udacity-session-01' not 'udacity_session'. "
                "If any tool fails or returns no useful data, tell the customer you are unable to help with that request."
            )
            summarization_hook = SummarizationHook()
            agent = Agent(
                model=model,
                tools=tools,
                hooks=[memory_hook, summarization_hook],
                system_prompt=system_prompt,
            )
            response = await agent.invoke_async(user_input)

        # Step 7: Return the text from the first content block of the response
        content = response.message.get("content", "")
        if isinstance(content, list):
            return content[0].get("text", "")
        return content

    except Exception:
        # Step 8: Handle exceptions gracefully
        logger.exception("Unhandled error during agent invocation")
        return "I'm sorry, I encountered an error processing your request. Please try again."


# ── CLI entry point (do not modify) ──────────────────────────────────────────
def main():
    """Run one invocation from the command line for local testing."""
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=str)
    args = parser.parse_args()
    response = asyncio.run(invoke(json.loads(args.payload)))
    print(response)


if __name__ == "__main__":
    app.run()
    # Uncomment the line below and comment app.run() for local CLI testing:
    # main()
