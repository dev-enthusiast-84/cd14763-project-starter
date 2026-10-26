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
from strands.hooks import (
    HookProvider, AfterInvocationEvent, HookRegistry, MessageAddedEvent,
)
import logging
import uuid
from typing import Dict
from bedrock_agentcore.tools.code_interpreter_client import code_session
from strands_tools.browser import AgentCoreBrowser


logging.basicConfig(level=logging.WARNING)
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
# NOTE: Code has been tested with actual values. Fill in your own values below
# to test. Remove before final commit to prevent credential leakage.
#
# GATEWAY_URL format: https://<alias>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp
# KB_ID       format: 10-character alphanumeric string from the KB console
# REGION:     your AWS region, e.g. "us-east-1"
# MEMORY_ID   format: shown in the AgentCore Memory console

GATEWAY_URL = "<gateway_url>"   # TODO: Replace with your Gateway URL
KB_ID       = "<kbid>"          # TODO: Replace with your Knowledge Base ID
REGION      = "<region>"        # TODO: Replace with your AWS region
MEMORY_ID   = "<mem_id>"        # TODO: Replace with your Memory ID


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
            context_block = "Customer Context:\n" + "\n".join(memory_texts)
            last_message["content"] = [{"text": f"{context_block}\n\n{query}"}]

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
                            customer_query = text
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
    # TODO: Implement the Knowledge Base search
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
tier_rates = {{"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}}

points_value = (loyalty_points // 500) * 5.0
max_redemption = order_total * 0.50
points_redeemed = min(points_value, max_redemption)
points_used = int((points_redeemed / 5.0) * 500)

subtotal_after_points = order_total - points_redeemed
tier_discount_pct = tier_rates.get(tier, 0.0)
tier_discount = subtotal_after_points * tier_discount_pct
final_total = subtotal_after_points - tier_discount

total_savings = order_total - final_total
points_earned = int(order_total * earn_rates.get(product_category, 1))
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
                    return structured.get("stdout", "")
                return json.dumps({"error": structured.get("stderr", "Execution failed")})
            return json.dumps({"error": "No output from code interpreter"})

    except Exception as e:
        logger.warning(f"Code Interpreter unavailable, using fallback ({type(e).__name__}): {e}")
        earn_rates = {"standard": 1, "device": 2, "fresh": 5}
        tier_rates = {"Silver": 0.00, "Gold": 0.10, "Platinum": 0.15}
        pct = tier_rates.get(tier, 0.0)
        points_value = (loyalty_points // 500) * 5.0
        max_redemption = order_total * 0.50
        points_redeemed_val = min(points_value, max_redemption)
        points_used = int((points_redeemed_val / 5.0) * 500)
        subtotal = order_total - points_redeemed_val
        tier_discount = subtotal * pct
        final_total = subtotal - tier_discount
        points_earned = int(order_total * earn_rates.get(product_category, 1))
        return json.dumps({
            "original_total": order_total,
            "points_redeemed": points_used,
            "points_discount": points_redeemed_val,
            "tier_discount_pct": pct,
            "tier_discount": round(tier_discount, 2),
            "final_total": round(final_total, 2),
            "total_savings": round(order_total - final_total, 2),
            "points_earned": points_earned,
            "remaining_points": loyalty_points - points_used + points_earned,
        })


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
        ) as mcp_client:
            gateway_tools = mcp_client.list_tools_sync()
            logger.warning(f"Gateway tools loaded: {[getattr(t, 'tool_name', getattr(t, 'name', str(t))) for t in gateway_tools]}")
            tools.extend(gateway_tools)

            # Step 6: Create and invoke the Agent
            system_prompt = (
                "You are a helpful customer support agent for an e-commerce company. "
                "Use the available tools to answer customer questions accurately about "
                "products, orders, returns, warranties, and loyalty rewards. "
                "Always be polite, concise, and helpful. "
                "Call each tool at most once per request. "
                "Once a tool returns any result, use that result to answer the customer immediately. "
                "Never call the same tool more than once. "
                "If a tool fails or returns no useful data, tell the customer you are unable to help with that request."
            )
            agent = Agent(
                model=model,
                tools=tools,
                hooks=[memory_hook],
                system_prompt=system_prompt,
            )
            response = await asyncio.wait_for(
                agent.invoke_async(user_input),
                timeout=60,
            )

        # Step 7: Return the text from the first content block of the response
        content = response.message.get("content", "")
        if isinstance(content, list):
            return content[0].get("text", "")
        return content

    except Exception as e:
        # Step 8: Handle exceptions gracefully
        logger.error(f"Error during invocation ({type(e).__name__}): {e}")
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