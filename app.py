"""
Hugging Face Space entrypoint (FREE Gradio SDK — no Docker, no card).

Launches the full bot (auto scanner + Telegram wizard) in a background
thread and serves a small status page on port 7860 so HF sees a healthy app.
"""
import threading
import time
import traceback

import gradio as gr

import main as bot

def _bot_forever():
    while True:
        try:
            # health=False: the Gradio UI itself serves port 7860
            bot.main(health=False)
        except Exception as e:
            print(f"[APP] bot crashed: {e}")
            traceback.print_exc()
            time.sleep(60)  # restart after a minute

threading.Thread(target=_bot_forever, daemon=True).start()

def status():
    return "🟢 myauto profit bot is running — check your Telegram!"

demo = gr.Interface(
    fn=status,
    inputs=None,
    outputs=gr.Textbox(label="Status"),
    title="🚗 myauto Profit Bot",
    description="Scans myauto.ge and sends profitable cars to Telegram.",
)

demo.launch(server_name="0.0.0.0", server_port=7860)
