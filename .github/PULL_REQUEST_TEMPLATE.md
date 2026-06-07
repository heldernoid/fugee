## Summary

<!-- What does this PR do? One sentence. -->

## Tasks completed

<!-- List the PLAN.md task IDs this PR closes. -->

- [ ] T### — description
- [ ] T### — description

## Success criteria verified

<!-- For each SC in this phase, state PASS/FAIL and the evidence. -->

| SC | Status | Evidence (command + output) |
|----|--------|-----------------------------|
| SC-### | ✅ PASS | `pytest tests/... -v` — 3 passed |
| SC-### | ✅ PASS | Visual check against mockup.html #phase-N |

## Design check

- [ ] Colors match `DESIGN.md` tokens (no raw hex values invented)
- [ ] Checked against `mockup.html` for the phase(s) touched
- [ ] One primary (amber) action per screen
- [ ] Touch targets ≥ 44px (checked at 390px viewport)

## Test evidence

<!-- Paste the terminal output of the test run. -->

```
$ pytest tests/... -v
...
N passed in Xs
```

## Notes for developer sign-off

<!-- Anything the developer should know before approving. -->

---

*Built with [Codex](https://openai.com/codex)*
*`Co-authored-by: Codex <noreply@openai.com>`*
