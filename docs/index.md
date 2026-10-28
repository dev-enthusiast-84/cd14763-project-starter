---
layout: default
title: Home
nav_order: 1
---

# Customer Support AI Agent

> AWS AI Engineering Nanodegree - Module 2 Project Implementation

## 🎯 Project Overview

A fully functional AI customer support agent deployed on Amazon Bedrock AgentCore with:
- **Retrieval-Augmented Generation** using managed Knowledge Base
- **Cross-session Memory** with AgentCore Memory Service
- **Sandboxed Code Execution** for precise calculations
- **Live Web Browsing** for real-time information
- **External Tool Integration** via Model Context Protocol

## ✨ Key Features

- 📚 Smart knowledge base search with semantic retrieval
- 💰 Loyalty discount calculator with secure sandboxing
- 🧠 Multi-session customer memory and preferences
- 🛠️ Lambda integration for order tracking and refunds
- 🌐 Live web browsing capabilities
- 🔐 Enterprise-grade security with credential protection

## 📋 Implementation Status

**All requirements met and verified:**
- ✅ Cloud deployment with BedrockAgentCoreApp
- ✅ MCP integration with Gateway tools
- ✅ RAG with Bedrock Knowledge Base
- ✅ Cross-session memory with MemoryHook
- ✅ Secure code execution with fallbacks
- ✅ Browser tool integration
- ✅ Pydantic output validation
- ✅ Security audit and testing

## 🚀 Quick Start

```bash
# Setup
cd starter
uv sync --python 3.13

# Deploy
agentcore deploy
uv run setup_permissions.py

# Test
agentcore invoke '{"prompt": "Hello", "customer_id": "CUST-123"}'
```

## 📁 Architecture

```
Agent Runtime (AgentCore)
├── Tools
│   ├── Search Knowledge Base (RAG)
│   ├── Calculate Loyalty Discount (Code Interpreter)
│   ├── Memory Retrieval & Save (Cross-session)
│   ├── Gateway Tools (Lambda via MCP)
│   └── Browser (Live web access)
├── Bedrock Model (Amazon Nova 2 Lite)
└── Hooks (Memory + Validation)
```

## 🔒 Security

- No hardcoded AWS credentials in code
- Placeholder values with .gitignore protection
- Pydantic validation for all outputs
- Sandboxed code execution
- Comprehensive security audit completed

## 📊 Test Results

- Functional: All tools tested and verified
- Security: No vulnerabilities found
- Code Quality: Full type hints, comprehensive error handling
- Production: Scalable, cost-efficient, resilient

## 🎓 Technical Highlights

### Conversation Summarization
When session history exceeds token budget, older turns are summarized instead of dropped, preserving context while managing costs.

### Pydantic Validation
All tool responses validated against models for type safety and integration readiness.

### Cross-Session Memory
MemoryHook implements semantic and preference-based retrieval, allowing personalization across sessions.

### Secure Code Execution
Self-contained Python code with embedded business rules executes in isolated sandbox.

## 📚 Resources

- [AWS Bedrock AgentCore](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Bedrock Knowledge Base](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base.html)
- [AgentCore Memory](https://docs.aws.amazon.com/bedrock/latest/userguide/memory.html)

## 📝 Reflection

This project demonstrates enterprise-grade agent architecture with careful attention to:
- **Security**: Credential protection and validated outputs
- **Scalability**: Optimized token usage and conversation summarization
- **Reliability**: Comprehensive error handling and fallbacks
- **Integration**: Multiple external services coordinated seamlessly

---

**Repository:** [github.com/dev-enthusiast-84/cd14763-project-starter](https://github.com/dev-enthusiast-84/cd14763-project-starter)
