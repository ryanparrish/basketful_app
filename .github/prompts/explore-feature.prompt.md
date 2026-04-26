---
name: explore-feature
description: Explore the possibilities for a new feature idea across the codebase — from safe and incremental to bold and transformative. Use when you want to understand what's possible before committing to a direction. Not a build prompt — a thinking prompt.
---

# Feature Exploration

You have an idea. Before writing a single line of production code, this prompt helps you understand **what is possible**, **what already exists**, and **how far you could take it** — across three levels of ambition.

> *"Exploration is not a luxury. It is the process by which you discover whether your idea is good."*

This is not a spec. It is a **map of the possibility space**.

---

## Workflow

### 1. Understand the Idea

Start by making sure the feature idea is clearly stated. Ask yourself (or the user):

- [ ] What problem does this solve or what value does it add?
- [ ] Who benefits — participants, staff, admins, or all of them?
- [ ] Is there a trigger? (user action, scheduled task, data event)
- [ ] Any rough sense of where in the app it might live?

Don't try to be precise yet. A vague idea is fine — that's what exploration is for.

---

### 2. Explore the Codebase

Before generating ideas, **read the terrain**. Understand what already exists that is relevant:

- [ ] Are there existing models, views, or serializers that relate to this idea?
- [ ] Are there existing UI patterns (components, pages, flows) that could be extended?
- [ ] Are there signals, Celery tasks, or middleware that could be leveraged?
- [ ] Are there any existing data points, fields, or relationships that are adjacent to this idea?
- [ ] What would need to be added vs what already exists?

Use this context to ground all three proposals in **what is actually there**, not abstract theory.

---

### 3. Generate Three Possibilities — Mild to Wild (Parallel Sub-Agents)

Spawn **three sub-agents simultaneously** using the Task tool — one per proposal. Each agent explores the same feature idea from a different level of ambition. Run them in parallel so proposals are generated concurrently, then present the results in order.

```
Prompt template for each sub-agent:

You are exploring a feature idea for the Basketful app (Django + DRF backend, React-Admin
frontend, React participant frontend).

Feature idea: [feature description from step 1]

Codebase context gathered: [relevant models, files, patterns from step 2]

Your constraint: [assign one constraint per agent — see below]

Produce a self-contained feature proposal in this exact format:

- **What it does**: Describe the feature at this ambition level.
- **What it touches**: Specific files, models, serializers, components, or Celery tasks affected.
- **What it reuses**: Existing patterns, signals, or infrastructure it builds on.
- **What it defers / reimagines**: What this version leaves out (Mild/Medium) or challenges (Wild).
- **Key design decisions**: The non-trivial choices — data model shape, permission logic, async vs sync, etc.
- **Rough effort**: S / M / L / XL / Epic
- **Code sketch** (optional): A short illustrative snippet showing the key new piece only — not a full implementation.
```

**Agent constraints:**

- **Agent 1 — Mild** `"The Natural Extension"`: Constraint: *fit entirely inside what already exists — no new models, no new background tasks, ships in days.*
- **Agent 2 — Medium** `"The Considered Build"`: Constraint: *introduce new infrastructure (a model, an endpoint, a Celery task) but stay within the existing architecture patterns.*
- **Agent 3 — Wild** `"The Bold Rethink"`: Constraint: *challenge at least one existing assumption — reframe the feature, expand its scope dramatically, or reimagine who it serves.*

**Rules for sub-agents:**
- Each agent must read the codebase context gathered in step 2 before proposing.
- Agents must not produce similar proposals — enforce radical difference between levels.
- Wild must be genuinely bold. Mild must be genuinely small. No sandbagging, no gold-plating.

---

Present proposals sequentially after all three agents complete — 🟢 Mild first, then 🟡 Medium, then 🔴 Wild — so the user can absorb each before the comparison.

---

### 4. Compare and Reflect

After presenting all three, briefly compare them:

| | Mild | Medium | Wild |
|---|---|---|---|
| **Effort** | | | |
| **User impact** | | | |
| **Technical risk** | | | |
| **Reversible?** | | | |
| **Builds toward Wild?** | | | |

Then offer a **recommendation**: which option (or which combination of options, phased) best fits the current state of the product?

---

### 5. Next Steps

End with a clear fork in the road:

- If the user wants to **build Mild** → point to the specific files and suggest the first PR scope.
- If the user wants to **explore Medium or Wild further** → identify the open questions that need answers before building.
- If the user wants to **combine approaches** → sketch a phased roadmap (Mild now → Medium next → Wild later).

---

## Ground Rules

- **No gold-plating the Mild option.** Keep it genuinely small.
- **No sandbagging the Wild option.** Make it genuinely bold.
- **All options must be grounded in this codebase.** Reference real files, real models, real patterns — not generic advice.
- **Code sketches are optional.** Only include them when they add clarity, not bulk.
- **This is not a build prompt.** Do not generate full implementations unless the user explicitly asks to proceed.
