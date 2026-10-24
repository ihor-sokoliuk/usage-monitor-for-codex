# Automatic update checks

There are two separate version surfaces:

- **Codex CLI updates** use only the fixed official `codex update` command. They run at startup and at `codex_cli_update_interval`, when enabled. Provider operations are serialized and the child stopped first. A notification appears only when the installed version changes. Failure is logged without raw subprocess output and retried only after the configured interval; there is no elevation or fallback installer. See [configuration](configuration.md#codex-cli-updates).
- **Monitor releases** are published on this fork's [release page](https://github.com/ihor-sokoliuk/usage-monitor-for-codex/releases). The monitor does not download or install its own releases. Check that page manually, or configure your own event command to open it.

A configured event command runs with your privileges and may perform network or filesystem operations. This opt-in surface is separate from the app-server provider boundary. The application does not supply an automatic monitor release scraper or a download URL generator.
