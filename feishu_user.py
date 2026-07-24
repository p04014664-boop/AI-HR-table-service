"""飞书【用户身份】客户端(OAuth v2)。
用途:app(机器人)身份读不了「人拥有的妙记/文字记录」——飞书把 app 当"非组织成员","组织内可见"只对人开放。
     全自动出面评必须用**用户身份**:一个 HR/服务账号授权一次,服务用它的 token 搜+读妙记文字记录。
     (2026-07-23 已用句子局长用户 token 实测:用户身份能搜到+读出真实面试逐字稿,app 身份不行。)

配置(env,放服务器 .env,绝不进仓库):
  FEISHU_USER_APP_ID / FEISHU_USER_APP_SECRET  用户身份 OAuth 用的 app(可与秒聘同一个 app,要在开放平台开用户 scope+redirect;
                                               或另建一个专用 spider app)。缺省回退 FEISHU_APP_ID/SECRET。
  FEISHU_OAUTH_REDIRECT   在开放平台配的重定向 URL(拿授权码用),缺省 https://open.feishu.cn/api-explorer/loopback
令牌落盘:data/user_token.json (refresh_token 长期有效、过期前自动刷新)。
所需用户 scope(开放平台"用户身份"那栏勾上):docs:document.content:read、search:docs:read(或 minutes:minutes.search:read)、offline_access。
"""
import os, json, time, logging, requests

log = logging.getLogger("feishu_user")
AUTH = "https://open.feishu.cn/open-apis"
ACCOUNTS = "https://accounts.feishu.cn/open-apis"
SCOPES = "docx:document:readonly docs:document.content:read search:docs:read offline_access"


class FeishuUser:
    def __init__(self, token_path=None):
        self.app_id = os.environ.get("FEISHU_USER_APP_ID") or os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = os.environ.get("FEISHU_USER_APP_SECRET") or os.environ.get("FEISHU_APP_SECRET", "")
        self.redirect = os.environ.get("FEISHU_OAUTH_REDIRECT",
                                       "https://open.feishu.cn/api-explorer/loopback")
        self.token_path = token_path or os.path.join(
            os.environ.get("DATA_DIR", "data"), "user_token.json")
        self._store = self._load()

    # ---------- 令牌落盘 ----------
    def _load(self):
        try:
            return json.load(open(self.token_path))
        except Exception:
            return {}

    def _save(self):
        os.makedirs(os.path.dirname(self.token_path) or ".", exist_ok=True)
        json.dump(self._store, open(self.token_path, "w"), ensure_ascii=False)

    def authorized(self):
        return bool(self._store.get("refresh_token"))

    # ---------- OAuth ----------
    def authorize_url(self, state="miaopin"):
        """一次性:把这个 URL 发给 HR/服务账号,登录授权后从回调 URL 里拿 ?code= 交给 exchange_code。"""
        from urllib.parse import urlencode
        q = urlencode({"client_id": self.app_id, "redirect_uri": self.redirect,
                       "scope": SCOPES, "state": state, "response_type": "code"})
        return f"{ACCOUNTS}/authen/v1/authorize?{q}"

    def _token_call(self, payload):
        r = requests.post(f"{AUTH}/authen/v2/oauth/token",
                          json={**payload, "client_id": self.app_id,
                                "client_secret": self.app_secret}, timeout=20).json()
        if r.get("code") not in (0, None) or "access_token" not in r:
            raise RuntimeError(f"oauth token: {r.get('code')} {r.get('error') or r.get('msg')} {r}")
        now = int(time.time())
        self._store.update({
            "access_token": r["access_token"],
            "refresh_token": r.get("refresh_token", self._store.get("refresh_token")),
            "access_exp": now + int(r.get("expires_in", 7000)) - 300,
            "refresh_exp": now + int(r.get("refresh_token_expires_in", 30 * 86400)),
        })
        self._save()
        return r["access_token"]

    def exchange_code(self, code):
        """一次性:用授权码换 access+refresh token 并落盘。"""
        return self._token_call({"grant_type": "authorization_code", "code": code,
                                 "redirect_uri": self.redirect})

    def refresh(self):
        rt = self._store.get("refresh_token")
        if not rt:
            raise RuntimeError("未授权:先跑 oauth_bootstrap.py 让服务账号授权一次")
        if self._store.get("refresh_exp", 0) < time.time():
            raise RuntimeError("refresh_token 已过期:需服务账号重新授权一次")
        return self._token_call({"grant_type": "refresh_token", "refresh_token": rt, "scope": SCOPES})

    def token(self):
        if self._store.get("access_token") and self._store.get("access_exp", 0) > time.time():
            return self._store["access_token"]
        return self.refresh()

    def _h(self):
        return {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"}

    # ---------- 业务:搜 + 读 ----------
    def search_docs(self, query, count=10):
        """按关键词搜用户可见的云文档,返回 [{title, token}]。用户身份=能搜到组织内可见的真实妙记文字记录。"""
        r = requests.post(f"{AUTH}/suite/docs-api/search/object", headers=self._h(),
                          json={"search_key": query, "count": count, "docs_types": ["doc"]},
                          timeout=20).json()
        if r.get("code") != 0:
            raise RuntimeError(f"search: {r.get('code')} {r.get('msg')}")
        out = []
        for e in (r.get("data", {}) or {}).get("docs_entities", []):
            out.append({"title": e.get("title", ""), "token": e.get("docs_token", "")})
        return out

    def read_doc(self, doc_token):
        """用户身份读 docx 正文(app 读不了的组织内可见文档,用户能读)。"""
        r = requests.get(f"{AUTH}/docx/v1/documents/{doc_token}/raw_content",
                         headers=self._h(), timeout=30).json()
        if r.get("code") != 0:
            raise RuntimeError(f"read_doc: {r.get('code')} {r.get('msg')}")
        return r["data"]["content"]

    def find_transcript(self, name, position=""):
        """找某候选人这场面试的文字记录文档 → 返回 (title, token, url) 或 None。
        面试会议标题=「线上面试-{岗位}-{姓名}」,妙记生成的文字记录标题=「文字记录:线上面试-{岗位}-{姓名}」。
        用姓名+线上面试搜(岗位可能与建会时口径略有出入,不强匹配岗位),再在标题里校验。"""
        hits = self.search_docs(f"文字记录 线上面试 {name}", count=15)
        for h in hits:
            t = h["title"]
            if t.startswith("文字记录") and "线上面试" in t and name in t:
                return t, h["token"], f"https://juzihudong.feishu.cn/docx/{h['token']}"
        return None
