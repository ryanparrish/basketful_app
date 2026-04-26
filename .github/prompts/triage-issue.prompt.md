---
name: triage-issue
description: Systematically triage a bug or unexpected behaviour in the codebase. Use when something isn't working as expected, you're getting an error you don't understand, or behaviour is inconsistent between environments.
---

# Triage Issue

A structured process for getting from "something is wrong" to "here is the root cause and the fix". Modelled on the scientific method: **observe → question → hypothesise → predict → experiment → analyse → conclude → iterate**. Skips assumptions, follows evidence.

> *"The highly controlled, cautious, and curious aspects of the scientific method are what make it well suited for identifying persistent systematic errors."* — Kevin Dunbar

---

## Workflow

### 1. Observe — Capture the Problem
*Science begins with careful, systematic observation before any explanation is attempted.*

Before touching any code, nail down exactly what is happening:

- [ ] **What is the observed behaviour?** (exact error message, wrong value, nothing happens)
- [ ] **What is the expected behaviour?** (what should have happened)
- [ ] **When did it start?** (always broken, broke after a change, intermittent)
- [ ] **Is it reproducible?** (always, sometimes, only in production)
- [ ] **What environment?** (local dev, staging, prod, which OS/Python/Node version)
- [ ] **What does the user see vs what does the log show?**

If a stack trace or error message is provided, read it completely — the root cause is often not on the last line.

---

### 2. Question — Define the Problem Space
*A well-posed question is half the answer. Scope the inquiry before gathering data.*

Understand how much of the system is affected before diving in:

- [ ] Is this isolated to one endpoint / component / model?
- [ ] Does it affect all users or a subset?
- [ ] Is data corrupted, or just a display/logic issue?
- [ ] Are there related systems that might also be affected?
- [ ] Can the question be stated precisely? e.g. *"Why does `GET /api/vouchers/` return 403 for staff users created after 2024-01-01?"*

**Rule**: Fix the smallest surface area first. Don't refactor while triaging.

---

### 3. Gather Evidence — Characterise the System
*Systematic, careful collection of measurements is what separates debugging from guessing.*

Collect facts — don't hypothesise yet.

#### Backend (Django / Python)
- Read the full stack trace. Note the **innermost frame** — that's where it actually failed.
- Check `manage.py runserver` output and any Celery worker logs.
- Run the failing code path in isolation: `manage.py shell`, a test, or a `print()`.
- Check recent migrations: `manage.py showmigrations` — is everything applied?
- Check model state vs database state: does the schema match the model?

#### Frontend (React / TypeScript)
- Open browser DevTools → Network tab: what did the API actually return?
- Check the Console tab for JS errors.
- Check the request payload — is the frontend sending what it should?
- Is the issue in state management, rendering, or the API call itself?

#### Data
- Does the issue reproduce with a specific record? Check it directly in the DB or Django admin.
- Was the record created before or after a migration/code change?

---

### 4. Hypothesise — Propose an Explanation
*Only after gathering evidence, form a single falsifiable hypothesis. Entertain multiple alternatives to avoid confirmation bias.*

State a clear, testable hypothesis using this pattern:

```
I believe [X] is happening because [Y].
Prediction: if I [change Z], the symptom will [disappear / change in this specific way].
Falsification: if [alternative outcome], my hypothesis is wrong and I need to reconsider.
```

Examples:
- "I believe the 404 is happening because the URL pattern expects `/api/v1/coaches/` but the frontend is calling `/api/coaches/`. Prediction: if I update the frontend base URL, the 404 disappears. Falsification: if I fix the URL and still get 404, the issue is in the router, not the URL."
- "I believe the migration is failing because `0007` references a field removed in `0006`. Prediction: squashing the migrations removes the error. Falsification: if squashing doesn't help, the field reference is elsewhere."

> Use **Occam's Razor**: prefer the simplest explanation that fits all evidence before reaching for complex causes.

If you can't form a clear hypothesis, go back to step 3.

---

### 5. Predict & Experiment — Test the Hypothesis
*A hypothesis is only scientific if it makes a testable prediction. Run the smallest experiment that could falsify it.*

Before applying a fix, design a targeted experiment:

- [ ] Can you reproduce the failure in isolation? (controlled conditions)
- [ ] Can you make it **stop** failing by temporarily reversing the suspected cause?
- [ ] Does the fix make sense without introducing new risk?
- [ ] Is there a prediction you can check *before* writing code? (e.g. query the DB directly, curl the endpoint, check a flag in admin)

For backend: **write a failing test first** — it is the experiment. It proves the bug exists and prevents regression.

> Unexpected results during experimentation are data, not failures. If the bug doesn't reproduce in isolation, that itself is a finding — the issue may be environmental or a timing/ordering problem.

---

### 6. Analyse — Interpret the Results
*Raw results mean nothing without interpretation. Compare what you predicted against what you observed.*

After running the experiment:

- Did the result **confirm** your hypothesis? → proceed to fix.
- Did the result **contradict** your hypothesis? → revise it (return to step 4).
- Did you get an **unexpected result** entirely? → treat it as new observation data (return to step 3).

> Resist confirmation bias: don't explain away contradictory evidence. A result that falsifies your hypothesis is more valuable than one that confirms it — it rules out a wrong path.

---

### 7. Apply the Fix — Intervene in the Causal Mechanism
*The best explanations allow you to predict and intervene. Apply the minimal change that resolves the root cause.*

- Make the **smallest change** that resolves the issue.
- Do not fix unrelated things in the same change.
- If the fix requires a migration, run `makemigrations` + `migrate` and verify.
- If the fix touches serializers or API contracts, check the frontend still works.

---

### 8. Confirm & Iterate — Verify and Communicate
*Science is iterative. Successful results increase confidence but do not prove the hypothesis definitively. New information may require revisiting earlier steps.*

- [ ] The original symptom is gone
- [ ] No new errors appear in logs
- [ ] Related paths still work (smoke test adjacent features)
- [ ] If a test was written, it passes
- [ ] If data was corrupted, it has been corrected
- [ ] Document the root cause so others can build on the finding (see Reporting Format below)

> The cycle is: characterise → hypothesise → test → characterise again. If the fix reveals a deeper issue, restart from step 1 with the new information.

---

## Common Patterns in This Codebase

### Django / DRF
- **404 on valid ID** → check `get_queryset()` filtering — the object may exist but be filtered out by owner/permission scope
- **Field not saving** → check if it's in the serializer's `fields` list and not in `read_only_fields`
- **Migration error** → run `showmigrations` and check for unapplied or conflicting migrations
- **Signal not firing** → check the signal is connected (`@receiver`) and the sender matches exactly
- **Celery task not running** → check the task is registered, the broker is running, and `CELERY_TASK_ALWAYS_EAGER` is set correctly in test config

### React / TypeScript
- **Data not updating after action** → check if `useRefresh()` or `invalidateQueries` is called after mutation
- **Button not appearing** → likely conditional render based on record state — check the `if (!record || ...)` guard
- **API call returns 403** → check the permission class on the ViewSet and whether the test user is in the right group
- **TypeScript error on build but not dev** → strict mode catches things Vite's dev server may not — run `tsc --noEmit` explicitly

### Auth / Permissions
- **Unexpected 401** → httpOnly cookie may have expired; check `access_token` cookie in DevTools → Application tab
- **Staff action denied** → verify the user is in the correct Django group AND `is_staff=True`
- **reCAPTCHA failing in tests** → `RECAPTCHA_TESTING_MODE` must be set in test settings

---

## Reporting Format

When handing off or documenting a triage, use:

```
## Issue Summary

**Symptom**: What the user/system observed
**Root Cause**: What actually caused it
**Affected Scope**: What was broken (endpoint, model, component)
**Fix Applied**: What was changed
**Verified By**: How it was confirmed (test, manual check, log review)
**Regression Risk**: What else could break, if anything
```

---

## Anti-Patterns

- **Fixing symptoms, not causes** — if you suppressed an error without understanding it, it will recur
- **Hypothesis-first debugging** — changing code before gathering evidence wastes time and introduces new bugs
- **Fixing too much** — resolving a bug and refactoring in the same change makes it hard to revert if wrong
- **Not writing a test** — if the bug was subtle enough to slip through, it needs a regression test
- **Assuming the obvious** — "it must be the recent change" is sometimes right, but always verify
