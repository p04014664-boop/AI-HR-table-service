import re, requests
from config import cfg
from feishu import Feishu
import doubao, resume
from rules import _cell
BASE="https://open.feishu.cn/open-apis"
fs=Feishu()
# 1. 句子秒聘读AI面评prompt文档
r=requests.get(f"{BASE}/docx/v1/documents/Nsgbw1j1Bi1IYUkG6kkcaKcDnFe/raw_content",
               headers={"Authorization":f"Bearer {fs.token()}"},timeout=30).json()
if r.get("code")!=0:
    print("❌ 句子秒聘读AI面评文档失败:",r.get("code"),r.get("msg")[:80]); raise SystemExit
print("✅ 句子秒聘能读到AI面评标准文档")
content=r["data"]["content"]
idx=content.find("前端开发工程师")
frontend=content[idx:idx+1600]
# 2. 范子腾简历摘要
att=None
for rec in fs.list_records(cfg.PROG_APP,cfg.PROG_TABLE):
    if _cell(rec["fields"].get("姓名"))=="范子腾":
        a=rec["fields"].get("简历"); att=a[0] if a else None; break
fields,_=resume.extract_fields(fs.download_attachment(att),att.get("name",""))
summary=fields.get("简历摘要","")
# 3. 豆包严格按前端标准打分
p=("你是资深招聘官。严格按下面这份【岗位评分标准】的维度和权重给候选人打分,不要用你自己的通用判断。"
   '只输出JSON:{"各维度得分":{},"总分":0,"结论":"","一票否决命中":"无或具体","亮点":"","顾虑":""}\n'
   f"【岗位评分标准】\n{frontend}\n\n【候选人简历】\n{summary}")
print("\n=== 豆包按【前端标准包】给范子腾打分 ===")
print(doubao.ask(p))
