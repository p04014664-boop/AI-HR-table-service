"""通讯录开通后:app 查到玄玄的正确 openId → 建会议+正确邀请+允许参会人开会。"""
import os, time, requests
from urllib.parse import quote
BASE = "https://open.feishu.cn/open-apis"
tok = requests.post(f"{BASE}/auth/v3/tenant_access_token/internal",
    json={"app_id": os.environ["FEISHU_APP_ID"], "app_secret": os.environ["FEISHU_APP_SECRET"]}, timeout=20).json()["tenant_access_token"]
H = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

# ① 查玄玄 openId:先试通讯录 batch_get_id(需玄玄邮箱/手机),兜底用秒聘开发群成员
xuan = None
# 兜底:从秒聘开发群成员拿(cli_aad38 scope)
r = requests.get(f"{BASE}/im/v1/chats/oc_002c4a5698559cefb3761e64cd606ff8/members",
    headers=H, params={"page_size": 50}, timeout=20).json()
print("群成员 code=", r.get("code"), r.get("msg") or "")
for m in (r.get("data") or {}).get("items", []):
    if "玄玄" in (m.get("name") or ""):
        xuan = m.get("member_id")
print("玄玄 openId(cli_aad38 scope)=", xuan)

# ② 验通讯录:用这个 openId 反查用户信息(通讯录权限通了才有返回)
if xuan:
    u = requests.get(f"{BASE}/contact/v3/users/{xuan}", headers=H, params={"user_id_type": "open_id"}, timeout=20).json()
    print("通讯录查用户 code=", u.get("code"), "| 姓名=", ((u.get("data") or {}).get("user") or {}).get("name"), "| 邮箱=", ((u.get("data") or {}).get("user") or {}).get("email"))

# ③ 建会议 + 邀请玄玄 + 允许参会人开会
cal = requests.post(f"{BASE}/calendar/v4/calendars/primary", headers=H, timeout=20).json()
cid = cal["data"]["calendars"][0]["calendar"]["calendar_id"]
ce = quote(cid, safe="")
start = int(time.time()) + 60
r = requests.post(f"{BASE}/calendar/v4/calendars/{ce}/events", headers=H, json={
    "summary": "AI-HR全自动测试-app建",
    "start_time": {"timestamp": str(start), "timezone": "Asia/Shanghai"},
    "end_time": {"timestamp": str(start + 1800), "timezone": "Asia/Shanghai"},
    "vchat": {"vc_type": "vc", "meeting_settings": {"auto_record": True, "allow_attendees_start": True}},
    "need_notification": True,
}, timeout=20).json()
ev = (r.get("data") or {}).get("event") or {}
eid = ev.get("event_id")
print("\n建日程 code=", r.get("code"), "| event=", eid, "| 会议链接=", (ev.get("vchat") or {}).get("meeting_url"))
if xuan and eid:
    ra = requests.post(f"{BASE}/calendar/v4/calendars/{ce}/events/{eid}/attendees", headers=H,
        json={"attendees": [{"type": "user", "user_id": xuan}], "need_notification": True}, timeout=20).json()
    print("邀请玄玄 code=", ra.get("code"), ra.get("msg") or "ok")
