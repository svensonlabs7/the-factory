---
name: ux-laws
description: Review or plan a user-facing change against 20 UX laws and end with a PASS or VIOLATIONS verdict. Use before and after building any UI, form, dashboard, page, or user-facing flow, and when asked for a UX review.
---

# UX Laws

Apply these laws to anything a person will see or operate. Use it twice: before building, to plan the shortest clear path, and after building, to review what was built.
The laws and their order follow Adam Hayes's post "The UX laws in my CLAUDE.md" (https://adamhayes.xyz/blog/the-ux-laws-in-my-claude-md). The wording here is our own.

## Before building

1. Name the user's primary goal in one sentence.
2. Sketch the shortest clear path to it, and make the next action obvious at every step.
3. Remove anything that distracts from that path.
4. Plan immediate feedback, error prevention, saved work, and a clear completion state.

## The 20 laws

For each law, ask the check question about the files under review.

| # | Law | Check |
|---|-----|-------|
| 1 | Hick's Law: choices | Does each screen have one purpose, with low-priority options cut or hidden? Are hard decisions split into steps? |
| 2 | Fitts's Law: target size | Are controls large enough, spaced apart, and not icon-only, with a generous clickable area on important ones? |
| 3 | Jakob's Law: convention | Does it work like products people already know? Are navigation and settings where users look? Is any new pattern justified? |
| 4 | Proximity | Do related items sit together and unrelated groups sit apart? Is spacing doing the grouping, not borders? |
| 5 | Miller's Law: memory | Is long content chunked, are long forms stepped, and is nothing carried from one screen to the next in the user's head? |
| 6 | Doherty Threshold: speed | Does every action get feedback in about 400 ms, with loading and success states? Can the user always tell something registered? |
| 7 | Von Restorff: distinctiveness | Is there one dominant action per section, with secondary actions visibly quieter? |
| 8 | Fitts's Law: distance | Do actions sit next to the content they affect, and submit near the last input? Is cursor and eye travel short? |
| 9 | Serial Position | Does the key information come first and the final action or takeaway come last? Are lists ordered by importance? |
| 10 | Peak-End Rule | Does the flow end on a clear completion state that confirms what happened and what comes next, never a blank or ambiguous screen? |
| 11 | Zeigarnik Effect | Are done and remaining steps visible? Is progress saved, and is an interrupted task easy to resume? |
| 12 | Prägnanz: simplicity | Is the structure simple, the hierarchy clear, and decoration removed, so it makes sense at a glance? |
| 13 | Hick's Law: defaults | Is the safe, common option preselected and existing context reused? Is every default easy to change and free of surprise commitments? |
| 14 | Postel's Law: input | Are reasonable input formats accepted, requirements stated before submit, unavailable actions disabled, and risky ones warned about? |
| 15 | Postel's Law: errors | Is user work kept after an error, the problem explained in plain words with a fix, and undo, retry or cancel offered where suitable? |
| 16 | Similarity | Do similar things look and behave alike, different actions look different, and existing components get reused before new ones are built? |
| 17 | Uniform Connectedness | Are controls visually tied to what they affect, with unrelated items kept apart, and links drawn only on purpose? |
| 18 | Parkinson's Law | Are steps and confirmations kept to the minimum, known information prefilled, and shortcuts offered for repeat actions? |
| 19 | Tesler's Law | Is unavoidable complexity absorbed by the system, essential controls shown first, and advanced options revealed only when relevant? |
| 20 | Goal-Gradient Effect | Do multi-step flows show progress, visible milestones, completed work, and specific remaining steps? |

## When laws disagree

Put clarity, accessibility, user control and task completion first. Apply the laws on purpose, not mechanically. A law that does not fit the screen under review is not a violation.

## How to review

1. Read the UI files in the change: markup, styles, components and templates.
2. For each law that applies, decide whether the change breaks it in a way a real user would hit.
3. A **violation** needs a specific place (`file:line`), the law, what goes wrong for the user, and the smallest fix. Cosmetic taste and speculative cases are advisory notes, not violations.
4. Do not report laws that were met. Report the violations, then the advisory notes.

## Verdict Format

End every review with one of two verdicts, on its own last line, with nothing after it:

- `PASS` — no violations. Advisory notes may remain above it.
- `VIOLATIONS` — one or more violations. List each one above the verdict, as `<law> — <file:line> — <what goes wrong> — <fix>`.

Do not use partial approvals or conditional verdicts. The verdict is binary.
