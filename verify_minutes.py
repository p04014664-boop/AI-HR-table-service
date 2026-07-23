"""验证:app 身份能否取到某会议的录制妙记 + 读出逐字稿文本。
用法: python verify_minutes.py <meeting_no>   (默认 272063038 = 玄玄的测试会议)"""
import os, sys, time, datetime, requests, re
BASE = "https://open.feishu.cn/open-apis"
MEETING_NO = sys.argv[1] if len(sys.argv) > 1 else "272063038"

tok = requests.post(f"{BASE}/auth/v3/tenant_access_token/internal",
    json={"app_id": os.environ["FEISHU_APP_ID"], "app_secret": os.environ["FEISHU_APP_SECRET"]},
    timeout=20).json()
if "tenant_access_token" not in tok:
    print("❌ 取token失败:", tok); sys.exit(1)
H = {"Authorization": f"Bearer {tok['tenant_access_token']}"}

# 时间范围:今天0点~现在(list_by_no 按会议开始时间过滤)
now = int(time.time())
start = int(datetime.datetime.now().replace(hour=0, minute=0, second=0).timestamp())

print(f"=== ① list_by_no 会议号={MEETING_NO} ===")
r = requests.get(f"{BASE}/vc/v1/meetings/list_by_no", headers=H,
    params={"meeting_no": MEETING_NO, "start_time": str(start), "end_time": str(now)}, timeout=20).json()
print("  code=", r.get("code"), "msg=", r.get("msg"))
briefs = (r.get("data") or {}).get("meeting_briefs") or []
print("  找到会议:", [b.get("id") or b.get("meeting_id") for b in briefs])
if not briefs:
    print("  (没找到会议实例:可能时间范围不对/会议没真正开过/权限不够)"); sys.exit(0)

mid = briefs[-1].get("id") or briefs[-1].get("meeting_id")
print(f"\n=== ② 取录制 meeting_id={mid} ===")
r = requests.get(f"{BASE}/vc/v1/meetings/{mid}/recording", headers=H, timeout=20).json()
print("  code=", r.get("code"), "msg=", r.get("msg"))
rec = (r.get("data") or {}).get("recording") or {}
url = rec.get("url", "")
print("  妙记链接:", url or "(空—可能还没录制完/没开录制)")
if not url:
    sys.exit(0)

# 从妙记链接抽 minute_token
m = re.search(r"/minutes/([A-Za-z0-9]+)", url)
mt = m.group(1) if m else ""
print(f"\n=== ③ 妙记信息 minute_token={mt} ===")
r = requests.get(f"{BASE}/minutes/v1/minutes/{mt}", headers=H, timeout=20).json()
print("  code=", r.get("code"), "msg=", r.get("msg"))
mn = (r.get("data") or {}).get("minute") or {}
print("  标题:", mn.get("title"), "| owner:", mn.get("owner_id"), "| 时长ms:", mn.get("duration"))

print(f"\n=== ④ 逐字稿文本 ===")
r = requests.get(f"{BASE}/minutes/v1/minutes/{mt}/transcript", headers=H,
    params={"need_speaker": "true", "need_timestamp": "false"}, timeout=20)
ct = r.headers.get("content-type", "")
if "application/json" in ct:
    j = r.json()
    print("  code=", j.get("code"), "msg=", j.get("msg"))
    txt = ((j.get("data") or {}).get("transcript")) or ""
else:
    txt = r.text
print("  逐字稿前200字:", (txt or "(空)")[:200])
print("\n🎉 若④有文本 → 整条链路通,自动收集可做")
