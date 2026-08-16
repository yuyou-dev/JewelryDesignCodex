# Feishu Delivery Operations

Use this reference only after `$jewelry-feishu-agent` triggers.

## Preflight

- Verify `lark-cli` availability and inspect its current help.
- Run `lark-cli doctor --offline`.
- Check authorization and required scope without exposing tokens or full identity values.
- Confirm the target document or folder, acting identity, local media count, and upload timeout.

If authorization is missing, start the CLI's split login flow. Treat the returned authorization URL
and device code as opaque values; never parse credentials from them.

## Safe execution

- Build fixed argument arrays and pass local task files explicitly.
- Do not generate commands by concatenating user input.
- Keep provider responses inside the active task workspace.
- Use a media-aware timeout for documents with images or attachments.
- Read back the resulting document and compare its title, content summary, and media count.

## Result contract

Return the document URL, a redacted target summary, uploaded media count, and read-back status. On
failure, state the missing authorization, scope, target, or provider result without printing raw
secrets.
