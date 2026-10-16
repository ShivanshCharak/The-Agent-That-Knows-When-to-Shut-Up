# VS Code extension implementation notes

- `extension.js` is a plain JavaScript VS Code extension with no npm runtime dependencies.
- Send only file-backed active documents. The Python bridge is bound to `127.0.0.1`.
- Event sources are active-editor changes (`file_open`), saves (`edit` or `test_fail`), and active-document diagnostic changes (`test_fail`/`test_pass`).
- `file_open` events are retained in context but skipped by deterministic rules before Decider calls.
- Keep the product as an interruption gate. Do not add inline completions or automatic edits without a separate product decision.
- The bridge always uses the configured Strands Decider HTTP endpoint. Bedrock generation remains opt-in through backend environment configuration.
