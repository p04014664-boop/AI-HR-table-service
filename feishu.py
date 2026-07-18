"""飞书客户端：应用身份(tenant_access_token)。多维表格读写删 + 附件上传下载。"""
import time
import requests
from config import cfg

BASE = "https://open.feishu.cn/open-apis"


class Feishu:
    def __init__(self):
        self._tok = None
        self._exp = 0

    def token(self):
        if self._tok and time.time() < self._exp - 120:
            return self._tok
        r = requests.post(
            f"{BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": cfg.FEISHU_APP_ID, "app_secret": cfg.FEISHU_APP_SECRET},
            timeout=20,
        ).json()
        if "tenant_access_token" not in r:
            raise RuntimeError(f"取 token 失败: {r}")
        self._tok = r["tenant_access_token"]
        self._exp = time.time() + r.get("expire", 7000)
        return self._tok

    def _h(self):
        return {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"}

    def list_records(self, app, table, automatic_fields=False):
        out, pt = [], None
        while True:
            params = {"page_size": 500}
            if automatic_fields:
                params["automatic_fields"] = "true"
                params["user_id_type"] = "open_id"
            if pt:
                params["page_token"] = pt
            r = requests.get(
                f"{BASE}/bitable/v1/apps/{app}/tables/{table}/records",
                headers=self._h(), params=params, timeout=40,
            ).json()
            if r.get("code") != 0:
                raise RuntimeError(f"list_records {app}: {r.get('code')} {r.get('msg')}")
            out += r["data"].get("items", [])
            pt = r["data"].get("page_token")
            if not r["data"].get("has_more"):
                break
        return out

    def create_record(self, app, table, fields):
        r = requests.post(
            f"{BASE}/bitable/v1/apps/{app}/tables/{table}/records",
            headers=self._h(), json={"fields": fields}, timeout=40,
        ).json()
        if r.get("code") != 0:
            raise RuntimeError(f"create: {r.get('code')} {r.get('msg')}")
        return r["data"]["record"]["record_id"]

    def update_record(self, app, table, rid, fields):
        r = requests.put(
            f"{BASE}/bitable/v1/apps/{app}/tables/{table}/records/{rid}",
            headers=self._h(), json={"fields": fields}, timeout=40,
        ).json()
        if r.get("code") != 0:
            raise RuntimeError(f"update: {r.get('code')} {r.get('msg')}")
        return r["data"]["record"]

    def delete_record(self, app, table, rid):
        r = requests.delete(
            f"{BASE}/bitable/v1/apps/{app}/tables/{table}/records/{rid}",
            headers=self._h(), timeout=30,
        ).json()
        return r.get("code") == 0

    def list_fields(self, app, table):
        r = requests.get(
            f"{BASE}/bitable/v1/apps/{app}/tables/{table}/fields",
            headers=self._h(), params={"page_size": 100}, timeout=30,
        ).json()
        if r.get("code") != 0:
            raise RuntimeError(f"list_fields: {r.get('code')} {r.get('msg')}")
        return r["data"]["items"]

    def field_options(self, app, table, name):
        for it in self.list_fields(app, table):
            if it["field_name"] == name:
                return [o["name"] for o in (it.get("property") or {}).get("options", [])]
        return []

    def download_media(self, file_token):
        r = requests.get(
            f"{BASE}/drive/v1/medias/{file_token}/download",
            headers={"Authorization": f"Bearer {self.token()}"}, timeout=60,
        )
        r.raise_for_status()
        return r.content

    def download_attachment(self, att):
        """下载附件字节。开了高级权限的表(如真进度表)要用附件对象里的 url 字段+令牌下，
        否则回退到 file_token 的 medias/download。att = 记录里附件字段的一个元素。"""
        url = att.get("url")
        if url:
            r = requests.get(url, headers={"Authorization": f"Bearer {self.token()}"}, timeout=60)
            if r.status_code == 200:
                return r.content
        return self.download_media(att["file_token"])

    def read_doc_content(self, doc_id):
        """读一篇 docx 的纯文本内容。"""
        r = requests.get(f"{BASE}/docx/v1/documents/{doc_id}/raw_content",
                         headers=self._h(), timeout=30).json()
        if r.get("code") != 0:
            raise RuntimeError(f"read_doc: {r.get('code')} {r.get('msg')}")
        return r["data"]["content"]

    def create_doc(self, title, blocks):
        """创建一篇 docx 文档并写入内容块，返回 (document_id, url)。blocks 见 docx 块结构。"""
        r = requests.post(f"{BASE}/docx/v1/documents", headers=self._h(),
                          json={"title": title}, timeout=30).json()
        if r.get("code") != 0:
            raise RuntimeError(f"create_doc: {r.get('code')} {r.get('msg')}")
        did = r["data"]["document"]["document_id"]
        if blocks:
            w = requests.post(f"{BASE}/docx/v1/documents/{did}/blocks/{did}/children",
                              headers=self._h(), json={"index": 0, "children": blocks}, timeout=30).json()
            if w.get("code") != 0:
                raise RuntimeError(f"写块失败: {w.get('code')} {w.get('msg')}")
        return did, f"https://juzihudong.feishu.cn/docx/{did}"

    def insert_file_block(self, doc_id, index, filename, data):
        """在文档 index 处插入一个文件块并上传文件(用于把原始简历嵌进面评)。"""
        body = {"index": index, "children": [{"block_type": 23, "file": {"token": ""}}]}
        r = requests.post(f"{BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                          headers=self._h(), json=body, timeout=30).json()
        if r.get("code") != 0:
            raise RuntimeError(f"建文件块: {r.get('code')} {r.get('msg')}")
        view = [b for b in r["data"]["children"] if b.get("block_type") == 33][0]
        fbid = view["children"][0]  # 视图块的子块才是真正的文件块
        up = requests.post(f"{BASE}/drive/v1/medias/upload_all",
                           headers={"Authorization": f"Bearer {self.token()}"},
                           data={"file_name": filename, "parent_type": "docx_file",
                                 "parent_node": fbid, "size": str(len(data))},
                           files={"file": (filename, data, "application/pdf")}, timeout=90).json()
        if up.get("code") != 0:
            raise RuntimeError(f"上传文件: {up.get('code')} {up.get('msg')}")
        requests.patch(f"{BASE}/docx/v1/documents/{doc_id}/blocks/{fbid}",
                       headers=self._h(), json={"replace_file": {"token": up["data"]["file_token"]}}, timeout=30)

    def get_doc_title(self, doc_id):
        r = requests.get(f"{BASE}/docx/v1/documents/{doc_id}", headers=self._h(), timeout=30).json()
        if r.get("code") != 0:
            raise RuntimeError(f"get_doc: {r.get('code')} {r.get('msg')}")
        return r["data"]["document"]["title"]

    def update_doc_title(self, doc_id, title):
        """改 docx 标题 = 改根页面块的文本。"""
        r = requests.patch(f"{BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}",
                           headers=self._h(),
                           json={"update_text_elements": {"elements": [{"text_run": {"content": title}}]}},
                           timeout=30).json()
        if r.get("code") != 0:
            raise RuntimeError(f"改标题: {r.get('code')} {r.get('msg')}")

    def doc_blocks(self, doc_id):
        """列出文档全部块(含根页面块)。"""
        out, pt = [], None
        while True:
            params = {"page_size": 500, "document_revision_id": -1}
            if pt:
                params["page_token"] = pt
            r = requests.get(f"{BASE}/docx/v1/documents/{doc_id}/blocks",
                             headers=self._h(), params=params, timeout=30).json()
            if r.get("code") != 0:
                raise RuntimeError(f"doc_blocks: {r.get('code')} {r.get('msg')}")
            out += r["data"].get("items", [])
            pt = r["data"].get("page_token")
            if not r["data"].get("has_more"):
                break
        return out

    def replace_section(self, doc_id, start_index, end_index, new_blocks):
        """把根节点 children 的 [start,end) 区间整段换成 new_blocks(用于重写面评的AI初筛节)。"""
        r = requests.delete(f"{BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children/batch_delete",
                            headers=self._h(),
                            json={"start_index": start_index, "end_index": end_index}, timeout=30).json()
        if r.get("code") != 0:
            raise RuntimeError(f"删节: {r.get('code')} {r.get('msg')}")
        w = requests.post(f"{BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                          headers=self._h(),
                          json={"index": start_index, "children": new_blocks}, timeout=30).json()
        if w.get("code") != 0:
            raise RuntimeError(f"插节: {w.get('code')} {w.get('msg')}")

    def set_doc_org_editable(self, doc_id):
        """把 docx 设为「组织内可编辑」——应用建的文档默认只有应用是 owner，
        HR 打不开也改不了，放开后公司同事拿到链接就能编辑。"""
        r = requests.patch(
            f"{BASE}/drive/v2/permissions/{doc_id}/public",
            headers=self._h(), params={"type": "docx"},
            json={"link_share_entity": "tenant_editable"}, timeout=30,
        ).json()
        if r.get("code") != 0:
            raise RuntimeError(f"设权限: {r.get('code')} {r.get('msg')}")
        return True

    def upload_media(self, filename, data, parent_node):
        """上传文件到某个多维表格(bitable_file)，返回 file_token，可写进附件字段。"""
        r = requests.post(
            f"{BASE}/drive/v1/medias/upload_all",
            headers={"Authorization": f"Bearer {self.token()}"},
            data={"file_name": filename, "parent_type": "bitable_file",
                  "parent_node": parent_node, "size": str(len(data))},
            files={"file": (filename, data, "application/octet-stream")},
            timeout=90,
        ).json()
        if r.get("code") != 0:
            raise RuntimeError(f"upload: {r.get('code')} {r.get('msg')}")
        return r["data"]["file_token"]
