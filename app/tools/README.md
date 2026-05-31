# Application Tool Adapters

This package contains adapters used by the application runtime.

The core policy workflow should call stable Python interfaces here instead of directly binding itself to a specific external MCP server, browser tool or prompt helper.

Current layout:

```text
mcp/
  MCP client adapters used by the app.

skills/
  Runtime skill registries and LangChain prompt templates used by the app.
```
