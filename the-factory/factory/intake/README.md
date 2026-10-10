# Factory Intake

Grok Bot is the intake layer for the-factory.

## What Intake Does

1. Receives feature requests via Grok Bot webhook
2. Parses and structures them into a standard feature brief
3. Queues them for `/orchestrate` (pstack planning)

## Feature Brief Format

```json
{
  "id": "feat-YYYYMMDD-NNN",
  "title": "Short feature name",
  "submitted_by": "user or bot",
  "submitted_at": "ISO timestamp",
  "description": "What and why",
  "acceptance_criteria": [],
  "priority": "P0 | P1 | P2",
  "labels": []
}
```

## Setup (TODO)

- [ ] Configure Grok Bot webhook endpoint
- [ ] Set up pstack `/make-bot-ui` for the intake UI
- [ ] Wire webhook → feature brief parser
- [ ] Feature brief → /orchestrate handoff

## Reference

pstack `/make-bot-ui` — builds the Grok Bot webhook UI.
Run `/make-bot-ui` inside Claude Code to scaffold the intake endpoint.
