# document-parse

Parse PDF, Word, image, spreadsheet or presentation inputs into structured text.

## When to use

- The user attaches PDF, Word, image or other documents.
- Before policy analysis when documents are relevant to the question.

## Steps

1. Identify the file type and whether it is text-based, scanned, table-heavy or layout-heavy.
2. Choose parsing strategy:
   - Text PDF → `liteparse` when available.
   - Table-heavy PDF → preserve table structure, page numbers and section titles.
   - Scanned PDF → OCR-capable parsing; mark OCR uncertainty.
   - Layout-heavy PDF → layout-aware parser.
   - Word → preserve headings, tables and footnotes.
3. Extract content with page/location markers, section titles and table boundaries.
4. Note OCR uncertainty, missing pages or unreadable sections.
5. Return only the parsed content summary and extraction notes.

## Privacy

- Do not send sensitive documents to external services without user approval.
- Keep original filenames and extraction metadata when passing content downstream.

## Output

Structured extraction with location markers. Do not perform policy analysis.
