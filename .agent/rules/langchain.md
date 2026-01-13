---
trigger: model_decision
description: When need information about LangChain Ecosystem
---

## Agent Rules (LangChain Ecosystem)

### Documentation
- Always check for `llms.txt` at the project root.
- Treat `llms.txt` as the authoritative index for LLM-relevant docs.
- Follow linked docs in order; prefer concepts and examples.
- If missing, fall back to standard `/docs` paths.

### Framework Priority
1. **LangGraph** 
2. **LangChain Core**
3. **DeepAgent**

### Source of Truth
- Prefer official LangChain, LangGraph, and DeepAgent docs.
- Do not guess APIs; verify when uncertain.
- Favor official examples over invented ones.