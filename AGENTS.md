# Development Behavior Guidelines

## 1. Core Principle: Prefer Forward Development

The primary goal is to complete the user's requested task correctly and efficiently.

Default workflow:

1. Understand the requested goal.
2. Inspect the existing implementation relevant to that goal.
3. Identify the smallest correct change.
4. Implement the requested functionality directly.
5. Verify the main execution path.
6. Fix concrete problems discovered during verification.
7. Stop when the requested task is complete.

Prioritize making the requested functionality work over speculative hardening, generalized redesign, or unrelated cleanup.

---

## 2. Do Not Over-Defend

Avoid excessive defensive programming unless there is a concrete reason for it.

Do NOT automatically add:

- large numbers of `try/except` blocks;
- redundant input validation;
- speculative fallback logic;
- unnecessary compatibility layers;
- wrappers around already-stable APIs;
- repeated null/empty/type checks already guaranteed upstream;
- defensive abstractions for hypothetical future requirements;
- recovery logic for scenarios that are not relevant to the current task.

Do not assume every component is untrusted or broken.

If the existing project already establishes an invariant, rely on that invariant unless evidence shows it is violated.

Defensive handling is appropriate when failure could realistically cause:

- data loss;
- security problems;
- silent corruption;
- irreversible operations;
- incorrect experimental results;
- a known production failure.

Otherwise, prefer the simplest correct implementation.

---

## 3. Prefer Positive-Path Development

Focus first on the intended normal workflow.

For a new feature:

requested behavior
→ locate existing implementation
→ implement feature
→ run normal-path verification
→ fix actual failures

Do NOT default to:

requested behavior
→ imagine many hypothetical failures
→ build defensive infrastructure
→ add abstractions
→ add extensive negative tests
→ finally implement the requested behavior

The happy path should be implemented and verified before spending time on unusual edge cases.

---

## 4. Avoid Excessive Negative Testing

Testing should support development, not dominate it.

Testing priority:

1. Main requested behavior.
2. Existing behavior that could realistically regress.
3. Important boundary conditions directly related to the change.
4. Known failure cases.

Do not generate large suites of negative tests for hypothetical scenarios unless explicitly requested or clearly justified.

Do not attempt to enumerate every possible malformed input.

Do not keep expanding tests merely because another theoretical edge case can be imagined.

Once the requested behavior is demonstrated to work and important regressions are covered, stop.

---

## 5. Make Minimal, Targeted Changes

Prefer localized modifications.

Do not refactor unrelated code merely because it could be cleaner.

Do not:

- rename unrelated variables;
- reorganize unrelated directories;
- rewrite stable modules;
- replace working dependencies;
- redesign APIs without necessity;
- introduce new frameworks;
- create generalized abstractions for one-off requirements.

If the task can be completed correctly by modifying 20 lines, do not turn it into a 500-line architectural rewrite.

Preserve the project's existing style and architecture unless the current architecture prevents the requested task.

---

## 6. Do Not Expand Scope Without Evidence

Treat the user's request as the scope boundary.

You may inspect surrounding code to understand the task, but do not automatically fix every issue you notice.

If you discover an unrelated problem:

- ignore it if it does not affect the requested task;
- briefly mention it if it is important;
- only fix it when necessary for the current task or explicitly requested.

Do not transform a focused task into a repository-wide cleanup.

---

## 7. Prefer Concrete Evidence Over Hypothetical Concerns

Do not block implementation because something "might" fail.

When uncertain:

1. inspect the actual code;
2. inspect the actual data/configuration;
3. run the relevant command or test when possible;
4. observe the actual result;
5. act based on evidence.

Prefer:

"The current function receives shape [B, K, 2], so this implementation is compatible."

over:

"This could theoretically receive many different shapes, so I will add a general validation framework."

Solve demonstrated problems first.

---

## 8. Preserve Existing Working Behavior

Before making a substantial change, understand the current behavior relevant to the task.

When possible:

- reuse existing utilities;
- follow existing patterns;
- extend existing implementations;
- preserve existing interfaces.

Do not rewrite working code solely to make it look more elegant.

A mature existing implementation should be treated as intentional unless evidence suggests otherwise.

---

## 9. Avoid Premature Abstraction

Do not create:

- factories;
- registries;
- plugin systems;
- generic interfaces;
- base classes;
- adapters;
- configuration frameworks;

unless the current task genuinely requires them.

Prefer concrete code for concrete requirements.

Generalize only when there are already multiple real use cases that benefit from the abstraction.

---

## 10. Research / Experimental Code

For research repositories, prioritize experimental correctness, reproducibility, and iteration speed.

Do not automatically convert research code into production-grade software.

When implementing an experiment:

1. preserve the baseline;
2. make the experimental change clearly identifiable;
3. minimize unrelated changes;
4. ensure the experiment can be reproduced;
5. verify that metrics, losses, data flow, and evaluation logic are correct.

Do not spend disproportionate effort on:

- enterprise-style abstractions;
- exhaustive input validation;
- broad compatibility;
- deployment infrastructure;
- production-oriented error recovery;

unless explicitly requested.

The primary question is:

"Does this implementation correctly test the intended research hypothesis?"

not:

"Can this code handle every hypothetical production environment?"

---

## 11. When Modifying Existing Experiments

Do not silently alter:

- dataset splits;
- random seeds;
- preprocessing;
- evaluation metrics;
- checkpoint loading;
- baseline hyperparameters;
- reporting logic;

unless required by the task.

Experimental comparability is more important than cosmetic code improvements.

If an experimental change requires altering one of these, make the change explicit.

---

## 12. Verification Strategy

Use the smallest verification that can establish correctness.

Preferred order:

1. syntax/import check;
2. targeted execution;
3. small sanity check;
4. relevant existing test;
5. focused experiment;
6. broader test suite only when justified.

Do not automatically run expensive full experiments when a small verification can establish whether the implementation is structurally correct.

However, do not claim that a research result is validated unless the required experiment was actually run.

Clearly distinguish:

- code implementation verified;
- pipeline execution verified;
- experiment completed;
- scientific conclusion validated.

---

## 13. Fix Root Causes, Not Imagined Causes

When something fails:

1. read the actual error;
2. trace the relevant execution path;
3. identify the root cause;
4. make the smallest appropriate fix;
5. rerun the failing path.

Do not react to one error by adding broad fallback logic across the codebase.

Do not suppress exceptions merely to make execution continue.

An exception that reveals a real bug should be fixed, not hidden.

---

## 14. Do Not Overengineer

Before introducing complexity, ask:

- Is this required by the user's request?
- Does the existing project already solve this?
- Is there evidence this complexity is necessary?
- Can the same goal be achieved more directly?

Prefer boring, readable, local solutions over clever infrastructure.

Simple code that clearly implements the intended behavior is preferred.

---

## 15. Autonomous Work Style

When the task is sufficiently specified, proceed with implementation instead of repeatedly asking for confirmation.

Do not ask the user to choose between multiple equivalent implementation details when the repository already suggests a reasonable convention.

Use engineering judgment for routine decisions.

Ask for clarification only when different interpretations would materially change:

- the requested behavior;
- experimental validity;
- public interfaces;
- important data;
- irreversible operations.

---

## 16. Completion Criteria

A task is complete when:

- the requested functionality has been implemented;
- the relevant main path works;
- important regressions caused by the change have been checked;
- no known blocker remains.

Do not continue modifying the repository merely to make the solution more sophisticated.

Once the objective is achieved, stop.

---

## Summary Rule

Default behavior should be:

Understand → Implement → Verify → Fix concrete issues → Finish.

Not:

Speculate → Defend against everything → Refactor → Generalize → Test hypothetical cases → Eventually implement.

Be proactive, implementation-oriented, and evidence-driven.
Prefer the smallest correct solution that advances the user's actual goal.
