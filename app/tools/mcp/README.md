# MCP Client Adapters

This directory is for app-side MCP integration code.

Use it for:

- Calling external OCR or document parsing MCP tools
- Calling browser or search MCP tools for source discovery
- Wrapping MCP responses into internal schemas
- Keeping MCP-specific failures away from the core workflow

Do not put self-hosted MCP server implementations here. The MVP does not keep repository-level MCP server directories; add one later only after there is a concrete external tool boundary.
