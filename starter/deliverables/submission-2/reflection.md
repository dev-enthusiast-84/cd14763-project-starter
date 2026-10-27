# Project Reflection — Customer Support AI Agent

## Why the Browser Tool Needed Its Own Instruction Block

My initial system prompt included a blanket rule: "Never call the same tool more than once." The intent was to prevent looping, but it silently broke the browser tool, which requires a fixed multi-step sequence — init_session, navigate, get content, close. The model treated each failed init_session as a violation and retried rather than proceed.

The logs made this visible: seven browser calls in one request, the first three failing instantly because Pydantic rejected invalid session names. The actual work only started on call four. Fixing it meant exempting the browser from the restriction and adding a concrete session name example to the prompt. A system prompt is the model's behavioral contract — contradictory instructions produce silent retry loops, not obvious errors.

## The Thing That Took the Longest to Fix — Code Interpreter Response Shape

The code interpreter tool was the hardest part of the project. The first version called `response.get("result")` and got `None` every time — no exception, no error message. I assumed the discount logic was broken and rewrote it in plain Python — the math was fine. The problem was how I was reading the response.

After printing the raw response I saw it: the return value was a streaming iterator, not a dict. The actual output lived at `response["stream"] → list(stream) → events[0]["result"]["structuredContent"]["stdout"]`. There's no helpful error when you miss a level — you just get `None`.

Once the path was clear I also needed to check `exitCode` before trusting `stdout`, because a Python runtime error still produces an event with the message in `stderr` instead. The fallback handles that explicitly. It was a documentation gap that cost several wrong assumptions.

## One Thing I Would Do Differently in Production

My initial implementation applied a single 60-second blanket timeout to the entire agent invocation. A knowledge base query should resolve in under five seconds, but a browser fetch to retrieve a live product page can legitimately take much longer — one timeout for both hides which tool is the actual bottleneck and makes it impossible to set a meaningful SLA. In production I'd instrument each tool call individually, surface per-tool latency as a CloudWatch metric, and alarm on p95 so slow dependencies are visible rather than silently consuming the budget.
