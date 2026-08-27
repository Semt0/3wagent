# open-websearch runtime

This directory pins the Node dependency used as 3wagent's local web-search
backend. The upstream source is not vendored into this repository.

## Install

```bash
cd src/infra/open-websearch
npm ci
```

`python -m src.main` 会自动探测并启动 daemon，并在主程序退出时关闭本次
启动的进程。如果需要独立调试，也可以手动启动：

```bash
cd src/infra/open-websearch
# Safe default: request-only search, localhost daemon on port 3210.
DEFAULT_SEARCH_ENGINE=bing \
ALLOWED_SEARCH_ENGINES=bing,duckduckgo,startpage,baidu,sogou \
SEARCH_MODE=request \
npm run serve
```

In another terminal:

```bash
cd src/infra/open-websearch
npm run status
```

The daemon is expected at `http://127.0.0.1:3210`. It is a local dependency;
do not expose it publicly. If outbound traffic needs a proxy, configure the
daemon explicitly with `USE_PROXY=true` and `PROXY_URL=...`.

Playwright/browser mode is intentionally not installed by default. Add it only
when official sites cannot be retrieved in request mode, and use a dedicated
anonymous browser profile rather than a personal logged-in browser.
