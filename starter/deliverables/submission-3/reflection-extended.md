\# Project Reflection — Customer Support AI Agent

## Why the Browser Tool Needed Its Own Instruction Block

My initial system prompt included a blanket rule: "Never call the same tool more than once." The intent was to prevent looping, but it silently broke the browser tool, which requires a fixed multi-step sequence — init_session, navigate, get content, close. The model treated each failed init_session as a violation and retried rather than proceed.

The logs made this visible: seven browser calls in one request, the first three failing instantly because Pydantic rejected invalid session names. The actual work only started on call four. Fixing it meant exempting the browser from the restriction and adding a concrete session name example to the prompt. A system prompt is the model's behavioral contract — contradictory instructions produce silent retry loops, not obvious errors.

## The Thing That Took the Longest to Fix — Code Interpreter Response Shape

The code interpreter tool was the hardest part of the project. The first version called `response.get("result")` and got `None` every time — no exception, no error message. I assumed the discount logic was broken and rewrote it in plain Python — the math was fine. The problem was how I was reading the response.

After printing the raw response I saw it: the return value was a streaming iterator, not a dict. The actual output lived at `response["stream"] → list(stream) → events[0]["result"]["structuredContent"]["stdout"]`. There's no helpful error when you miss a level — you just get `None`.

Once the path was clear I also needed to check `exitCode` before trusting `stdout`, because a Python runtime error still produces an event with the message in `stderr` instead. The fallback handles that explicitly. It was a documentation gap that cost several wrong assumptions.

## One Thing I Would Do Differently in Production

My initial implementation applied a single 60-second blanket timeout to the entire agent invocation. A knowledge base query should resolve in under five seconds, but a browser fetch to retrieve a live product page can legitimately take much longer — one timeout for both hides which tool is the actual bottleneck and makes it impossible to set a meaningful SLA. In production I'd instrument each tool call individually, surface per-tool latency as a CloudWatch metric, and alarm on p95 so slow dependencies are visible rather than silently consuming the budget.

## Memory Contamination From Saving Augmented Messages

The memory hook ran two operations per turn: retrieve context and prepend it to the user message, then save the turn after the agent responded. The bug was in what got saved. Because `retrieve_customer_context` mutated the message in place — replacing the original query with `"Customer Context:\n...\n\nCurrent request: <query>"` — `save_support_interaction` then walked the message list, found that augmented string, and stored the whole thing. On the next turn the retrieved memory included the injected context from the previous turn, not just the query. Over several sessions this compounded: a hallucinated tier or order detail would be saved as if it were a real customer statement, retrieved as authoritative context, and reinforced again on every subsequent turn.

The fix was to strip the injected prefix when saving — find the `"Current request: "` marker and store only what follows. In production, any system that retrieves context and injects it before the message reaches the model must be careful to save the pre-injection form. Saving the augmented form creates a feedback loop that is nearly impossible to debug from logs alone, because each turn looks plausible in isolation.

## Broad System Prompt Rules Can Block Multi-Step Tool Workflows

The rule "call each non-browser tool at most once per request, and answer immediately once any tool returns a result" was intended as a guard against looping. It had an unintended consequence: when a refund requires two tool calls (order lookup to get the total, then initiate_refund with that total), the model skipped the first step and called initiate_refund directly. The Lambda defaulted `amount` to `0` when not supplied, and the model rationalised the result rather than reporting an error — producing "Refund approved. Credit: $0 (full refund)."

There were two separate problems here. First, Lambda defaults that silently paper over missing inputs give the model nothing to raise an alarm about. Second, an overly broad "answer immediately" rule removed the model's freedom to perform the necessary setup step. The fix was to replace the broad rule with an explicit workflow instruction ("for a refund, first look up the order, then call initiate_refund with the order total") and narrow the guard to "never initiate the same refund twice" instead. In production, any multi-step tool workflow needs to be described explicitly; the model will not infer dependencies between tools unless the system prompt makes them visible.

## The Deployment Packager Silently Excludes `.env`

Switching from hardcoded resource IDs to `os.environ.get()` with `load_dotenv()` seemed like a clean improvement locally. Every invocation failed after deploy with `Invalid length for parameter memoryId, value: 0`. The problem was inside the AgentCore toolkit's packaging step: `direct_code_deploy` zips the source directory using a built-in `dockerignore.template` that explicitly excludes `.env` under the "Virtual environments" section. There is no user-accessible override — a project-level `.dockerignore` is not consulted.

The fix was to rename the file to `.env.agent`, which is not in the exclusion list, and use `load_dotenv(Path(__file__).parent / ".env.agent")` with an absolute reference so the path resolves correctly regardless of working directory in the Lambda runtime. The broader lesson: any time a deployment tool packages files, verify which files are excluded before assuming your config will be present at runtime. Silent empty-string defaults are worse than a startup crash because they allow the agent to appear healthy while producing wrong results.

## AST-Based Config Extraction Breaks When Code Style Changes

`setup_permissions.py` read `KB_ID`, `MEMORY_ID`, and `REGION` from `main.py` source text using `ast.literal_eval`. This worked perfectly when the variables were plain string literals. The moment they became `os.environ.get(...)` calls, `ast.literal_eval` raised `ValueError`, the script caught it silently, stored `None`, and then failed with a misleading message: "Set KB_ID to your resource's literal string value in main.py first." There was no indication that the real problem was a changed coding style rather than a missing value.

The fix added a `.env.agent` fallback inside `read_settings()`: if `ast.literal_eval` yields `None` for any variable, the function reads the same config file that `main.py` uses at runtime. This makes the script resilient to either style — literal strings or environment variables — without requiring the caller to know which convention is in use. In production, tooling that parses source code for configuration values is fragile by nature; a dedicated config file or a shared constants module is a more durable contract between the deployment script and the agent code.

## Test Isolation via Memory Purge Strategy

The Memory service keys all stored data to `customer_id`. A customer ID used in one test session carries its memory state into every future session, across deploys, and even after the agent runtime is deleted and recreated — because Memory is a separate AWS resource with its own lifecycle. Early tests for the refund workflow used `CUST-123`, which is also the hardcoded customer in the order tracker mock data. After several test runs, `CUST-123` had accumulated three refund records for ORD-002, and the agent treated a new refund request as a duplicate, invented a "no additional credit" policy, and listed all three REF IDs.

Rather than using dedicated customer IDs for each test, I chose to purge and recreate memory between test runs. This validates the memory lifecycle (create → use → destroy → recreate) and ensures clean test state without managing a sprawl of test fixture IDs. For each test scenario, the flow is: initialize fresh memory state, clear any previous customer_id records, run the test, then purge memory to confirm the cleanup operation works correctly. In production this approach lets you reuse real customer IDs for testing while maintaining isolation through intentional cleanup, rather than accumulating test debris under different fixture identifiers.
