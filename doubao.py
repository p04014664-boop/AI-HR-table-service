"""豆包(火山方舟)客户端：同一模型既能读文字、也能看图。"""
import json
import base64
import requests
from config import cfg

ARK = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"


def _chat(messages):
    r = requests.post(
        ARK,
        headers={"Authorization": f"Bearer {cfg.ARK_API_KEY}", "Content-Type": "application/json"},
        json={"model": cfg.ARK_MODEL, "messages": messages, "temperature": 0.0},
        timeout=90,
    ).json()
    return r["choices"][0]["message"]["content"].strip()


def ask(prompt):
    return _chat([{"role": "user", "content": prompt}])


def ask_image(prompt, image_bytes, mime="image/png"):
    b64 = base64.b64encode(image_bytes).decode()
    return _chat([{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ]}])


def parse_json(text):
    return json.loads(text[text.find("{"):text.rfind("}") + 1])


def classify_position(boss, source, positions, categories, channels):
    """把 BOSS 岗位名/来源，归类到公司真实岗位清单里（只从清单选，不瞎造）。"""
    p = (
        f"招聘信息归类。候选人在招聘平台的岗位名「{boss}」，简历来源「{source}」。"
        "从下面各清单里各选一个最匹配的，只输出JSON："
        '{"岗位":"","大类":"","渠道":""}；清单里都不匹配就填"待确认"。'
        f"\n岗位清单:{' / '.join(positions)}"
        f"\n大类清单:{' / '.join(categories)}"
        f"\n渠道清单:{' / '.join(channels)}"
    )
    try:
        return parse_json(ask(p))
    except Exception:
        return {}
