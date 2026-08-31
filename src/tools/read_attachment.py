"""AttachmentReadTool: on-demand reading of parsed attachments.

Large attachments are not inlined into the model context; sub-agents use this
tool to read specific slices by locator or to search by keyword. Every
returned slice carries its locator so conclusions can cite the exact page or
cell range.

Supported locator forms:
    pdf:p12            single PDF page
    pdf:p10-p15        PDF page range
    xlsx:Sheet1        one workbook sheet (all its chunks)
    xlsx:Sheet1!A1:H30 sheet + row range (column part is advisory)
    csv:rows10-30      CSV row range
    docx:c2 / text:c1  chunk index for DOCX / plain text
"""

import re

from qwen_agent.tools.base import BaseTool, register_tool

from src.attachments.storage import load_document, session_document_ids
from src.config.attachments import ATTACHMENT_SETTINGS
from src.config.runtime import get_run_id
from src.tools.common import parse_tool_params

# Per-agent read budget, same reasoning as SEARCH_BUDGET_PER_AGENT in
# web_search.py: each agent holds its own tool instance, the counter resets
# when the run_id changes. Without it, a model that hallucinates a
# document_id (e.g. the hex hash in a user-supplied PDF URL) retries id
# variants until the framework LLM-call cap kills the whole step.
READ_BUDGET_PER_AGENT = 12


@register_tool('AttachmentReadTool')
class AttachmentReadTool(BaseTool):
    name = 'AttachmentReadTool'
    description = (
        'Read slices of a previously uploaded attachment. '
        'Use document_id from the <uploaded_document> block. Provide either '
        'a locator (e.g. "pdf:p10-p15", "xlsx:Sheet1!A1:H30") or a query '
        'keyword to search for. Returned content always includes locators; '
        'cite them as [filename, locator] in conclusions.')
    parameters = {
        'type': 'object',
        'properties': {
            'document_id': {
                'description': 'Document id from the <uploaded_document> block',
                'type': 'string',
            },
            'locator': {
                'description': 'Optional locator, e.g. "pdf:p10-p15" or "xlsx:Sheet1!A1:H30"',
                'type': 'string',
            },
            'query': {
                'description': 'Optional keyword to search inside the document',
                'type': 'string',
            },
            'max_chars': {
                'description': 'Maximum characters to return (default 20000)',
                'type': 'integer',
            },
        },
        'required': ['document_id'],
    }

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self._budget_run_id: str | None = None
        self._read_count = 0
        self._seen_calls: set = set()
        self._missing_ids: set = set()

    def call(self, params: str, **kwargs) -> str:
        try:
            par = parse_tool_params(params)
        except Exception:
            return ('error: invalid arguments. Use a JSON object like '
                    '{"document_id": "abc123", "locator": "pdf:p10-p15"}')
        document_id = str(par.get('document_id') or '').strip()
        if not document_id:
            return 'error: missing required parameter "document_id"'
        try:
            max_chars = int(par.get('max_chars') or 20000)
        except (TypeError, ValueError):
            max_chars = 20000
        locator = str(par.get('locator') or '').strip() or None
        query = str(par.get('query') or '').strip() or None

        # URL/path passed as document_id: a user-supplied link is a web
        # resource, not an uploaded attachment. Redirect instead of failing
        # blind; this is the most common hallucination pattern.
        if '://' in document_id or '/' in document_id or document_id.lower().endswith('.pdf'):
            return (f'error: "{document_id}" is a URL or file name, not a document_id. '
                    'A document_id comes ONLY from an <uploaded_document> block created when the '
                    'user uploads a file. If the user gave you a web/PDF link, fetch it with '
                    'WebFetchTool instead. Do NOT retry AttachmentReadTool with ids derived from '
                    'a URL.')

        # Cheap guards first: they do not consume the read budget.
        call_key = (document_id, locator, query)
        if call_key in self._seen_calls:
            return ('error: you already made this exact AttachmentReadTool call and the result '
                    'is in the conversation above. Do NOT repeat it. If you have enough '
                    'information, STOP all tool calls now and write your final answer as plain '
                    'Markdown text (no tool call).')
        self._seen_calls.add(call_key)

        if document_id in self._missing_ids:
            return (f'error: document_id "{document_id}" already failed once in this run. '
                    'Do NOT retry it and do NOT guess variants of it. '
                    + self._available_ids_hint())

        run_id = get_run_id()
        if run_id != self._budget_run_id:
            self._budget_run_id = run_id
            self._read_count = 0
        if self._read_count >= READ_BUDGET_PER_AGENT:
            return ('error: your attachment read budget is exhausted. STOP reading attachments: '
                    'do NOT retry and do NOT guess other document_ids. Proceed with the content '
                    'already retrieved. If you have enough information, STOP all tool calls now '
                    'and write your final answer as plain Markdown text (no tool call).')
        self._read_count += 1

        try:
            manifest, chunks = load_document(document_id, ATTACHMENT_SETTINGS)
        except FileNotFoundError:
            self._missing_ids.add(document_id)
            return (f'error: document not found: {document_id}. '
                    + self._available_ids_hint())

        if locator:
            selected = _select_by_locator(chunks, locator)
            if not selected:
                return (f'error: no chunks match locator "{locator}". '
                        f'Available kinds: {_locator_sample(chunks)}')
        elif query:
            selected = [c for c in chunks if query.lower() in c.get('text', '').lower()]
            if not selected:
                return f'error: no chunks contain "{query}".'
        else:
            selected = chunks

        filename = manifest.get('filename', document_id)
        return _render(filename, selected, max_chars)

    @staticmethod
    def _available_ids_hint() -> str:
        ids = session_document_ids()
        if ids:
            return ('The only document_ids uploaded in this session are: '
                    + ', '.join(ids)
                    + '. Do NOT guess any other id.')
        return ('No attachment has been uploaded in this session (there is no '
                '<uploaded_document> block at all). If the user supplied a URL, it is a web '
                'resource: use WebFetchTool on it instead. Do NOT retry AttachmentReadTool.')


def _select_by_locator(chunks: list, locator: str) -> list:
    m = re.fullmatch(r'pdf:p(\d+)(?:-p?(\d+))?', locator)
    if m:
        lo = int(m.group(1))
        hi = int(m.group(2) or m.group(1))
        return [c for c in chunks
                if c.get('page') is not None and lo <= c['page'] <= hi]

    m = re.fullmatch(r'csv:rows(\d+)-(\d+)', locator)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return [c for c in chunks
                if c.get('metadata', {}).get('row_start') is not None
                and c['metadata']['row_start'] <= hi
                and c['metadata'].get('row_end', c['metadata']['row_start']) >= lo
                and c['locator'].startswith('csv:')]

    m = re.fullmatch(r'xlsx:([^!]+?)(?:!(?:rows)?[A-Z]*(\d+)(?:[:-][A-Z]*(\d+))?)?', locator)
    if m:
        sheet = m.group(1)
        selected = [c for c in chunks if c.get('sheet') == sheet]
        if m.group(2):
            lo = int(m.group(2))
            hi = int(m.group(3) or m.group(2))
            selected = [
                c for c in selected
                if c['metadata'].get('row_start', 0) <= hi
                and c['metadata'].get('row_end', 0) >= lo
            ]
        return selected

    m = re.fullmatch(r'(docx|text):c(\d+)', locator)
    if m:
        prefix, idx = m.group(1), int(m.group(2))
        return [c for c in chunks if c.get('locator') == f'{prefix}:c{idx}']

    # Fall back to exact locator match.
    return [c for c in chunks if c.get('locator') == locator]


def _locator_sample(chunks: list, limit: int = 20) -> str:
    return ', '.join(c.get('locator', '?') for c in chunks[:limit])


def _render(filename: str, chunks: list, max_chars: int) -> str:
    parts = []
    used = 0
    for chunk in chunks:
        block = f'\n[{filename}, {chunk["locator"]}]\n{chunk.get("text", "")}\n'
        if used + len(block) > max_chars:
            parts.append('\n... (truncated; narrow the locator or raise max_chars)\n')
            break
        parts.append(block)
        used += len(block)
    return ''.join(parts) or '(empty selection)'
