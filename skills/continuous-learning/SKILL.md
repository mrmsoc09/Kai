---
name: continuous-learning
version: 1.0.0
description: Capture successful solutions and learned patterns for future reuse
category: learning
author: KaisonOne
triggers:
  - continuous learning
  - remember solution
  - save solution
  - learned answer
  - knowledge retention
  - reuse solution
---

# Continuous Learning & Knowledge Retention

Skill for capturing, organizing, and retrieving learned solutions to improve future task execution.

## Purpose

Automatically capture successful solutions, patterns, and learnings from completed tasks so they can be reused in future similar scenarios without reinventing the wheel.

## Procedure

### Step 1: Capture Successful Solutions

After completing a task successfully, document:
- Problem description
- Solution approach  
- Code/commands used
- Key insights
- Error patterns encountered

```python
# Example: After fixing a dependency issue
learning = {
    "problem": "ModuleNotFoundError for neo4j during test collection",
    "solution": "pip install neo4j llama-index",
    "context": "test suite execution",
    "tags": ["dependencies", "testing", "neo4j"],
    "timestamp": "2026-04-30",
    "success": True
}
```

### Step 2: Save to Knowledge Base

Store learnings in `skills/continuous-learning/knowledge/`

```bash
echo '{"problem": "...", "solution": "..."}' > skills/continuous-learning/knowledge/$(echo "problem_desc" | md5sum | cut -d' ' -f1).json
```

### Step 3: Pre-Task Knowledge Check

Before starting a new task, search knowledge base:

```bash
grep -r "keyword" skills/continuous-learning/knowledge/ 2>/dev/null | head -5
```

### Step 4: Apply Learned Patterns

When similar task detected:
1. Load previous solution
2. Adapt to current context
3. Execute with learned optimizations
4. Document any new learnings

## Output

Knowledge base: `skills/continuous-learning/knowledge/`
Index: `skills/continuous-learning/knowledge/index.json`
