"""Themed WebUI for 3wagent.

Subclass of qwen_agent.gui.WebUI that overrides only presentation:
a dark "Deep Watch" Gradio theme plus a custom CSS layer, without
modifying the installed qwen-agent package.

The `run()` layout below mirrors qwen_agent.gui.web_ui.WebUI.run
(qwen-agent, Apache-2.0). If qwen-agent is upgraded, re-sync this
method with the vendor version.
"""

import os
from typing import List

from qwen_agent.gui import WebUI
from qwen_agent.llm.schema import Message

THEME_CSS_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'webui_theme.css')


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
            body_background_fill='#0a0f1a',
            body_background_fill_dark='#0a0f1a',
            body_text_color='#e8eef8',
            body_text_color_dark='#e8eef8',
            block_background_fill='#111a2a',
            block_background_fill_dark='#111a2a',
            block_border_color='rgba(120, 150, 200, 0.16)',
            block_border_color_dark='rgba(120, 150, 200, 0.16)',
            block_label_text_color='#a8b6cc',
            block_label_text_color_dark='#a8b6cc',
            input_background_fill='#16223a',
            input_background_fill_dark='#16223a',
            button_primary_background_fill='*primary_500',
            button_primary_background_fill_dark='*primary_500',
            button_primary_text_color='#0a0f1a',
            button_primary_text_color_dark='#0a0f1a',
        )

        with gr.Blocks(
                css=_load_theme_css(),
                theme=custom_theme,
                title='3wagent',
        ) as demo:
            history = gr.State([])
            with ms.Application():
                with gr.Row(elem_classes='container'):
                    with gr.Column(scale=4):
                        chatbot = mgr.Chatbot(value=convert_history_to_chatbot(messages=messages),
                                              avatar_images=[
                                                  self.user_config,
                                                  self.agent_config_list,
                                              ],
                                              height=850,
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

            demo.load(None)

        demo.queue(default_concurrency_limit=concurrency_limit).launch(share=share,
                                                                       server_name=server_name,
                                                                       server_port=server_port)
