---
name: consider-ui
description: Audit an existing user interface for UX friction, confusing journeys, and interaction anti-patterns. Use when a screen feels off, a flow is hard to explain, or a user keeps making the same mistake.
---

# Consider UI — UX Friction Audit

Good design isn't noticed. Bad design is felt. This skill surfaces the moments where users hesitate, guess, or give up — before they do.

## When to Use This

- A screen has too much happening at once
- Users ask "what does this button do?" or "where did that go?"
- A flow requires explanation to a new user
- A feature exists but rarely gets used
- Something "works" but feels wrong

---

## Workflow

### 1. Understand Context First

Before auditing, ask or infer:

- [ ] Who is the user? (admin, participant, first-time, returning)
- [ ] What is their **goal** on this screen?
- [ ] What is the **happy path** — the ideal sequence of actions?
- [ ] Are there multiple user types seeing the same UI?
- [ ] What happens after this screen? (where does the journey go next)

If a file or screenshot is provided, read it carefully. If not, ask: "What screen or flow should I review?"

---

### 2. Map the User Journey

Trace the full path through the interface:

1. **Entry point** — how does the user arrive here? (nav, link, redirect, notification)
2. **First impression** — what is the first thing their eye is drawn to?
3. **Primary action** — is it obvious what to do first?
4. **Secondary actions** — are they clearly secondary, or competing for attention?
5. **Exit points** — where can the user go from here? Are they all intentional?
6. **Error states** — what happens if something goes wrong? Is recovery clear?
7. **Empty states** — what does the screen look like before data exists?

---

### 3. Identify Friction Points

For each friction point found, capture:

```
### [Friction Point Title]

**Location**: Component, page, or flow step
**User Type**: Who experiences this
**What happens**: Describe what the user sees and does
**Where confusion enters**: The exact moment it becomes unclear
**Consequence**: Does the user stop? Do the wrong thing? Miss the feature entirely?
**Severity**: 🔴 Blocking | 🟠 High | 🟡 Medium | 🔵 Low
```

#### Friction Categories to Check

**Visibility**
- [ ] Are important actions hidden below the fold or behind icons with no labels?
- [ ] Does the state of the system reflect what just happened? (feedback after save, delete, etc.)
- [ ] Are disabled controls explained? Does the user know *why* they can't act?

**Affordance**
- [ ] Do interactive elements look clickable/tappable?
- [ ] Are buttons labeled with verbs? ("Save" not "OK", "Delete Voucher" not "Confirm")
- [ ] Is there a difference between primary and secondary actions in visual weight?

**Flow Interruption**
- [ ] Does the user have to leave the current task to complete a prerequisite?
- [ ] Are confirmation dialogs used when they aren't needed (adding friction)?
- [ ] Are destructive actions (delete, expire) clearly distinct from safe actions?

**Mental Model Mismatch**
- [ ] Does the terminology match what the user calls things?
- [ ] Are concepts named consistently across screens?
- [ ] Does a feature behave the way a user would expect based on analogy to other tools?

**Information Overload**
- [ ] Is every field/column on this screen necessary for this task?
- [ ] Are there fields visible that the user can't change — adding noise without value?
- [ ] Is status information repeated in a way that creates confusion about which is authoritative?

**Trust & Confidence**
- [ ] Does the user know if their action succeeded?
- [ ] Can the user undo or recover from a mistake?
- [ ] Are irreversible actions clearly flagged as such?

**Mobile / Responsive**
- [ ] Do touch targets meet minimum size (44x44px)?
- [ ] Does the layout degrade gracefully on smaller screens?
- [ ] Are critical actions reachable without scrolling?

---

### 4. Prioritize by Impact

Group findings into a prioritized list:

| Priority | Finding | User Impact | Effort to Fix |
|----------|---------|-------------|---------------|
| 🔴 1 | ... | Blocking / causes errors | ... |
| 🟠 2 | ... | High friction / task abandonment | ... |
| 🟡 3 | ... | Confusion / slower completion | ... |
| 🔵 4 | ... | Minor polish | ... |

---

### 5. Suggest Refinements

For each finding, propose a specific improvement:

- **Not**: "Make it clearer"
- **Yes**: "Replace the icon-only 'Revert' button with a labeled button that reads 'Undo Apply' and add a tooltip explaining the state change"

Refinements should be:
- Concrete (what exactly changes)
- Minimal (smallest change with the biggest improvement)
- Grounded in the user's goal, not the developer's model

---

### 6. Identify What's Working

Always call out what the UI does well. Audits that only find problems:

- Miss patterns worth repeating elsewhere
- Demoralise the team
- Ignore the cost of changing what already works

---

## Guiding Principles

**The user is not broken.** If they're confused, the interface is unclear.

**Clarity over cleverness.** A button that says "Mark as Applied" is better than an ambiguous state toggle.

**Proximity matters.** Related actions should be near related content. Destructive actions should be far from common ones.

**Labels are UI.** Every word on screen is a design decision. Vague labels ("Submit", "OK", "Update") are a friction point.

**States need to be visible.** If a voucher is applied, expired, or pending — the user should know at a glance without reading fine print.

**Don't make users think.** If a user has to pause and wonder what happens next, that pause is a design failure.

---

## Anti-Patterns to Flag

- **Mystery meat navigation** — icon-only buttons with no labels or tooltips
- **Confirmation inflation** — confirming low-stakes actions, habituating users to dismiss dialogs without reading
- **Orphan screens** — pages with no clear next step or back navigation
- **Premature optimization UX** — hiding features "to reduce clutter" that users actually need
- **Ghost actions** — disabled buttons with no explanation of how to enable them
- **Modal overuse** — interrupting a task flow to show information that could be inline
- **Inconsistent terminology** — "Account" in one place, "Participant" in another, "User" in a third
