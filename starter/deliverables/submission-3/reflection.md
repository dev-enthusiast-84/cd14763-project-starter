# Project Reflection — Customer Support AI Agent

## The Browser Tool and Why Rules Can Break

I added a simple rule: "Never call the same tool more than once." Seemed sensible — prevent looping. But it completely broke the browser tool without any obvious error. The browser needs: initialize session, navigate, grab content, close. When initialization failed, the model just retried. Seven calls in one request, the first three dead ends.

A system prompt is a behavioral contract. Contradictory rules produce silent retry loops, not obvious errors.

## Debugging the Code Interpreter

The code interpreter was the hardest part. I'd call `response.get("result")` and get `None`. No exception, no error message. I rewrote the discount calculation in plain Python thinking it was broken. The math was fine.

Then I printed the raw response. The API returns a streaming iterator, not a dict. The actual output was at `response["stream"] → events[0]["result"]["structuredContent"]["stdout"]`. I also had to check `exitCode` because Python runtime errors appear in `stderr`. Miss that step and you're flying blind.

## When Tools Require Multi-Step Workflows

A refund is actually two operations: look up the order, then initiate refund with that total. My system prompt said "answer immediately once any tool returns" — the model skipped the lookup and called initiate_refund directly. Lambda's default amount was zero, so it succeeded silently.

I had to replace blanket rules with actual workflow steps: "to process a refund: first retrieve the order, then call initiate_refund with that total." Tools have dependencies. The model won't infer them without being told.

## Deployment Surprises

When I switched from hardcoded IDs to `os.environ.get()`, deployment failed with `Invalid length for memoryId, value: 0`. AgentCore's packager silently excludes `.env` files. Renaming to `.env.agent` fixed it.

The setup script using `ast.literal_eval` broke too. I added a `.env.agent` fallback so it handles both styles. If a deployment tool packages files, you have to verify what's actually in the package.

## What I'd Change in Production

I set a blanket 60-second timeout for everything. Knowledge base queries hit in under five seconds. Browser work takes longer. One timeout for both means I can't tell which tool is slow.

For production I'd measure each tool separately, push per-tool latency to CloudWatch, and alarm on p95. Then you'd actually see what's slow instead of just hitting a wall.
