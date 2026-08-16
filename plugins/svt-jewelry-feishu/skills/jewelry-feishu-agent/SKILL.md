---
name: jewelry-feishu-agent
description: Use when a user explicitly asks to publish completed JewelryDesignCodex reports or media to Feishu/Lark and the optional lark-cli is separately installed and authorized.
---

# Jewelry Feishu Agent

## External dependency

This optional plugin does not bundle Feishu credentials, an app, a bot, or `lark-cli`. Before the
first live operation:

1. Confirm `lark-cli` is installed from its official distribution.
2. Run `lark-cli doctor --offline` and a redacted authorization status check.
3. If authorization is missing, pause and use `lark-cli auth login --no-wait --json`; present the
   returned authorization link without parsing it, then complete the device-code flow after the
   user authorizes.

Never copy tokens, app secrets, cookies, or unrelated Feishu identifiers into the plugin or task.

## Workflow

1. Trigger only when the user explicitly requests Feishu/Lark delivery.
2. Read `references/module-workflow.md` before a live publish.
3. Identify the completed task result, local media, target document, and acting identity.
4. Build fixed `lark-cli` argument arrays. Do not concatenate untrusted shell strings.
5. Use dry-run or mocks for development tests. Perform a real write only for an authorized delivery
   request.
6. Read the created document back when the CLI supports it, then return the document URL and state
   whether read-back verification succeeded.

## Boundaries

- Do not ask designers for raw JSON, scopes, tokens, or app secrets.
- Do not create a new app, robot, chat, or organization configuration unless explicitly requested.
- Redact access tokens, refresh tokens, app secrets, open IDs, and full scope dumps.
- A failed auth check or provider write is a blocker, not a completed delivery.

## Verification

- The source task assets exist locally.
- The target and identity are explicit.
- No secrets appear in logs or user-facing output.
- The returned URL points to the delivered document and read-back status is reported accurately.
