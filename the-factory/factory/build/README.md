# Factory Build

OpenHands + Claude Code + Ponytail 5 is the build layer.

## What Build Does

1. Receives a planned feature fleet from `/orchestrate`
2. OpenHands Automation Server executes each task
3. Claude Code performs the actual code changes
4. Ponytail 5 enforces lean code at generation time

## Ponytail 5 Benchmarks

- 53% less code generated
- 41% faster implementation
- 26% cheaper (fewer tokens)
- 98% of risky logic ships with a test

## OpenHands Integration (TODO)

- [ ] Install OpenHands locally (`pip install openhands`)
- [ ] Configure Claude Code as OpenHands backend
- [ ] Wire Automation Server to factory intake queue
- [ ] Set up GitHub integration for automatic PR creation

## pstack Build Commands

```
/orchestrate   — plan multi-day multi-PR feature fleet
/swarm         — spawn parallel workers for independent tasks  
/autopilot-full — PRs planned → built → merged autonomously
```

## Plugin Install

```bash
# Run inside Claude Code when opening the-factory:
/add-plugin pstack
/plugin marketplace add DietrichGebert/ponytail
```
