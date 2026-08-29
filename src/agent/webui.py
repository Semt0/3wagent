"""Themed WebUI for 3wagent.

Subclass of qwen_agent.gui.WebUI that overrides only presentation:
a dark "Deep Watch" Gradio theme plus a custom CSS layer, without
modifying the installed qwen-agent package.

The `run()` layout below mirrors qwen_agent.gui.web_ui.WebUI.run
(qwen-agent, Apache-2.0); `agent_run()` below mirrors WebUI.agent_run
with sub-agent transcript folding added. If qwen-agent is upgraded,
re-sync BOTH methods with the vendor version.
"""

import os
import pprint
import re
from html import escape
from typing import List

from markdown_it import MarkdownIt
from qwen_agent.agents.user_agent import PENDING_USER_INPUT
from qwen_agent.gui import WebUI
from qwen_agent.gui.utils import convert_fncall_to_text
from qwen_agent.llm.schema import CONTENT, NAME, ROLE, Message
from qwen_agent.log import logger

MAIN_AGENT_NAME = '3wagent'

# gfm-like enables tables; html is explicitly disabled because the result
# files are model-generated and gr.HTML does not sanitize.
_MD = MarkdownIt('gfm-like', {'html': False})


def group_responses_for_display(display_responses: List[dict]) -> List[dict]:
    """Fold consecutive same-sub-agent messages into one collapsible unit.

    Messages with no name (or the main agent's name) stay as individual
    bubbles. A run of consecutive messages tagged with the same sub-agent
    name (qwen-agent tags them automatically via Agent.run) becomes one
    bubble whose content is a collapsed <details> block.
    """
    units: List[dict] = []
    for msg in display_responses:
        name = msg.get(NAME)
        if not name or name == MAIN_AGENT_NAME:
            units.append({ROLE: msg[ROLE], CONTENT: msg[CONTENT], NAME: name})
            continue
        if units and units[-1].get('_group') == name:
            units[-1]['_parts'].append(msg[CONTENT] or '')
        else:
            units.append({ROLE: msg[ROLE], NAME: name, '_group': name, '_parts': [msg[CONTENT] or '']})

    result = []
    for unit in units:
        if '_group' not in unit:
            result.append(unit)
            continue
        parts = [p for p in unit['_parts'] if p.strip()]
        body = '\n\n---\n\n'.join(parts)
        unit[CONTENT] = (
            f"<details><summary>{escape(unit[NAME])} · {len(parts)} 条消息（已折叠）</summary>\n\n"
            f"{body}\n\n</details>"
        )
        unit.pop('_group')
        unit.pop('_parts')
        result.append(unit)
    return result

THEME_CSS_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'webui_theme.css')
LOGO_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')
LOGO_SMALL_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'logo_small.png')


def _logo_data_uri() -> str:
    """Inline the 128px logo as a data URI so gr.HTML can use it without a file route."""
    import base64

    with open(LOGO_SMALL_PATH, 'rb') as f:
        return 'data:image/png;base64,' + base64.b64encode(f.read()).decode()


def _load_theme_css() -> str:
    """Return vendor appBot.css followed by our theme overrides."""
    from qwen_agent.gui import web_ui as vendor_web_ui

    vendor_css_path = os.path.join(os.path.dirname(vendor_web_ui.__file__), 'assets', 'appBot.css')
    chunks = []
    for path in (vendor_css_path, THEME_CSS_PATH):
        with open(path, encoding='utf-8') as f:
            chunks.append(f.read())
    return '\n\n'.join(chunks)


class ThemedWebUI(WebUI):
    """qwen_agent WebUI with the 3wagent dark theme applied."""

    def agent_run(self, _chatbot, _history, _agent_selector=None):
        # Copied from qwen_agent.gui.web_ui.WebUI.agent_run (qwen-agent,
        # Apache-2.0) with one change: display_responses are grouped so
        # sub-agent transcripts collapse into <details> blocks.
        # Re-sync with the vendor version when qwen-agent is upgraded.
        if self.verbose:
            logger.info('agent_run input:\n' + pprint.pformat(_history, indent=2))

        num_input_bubbles = len(_chatbot) - 1
        num_output_bubbles = 1
        _chatbot[-1][1] = [None for _ in range(len(self.agent_list))]

        agent_runner = self.agent_list[_agent_selector or 0]
        if self.agent_hub:
            agent_runner = self.agent_hub
        responses = []
        for responses in agent_runner.run(_history, **self.run_kwargs):
            if not responses:
                continue
            if responses[-1][CONTENT] == PENDING_USER_INPUT:
                logger.info('Interrupted. Waiting for user input!')
                break

            display_responses = convert_fncall_to_text(responses)
            if not display_responses:
                continue
            if display_responses[-1][CONTENT] is None:
                continue

            # 3wagent change: fold sub-agent transcripts into one bubble each.
            display_responses = group_responses_for_display(display_responses)

            while len(display_responses) > num_output_bubbles:
                # Create a new chat bubble
                _chatbot.append([None, None])
                _chatbot[-1][1] = [None for _ in range(len(self.agent_list))]
                num_output_bubbles += 1

            assert num_output_bubbles == len(display_responses)
            assert num_input_bubbles + num_output_bubbles == len(_chatbot)

            for i, rsp in enumerate(display_responses):
                agent_index = self._get_agent_index_by_name(rsp[NAME])
                _chatbot[num_input_bubbles + i][1][agent_index] = rsp[CONTENT]

            if len(self.agent_list) > 1:
                _agent_selector = agent_index

            if _agent_selector is not None:
                yield _chatbot, _history, _agent_selector
            else:
                yield _chatbot, _history

        if responses:
            _history.extend([res for res in responses if res[CONTENT] != PENDING_USER_INPUT])

        if _agent_selector is not None:
            yield _chatbot, _history, _agent_selector
        else:
            yield _chatbot, _history

        if self.verbose:
            logger.info('agent_run response:\n' + pprint.pformat(responses, indent=2))

    def _render_side_panels(self):
        """Status block (run id / mode / current step) + sub-agent result files.

        Called once per second by a gr.Timer into hidden textboxes; the page's
        sidebar_js diffs them into the visible panels only when the content
        actually changed (polling without flicker). Reads runtime state
        without side effects (never creates a run).
        """
        from src.config.runtime import current_run_id, get_subagents_dir

        agent = self.agent_list[0]
        run_id = current_run_id()
        mode = getattr(agent, 'mode', None)
        working = mode is not None and mode.value == 'working'
        mode_label = '工作模式' if working else '对话模式'
        badge_cls = 'w3-badge w3-badge-working' if working else 'w3-badge w3-badge-normal'
        step = getattr(agent, 'current_step', None) or '—'
        status_html = (
            "<div class='w3-status'>"
            f"<div class='w3-status-row'><span class='w3-status-key'>run-id</span>"
            f"<span class='w3-status-val'>{escape(run_id or '—')}</span></div>"
            f"<div class='w3-status-row'><span class='w3-status-key'>模式</span>"
            f"<span class='{badge_cls}'>{mode_label}</span></div>"
            f"<div class='w3-status-step'><span class='w3-status-key'>当前步骤</span>"
            f"<span class='w3-status-step-val'>{escape(step)}</span></div>"
            "</div>"
        )

        items, modals = [], []
        if run_id:
            sub_dir = get_subagents_dir()
            if sub_dir.exists():
                for path in sorted(sub_dir.glob('*_result.md')):
                    modal_id = 'w3m-' + re.sub(r'[^0-9A-Za-z_-]', '-', path.stem)
                    items.append(
                        f"<div class='w3-result-link' data-w3modal='{modal_id}'>"
                        f"{escape(path.name)}</div>"
                    )
                    content_html = _MD.render(path.read_text(encoding='utf-8'))
                    modals.append(
                        f"<div class='w3-modal' id='{modal_id}'>"
                        "<div class='w3-modal-mask'></div>"
                        "<div class='w3-modal-card'>"
                        f"<div class='w3-modal-head'><span>{escape(path.name)}</span>"
                        "<button class='w3-modal-close' type='button'>×</button></div>"
                        f"<div class='w3-modal-body w3-md'>{content_html}</div>"
                        "</div></div>"
                    )
        results_html = (
            ''.join(items) if items else "<div class='w3-empty'>暂无子代理结果</div>"
        ) + ''.join(modals)

        return status_html, results_html

    def run(self,
            messages: List[Message] = None,
            share: bool = False,
            server_name: str = None,
            server_port: int = None,
            concurrency_limit: int = 10,
            enable_mention: bool = False,
            **kwargs):
        self.run_kwargs = kwargs

        from qwen_agent.gui.gradio_dep import gr, mgr, ms
        from qwen_agent.gui.utils import convert_history_to_chatbot

        custom_theme = gr.themes.Base(
            primary_hue=gr.themes.utils.colors.blue,
            neutral_hue=gr.themes.utils.colors.slate,
            radius_size=gr.themes.utils.sizes.radius_md,
            font=[
                gr.themes.GoogleFont('Inter'),
                'Noto Sans SC',
                'PingFang SC',
                'sans-serif',
            ],
            font_mono=[
                gr.themes.GoogleFont('JetBrains Mono'),
                'monospace',
            ],
        ).set(
            body_background_fill='#f6f8fa',
            body_background_fill_dark='#0d1117',
            body_text_color='#1f2328',
            body_text_color_dark='#e6edf3',
            block_background_fill='#ffffff',
            block_background_fill_dark='#161b22',
            block_border_color='#d0d7de',
            block_border_color_dark='#30363d',
            block_label_text_color='#59636e',
            block_label_text_color_dark='#9198a1',
            input_background_fill='#ffffff',
            input_background_fill_dark='#1c2330',
            button_primary_background_fill='#0969da',
            button_primary_background_fill_dark='#2f81f7',
            button_primary_background_fill_hover='#0550ae',
            button_primary_background_fill_hover_dark='#3b8cf5',
            button_primary_text_color='#ffffff',
            button_primary_text_color_dark='#ffffff',
        )

        header_html = """
<div style="display:flex;align-items:center;gap:12px;padding:4px 8px 14px;border-bottom:1px solid var(--w3-border);margin-bottom:14px">
  <img src="__LOGO__" alt="3wagent logo" style="width:34px;height:34px;border-radius:8px;display:block">
  <div>
    <div style="font-size:16px;font-weight:600;color:var(--w3-text);letter-spacing:-0.01em">3wagent</div>
    <div style="font-size:12px;color:var(--w3-text-2)">跨境政策合规分析助手</div>
  </div>
  <button id="w3-theme-toggle" type="button" title="切换明暗模式" aria-label="切换明暗模式">☾</button>
</div>
""".replace('__LOGO__', _logo_data_uri())

        # Mode resolution order (highest priority first):
        #   1. explicit ?__theme= URL param (Gradio native)
        #   2. stored manual choice (localStorage)
        #   3. whatever Gradio decided from the system preference
        # The click handler uses document-level delegation so it works
        # regardless of when the header HTML finishes rendering.
        theme_toggle_js = """
() => {
  const syncIcon = () => {
    const b = document.getElementById('w3-theme-toggle');
    if (b) b.textContent = document.body.classList.contains('dark') ? '☀︎' : '☾';
  };
  const apply = (mode, persist) => {
    document.body.classList.toggle('dark', mode === 'dark');
    if (persist) localStorage.setItem('w3-theme', mode);
    syncIcon();
  };
  const urlTheme = new URLSearchParams(location.search).get('__theme');
  const stored = localStorage.getItem('w3-theme');
  if (urlTheme === 'dark' || urlTheme === 'light') {
    apply(urlTheme, false);
  } else if (stored === 'dark' || stored === 'light') {
    apply(stored, false);
  } else {
    syncIcon();
  }
  if (!document.body.dataset.w3ThemeBound) {
    document.body.dataset.w3ThemeBound = '1';
    document.addEventListener('click', (e) => {
      if (e.target && e.target.id === 'w3-theme-toggle') {
        apply(document.body.classList.contains('dark') ? 'light' : 'dark', true);
      }
    });
  }
}
"""

        # Sidebar modal behavior: click a result link to open its modal; click
        # the mask or × to close. Panel content arrives via hidden textboxes
        # (gr.Timer → server) and is diffed into the visible roots only when
        # changed, so polling never flickers and an open modal survives
        # unchanged polls.
        sidebar_js = """
() => {
  if (document.body.dataset.w3SidebarBound) return;
  document.body.dataset.w3SidebarBound = '1';

  document.addEventListener('click', (e) => {
    const link = e.target.closest('.w3-result-link');
    if (link) {
      const m = document.getElementById(link.dataset.w3modal);
      if (m) m.classList.add('w3-open');
      return;
    }
    if (e.target.closest('.w3-modal-close') || e.target.classList.contains('w3-modal-mask')) {
      const m = e.target.closest('.w3-modal');
      if (m) m.classList.remove('w3-open');
    }
  });

  const last = {status: null, results: null};
  setInterval(() => {
    for (const key of ['status', 'results']) {
      const box = document.getElementById('w3-' + key + '-val');
      // single-line gr.Textbox renders an <input>, multi-line a <textarea>
      const ta = box && box.querySelector('textarea, input');
      const root = document.getElementById('w3-' + key + '-root');
      if (!ta || !root) continue;
      if (ta.value !== last[key]) {
        root.innerHTML = ta.value;
        last[key] = ta.value;
      }
    }
  }, 500);
}
"""

        with gr.Blocks(
                css=_load_theme_css(),
                theme=custom_theme,
                title='3wagent',
        ) as demo:
            history = gr.State([])
            with ms.Application():
                gr.HTML(header_html)
                with gr.Row(elem_classes='container'):
                    with gr.Column(scale=1, elem_classes='w3-sidebar'):
                        gr.HTML("<div class='w3-sidebar-title'>运行状态</div>")
                        gr.HTML("<div id='w3-status-root'></div>")
                        gr.HTML("<div class='w3-sidebar-title' style='margin-top:14px'>子代理结果</div>")
                        gr.HTML("<div id='w3-results-root'></div>")
                        # Hidden textboxes receive the polled panel content from
                        # the server; sidebar_js diffs them into the visible
                        # roots only when the content changed (no flicker).
                        status_val = gr.Textbox(visible=False, elem_id='w3-status-val')
                        results_val = gr.Textbox(visible=False, elem_id='w3-results-val')
                    with gr.Column(scale=4):
                        chatbot = mgr.Chatbot(value=convert_history_to_chatbot(messages=messages),
                                              avatar_images=[
                                                  self.user_config,
                                                  self.agent_config_list,
                                              ],
                                              height=620,
                                              avatar_image_width=80,
                                              flushing=False,
                                              show_copy_button=True,
                                              latex_delimiters=[{
                                                  'left': '\\(',
                                                  'right': '\\)',
                                                  'display': True
                                              }, {
                                                  'left': '\\begin{equation}',
                                                  'right': '\\end{equation}',
                                                  'display': True
                                              }, {
                                                  'left': '\\begin{align}',
                                                  'right': '\\end{align}',
                                                  'display': True
                                              }, {
                                                  'left': '\\begin{alignat}',
                                                  'right': '\\end{alignat}',
                                                  'display': True
                                              }, {
                                                  'left': '\\begin{gather}',
                                                  'right': '\\end{gather}',
                                                  'display': True
                                              }, {
                                                  'left': '\\begin{CD}',
                                                  'right': '\\end{CD}',
                                                  'display': True
                                              }, {
                                                  'left': '\\[',
                                                  'right': '\\]',
                                                  'display': True
                                              }])

                        input = mgr.MultimodalInput(placeholder=self.input_placeholder, )
                        audio_input = gr.Audio(
                            sources=['microphone'],
                            type='filepath'
                        )

                    with gr.Column(scale=1):
                        if len(self.agent_list) > 1:
                            agent_selector = gr.Dropdown(
                                [(agent.name, i) for i, agent in enumerate(self.agent_list)],
                                label='Agents',
                                info='选择一个Agent',
                                value=0,
                                interactive=True,
                            )

                        agent_info_block = self._create_agent_info_block()

                        agent_plugins_block = self._create_agent_plugins_block()

                        if self.prompt_suggestions:
                            gr.Examples(
                                label='推荐对话',
                                examples=self.prompt_suggestions,
                                inputs=[input],
                            )

                    if len(self.agent_list) > 1:
                        agent_selector.change(
                            fn=self.change_agent,
                            inputs=[agent_selector],
                            outputs=[agent_selector, agent_info_block, agent_plugins_block],
                            queue=False,
                        )

                    input_promise = input.submit(
                        fn=self.add_text,
                        inputs=[input, audio_input, chatbot, history],
                        outputs=[input, audio_input, chatbot, history],
                        queue=False,
                    )

                    if len(self.agent_list) > 1 and enable_mention:
                        input_promise = input_promise.then(
                            self.add_mention,
                            [chatbot, agent_selector],
                            [chatbot, agent_selector],
                        ).then(
                            self.agent_run,
                            [chatbot, history, agent_selector],
                            [chatbot, history, agent_selector],
                        )
                    else:
                        input_promise = input_promise.then(
                            self.agent_run,
                            [chatbot, history],
                            [chatbot, history],
                        )

                    input_promise.then(self.flushed, None, [input])

            timer = gr.Timer(1.0)
            timer.tick(fn=self._render_side_panels, outputs=[status_val, results_val])

            demo.load(None)
            demo.load(None, js=theme_toggle_js)
            demo.load(None, js=sidebar_js)

        demo.queue(default_concurrency_limit=concurrency_limit).launch(share=share,
                                                                       server_name=server_name,
                                                                       server_port=server_port,
                                                                       favicon_path=LOGO_PATH)
