# Contributing

Thank you for helping. Humans and coding agents are welcome; the human who opens a pull request is responsible for it.

## The best first contribution: your language

The rules work in any language, but the labels and examples need native speakers.
Open an issue with the "Add or fix my language" form, or send a pull request that adds your language to
`skills/ihav-asd-ste100/SKILL.md` (only if it stays small) and an example reply to `examples/`.

## Changing a rule

1. Start from `skills/ihav-asd-ste100/SKILL.md`. It is the only source of truth.
2. Show a real reply before and after the change.
3. Describe a prompt that shows the change; the maintainers keep the eval suite locally and run it before a release.
4. Keep `SKILL.md` under 7,100 bytes, because the hook injects it into every session.

## Hard limits

- Do not add ASD-STE100 specification text or its dictionary. Write principles in your own words.
- Do not make the hooks block a session or a prompt. They must exit 0 and stay silent on any failure.
- Do not add network calls, telemetry or paid model calls to the hooks or the checker.

## Checks

```bash
python3 -m unittest discover -s tests -v
claude plugin validate --strict .
```

`claude plugin eval .` calls paid models. Say in the pull request if you ran it, with the model, runs and cost.
