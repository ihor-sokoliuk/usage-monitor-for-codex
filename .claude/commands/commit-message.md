Analyze the staged changes by running `git diff --cached` and the current branch name by running `git branch --show-current`, then generate a commit message according to the following rules:

Follow **Conventional Commits** format with a descriptive body:

```
<type>: <short description>

<body explaining WHY this change was made>
```

# Types

| Type | Use for |
|------|---------|
| feat | New features |
| fix | Bug fixes |
| docs | Documentation changes |
| refactor | Code refactoring (no behavior change) |
| test | Adding or updating tests |
| chore | Maintenance tasks |

# Structure

**Subject line (required):**
- Lowercase, no period at end
- Maximum ~72 characters
- Imperative mood ("add feature" not "added feature")

**Body (optional):**
- Blank line after subject
- No hard line breaks - write as flowing prose, separate paragraphs with a blank line
- Explain **WHY** the change was made, not just WHAT changed

**Footer (optional):**
- `BREAKING CHANGE: description` for breaking changes

# Rules

- Base message ONLY on the actual code changes in the diff
- Never invent issue numbers, ticket references, or external links
- Never include code snippets or file contents in the message
- Describe the change's purpose and impact, not implementation details

# Example

```
fix: preserve dynamic quota labels after account changes

Keep provider-named windows visible when a new account reports a different quota set.
```

Generate text only. Do not stage, commit, push, or publish. Git commit author name and email are public metadata; recommend a GitHub `noreply` email when privacy is desired.
