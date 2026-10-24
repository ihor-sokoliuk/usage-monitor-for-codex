## Summary

<!-- What changed and why? Link related issues or discussions. -->

## Validation

- [ ] Read [AGENTS.md](../blob/main/AGENTS.md) and preserved the fixed local Codex app-server boundary
- [ ] Full native Windows suite: `python -m unittest discover -s tests`
- [ ] Applicable Linux tests; describe headless, virtual-display, and real-desktop coverage separately
- [ ] Build/frozen smoke when packaging, dependencies, or runtime integration changed
- [ ] Reviewed publishable files for private paths, emails, credentials, settings, logs, and raw probes

## User-visible changes

<!-- Update affected documentation and the fork Unreleased changelog. Skip irrelevant items. -->

- [ ] README and privacy claims match the final behavior
- [ ] Configuration/event documentation and locale strings match the implementation
- [ ] Changelog describes user-visible features, fixes, or behavior changes

## Notes for reviewers

<!-- Mention risks, lifecycle/concurrency implications, intentional dormant upstream scaffolding, and verification limits. Source changes do not authorize merge, release, deployment, or restart. -->
