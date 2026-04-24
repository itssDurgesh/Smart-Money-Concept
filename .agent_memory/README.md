# .agent_memory — Agent Persistent Memory System

> **Purpose:** This folder is the universal knowledge base for any AI agent working on this project.  
> Before doing ANY work, every agent MUST read this folder to understand context, avoid confusion, and continue seamlessly from where a previous agent left off.

---

## 📂 File Index

| File | Purpose | Read Priority |
|------|---------|---------------|
| `project_context.md` | Full project description, goals, tech stack, architecture | 🔴 **ALWAYS FIRST** |
| `current_state.md` | What has been built, what is in progress, what is next | 🔴 **ALWAYS SECOND** |
| `task_registry.md` | Master checklist of all deliverables with status tracking | 🟡 Before starting any task |
| `data_inventory.md` | All database schemas, data sources, and data flow details | 🟡 When working on data/DB/ML |
| `important_notes.md` | Critical decisions, constraints, gotchas, and domain rules | 🟠 Before making any decisions |
| `confusion_log.md` | Known ambiguities, unresolved questions, and clarifications | 🟠 When something seems unclear |
| `changelog.md` | Chronological log of all changes made by any agent | 🟢 Before and after every session |

---

## 🛡️ Agent Rules

> [!CAUTION]
> **AGENT MEMORY FIRST.** Before scanning any source code, read `.agent_memory` files.  
> **WORK IN CHUNKS.** Complete one small task → update memory → then move to the next.  
> Agent sessions can terminate at any time. If you don't update memory, the next agent loses all context.  
> **If it's not written in `.agent_memory`, it doesn't exist.**

1. **MEMORY BEFORE CODE.** Before reading ANY source file, read `.agent_memory` first. Find the relevant info, understand what's been done, and identify what needs changing — THEN go to the code. Never blindly scan the entire codebase.
2. **READ BEFORE YOU WRITE.** Always read `project_context.md` and `current_state.md` before doing anything.
3. **LOG AFTER YOU WORK.** Every agent must append to `changelog.md` after completing work.
4. **UPDATE STATE.** Update `current_state.md` and `task_registry.md` to reflect progress.
5. **FLAG CONFUSION.** If something is ambiguous, log it in `confusion_log.md` — never silently assume.
6. **RESPECT DECISIONS.** Read `important_notes.md` before overriding any past design choice.
7. **NO ORPHAN WORK.** Every deliverable must appear in `task_registry.md` with a clear status.
8. **CHUNK YOUR WORK.** After each file created/modified, update memory files BEFORE moving on. Never batch 3+ files without a memory update.

---

## 🔄 Agent Handoff Protocol

When starting a new session:
```
1. Read README.md (this file)
2. Read project_context.md → understand the project
3. Read current_state.md → understand where things stand
4. Read task_registry.md → pick up the next task
5. Read important_notes.md → understand constraints
6. Check confusion_log.md → see unresolved questions
7. Read changelog.md → see what was done recently
```

When ending a session:
```
1. Update current_state.md → reflect new state
2. Update task_registry.md → mark completed/in-progress tasks
3. Append to changelog.md → log what you did
4. Update confusion_log.md → flag anything unresolved
5. Update important_notes.md → if you made a key decision
```

---

*This system is designed so that ANY agent (Claude, Gemini, GPT, Copilot, or a human) can seamlessly pick up work without losing context.*
