# Poke Holes

A structured adversarial review process. Takes a plan, feature spec, or design document and systematically attacks it from every angle before a single line of code is written.

> *"The goal of adversarial review is not to kill ideas — it is to find the cracks while they are still cheap to fix."*

This is not a build prompt. It is a **stress test**.

---

## Workflow

### 1. Read the Plan

Before poking any holes, understand what the plan is actually trying to do:

- [ ] What problem is it solving?
- [ ] Who is it for?
- [ ] What does success look like?
- [ ] What assumptions are baked in?

Do not begin critique until you can state the plan's goal in one sentence. If you can't, that itself is a hole.

---

### 2. Spawn Parallel Adversarial Agents


```
Prompt template for each agent:

You are a critical reviewer attacking a software plan from a specific angle.
Your job is NOT to be constructive — it is to find every flaw, edge case,
assumption, and failure mode from your assigned perspective.

Plan to review:
[paste full plan content]

Your lens: [assign one lens per agent — see below]

For each issue you find, output it in this format:

### [SEVERITY] Issue Title

**Lens**: [your assigned lens]
**What could go wrong**: Specific description of the failure mode or gap.
**Who is harmed**: Which users, stakeholders, or systems are affected.
**Likelihood**: Low / Medium / High
**Suggested question to ask**: A single question that, if answered, would resolve or mitigate this issue.
```

**Agent lenses:**

- **Agent 1 — 🧓 Tech Literacy**: *"What happens when the user has never used software like this before?"* Attack assumptions about digital fluency. Consider: elderly users, first-time smartphone owners, users who have never shopped online, users who don't know what a "button" vs a "link" looks like, users who will mis-tap, mis-click, or not understand confirmation dialogs.

- **Agent 2 — ♿ Disability & Accessibility**: *"What breaks for users who cannot use the product the way it was designed?"* Attack assumptions about ability. Consider: screen reader users (NVDA, VoiceOver, JAWS), keyboard-only navigation, motor impairments (tremor, limited hand use, switch access), cognitive disabilities (dyslexia, ADHD, memory impairments), low vision users who zoom to 400%, users with colour blindness (all three types), users who rely on captions or transcripts.

- **Agent 3 — 🌐 Language & Literacy**: *"What breaks for users who don't read English well, or at all?"* Attack assumptions about language. Consider: non-English speakers, low-literacy users, users relying on machine translation, icons that carry cultural meaning (e.g. a "mailbox" icon means nothing outside North America), error messages that use jargon, date/number formats that differ by locale, right-to-left languages.

- **Agent 4 — 📱 Device & Connectivity**: *"What breaks in the real physical world?"* Attack assumptions about hardware and environment. Consider: small screens (3.5-inch phones), slow or intermittent connections (2G, library WiFi, rural areas), no WiFi (data-only), old browsers, screen glare in bright sunlight, users who share a device with family members, users who are interrupted mid-flow, sessions that time out.

- **Agent 5 — 🔐 Trust & Safety**: *"What could be abused, misunderstood, or exploited?"* Attack assumptions about intent and safety. Consider: what happens if staff make an error on behalf of a participant? Who can undo it? Are there privacy risks (staff seeing participant data they shouldn't)? Could a frustrated or malicious staff member abuse the feature? Are there data retention or audit concerns? What does the participant see — do they know an order was placed on their behalf? Is there consent?

- **Agent 6 — 💥 Edge Cases & Failure Modes**: *"What happens when things go wrong?"* Attack the happy path. Consider: network failure mid-submission, duplicate submissions (double-click, browser back), empty states (no products, no participants, zero balance), participants with no account balance record, order window closed mid-session, server errors, partial failures (order created but items not saved), stale data (product removed while in cart), concurrent sessions (two staff members ordering for the same participant simultaneously).

---

### 3. Collate & Prioritise

After all six agents complete, collate their findings into a single prioritised list using this table:

| # | Severity | Lens | Issue | Likelihood | Effort to Fix |
|---|----------|------|-------|------------|---------------|
| 1 | 🔴 Critical | | | | |
| 2 | 🟠 High | | | | |
| … | | | | | |

**Severity scale:**
- 🔴 **Critical** — Blocks a user entirely or causes data harm
- 🟠 **High** — Significantly degrades experience for a meaningful user group
- 🟡 **Medium** — Noticeable problem, workaround exists
- 🔵 **Low** — Polish issue, edge case with low likelihood
- ⚪ **Info** — Observation, no immediate action needed

---

### 4. Verdict

End with a plain-language verdict in three parts:

**Biggest unresolved risk**: The single issue that, if not addressed, most threatens the plan's success.

**Quick wins**: Issues that are cheap to fix before building (a label change, a confirmation dialog, an error state).

**Questions that need answers before building**: Decisions embedded in the plan that haven't been made yet but will force a rewrite if answered wrong later.

---

## Ground Rules

- **No praise.** This prompt exists to find problems, not to validate the plan.
- **Be specific.** "This could be confusing" is not a finding. "A user with low vision who zooms to 400% will not be able to see the sticky cart panel because it overflows the viewport and there is no scroll indicator" is a finding.
- **All six lenses must produce findings.** If an agent has nothing to say, it hasn't looked hard enough.
- **Severity must be justified.** Don't call something Critical unless you can explain exactly who is blocked and how.
- **Do not suggest rewrites.** Poke holes only. Leave the fixes to the builder — or to a follow-up prompt.

---

## Usage

Attach or paste the plan `.md` file and run this prompt. The agent will:
1. Summarise the plan in one sentence
2. Spawn six parallel adversarial agents
3. Return a collated, prioritised findings tableUse the Task tool to run **six adversarial agents simultaneously**, each attacking the plan from a different lens. Each agent should read the full plan before critiquing.

4. End with a verdict

The output of this prompt is the input to a **revision pass** — not a blocker. The plan is better for being attacked.
