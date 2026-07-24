"""大模型客户端（OpenAI 兼容 chat/completions）：同一模型既能读文字、也能看图。
默认走句子内部网关 gpt-4o(配了 LLM_KEY)，与触达统一；没配 LLM_KEY 则回退火山豆包。"""
import json
import base64
import requests
from config import cfg

ARK = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"


def _target():
    """返回 (url, key, model)：有网关 key 走网关 gpt-4o，否则回退火山豆包。"""
    if cfg.LLM_KEY:
        return cfg.LLM_BASE.rstrip("/") + "/v1/chat/completions", cfg.LLM_KEY, cfg.LLM_MODEL
    return ARK, cfg.ARK_API_KEY, cfg.ARK_MODEL


def _chat(messages):
    url, key, model = _target()
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0.0, "max_tokens": 4096},
        timeout=90,
    ).json()
    if not r.get("choices"):  # 缺 choices 或 choices 为空列表(网关 4xx/鉴权失败/被过滤)→可读报错
        raise RuntimeError(f"LLM 返回异常({model}): {str(r)[:300]}")
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
