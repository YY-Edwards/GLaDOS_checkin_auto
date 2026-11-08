import requests
import json
import os


# ================= 配置区 =================
# PushPlus 推送密钥（可选，为空则不推送）
sckey = os.environ.get("PUSHPLUS_TOKEN", "")

# GLaDOS Cookie，多个账号用 & 分隔
cookies_raw = os.environ.get("GLADOS_COOKIE", "")
cookies = cookies_raw.split("&") if cookies_raw else []

# User-Agent：务必与获取 Cookie 的浏览器一致
useragent = os.environ.get(
    "GLADOS_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36",
)

# GLaDOS 2026 年新 API
BASE_URL = "https://glados.cloud"
URL_CHECKIN = f"{BASE_URL}/api/user/checkin"
URL_STATUS = f"{BASE_URL}/api/user/status"
REFERER = f"{BASE_URL}/console/checkin"
ORIGIN = BASE_URL

# 签到 token（新 API 使用 glados.cloud）
PAYLOAD = {"token": "glados.cloud"}
# =========================================


def send_push(title, content):
    """发送 PushPlus 通知，失败不影响主流程"""
    if not sckey:
        return
    try:
        requests.get(
            "http://www.pushplus.plus/send",
            params={"token": sckey, "title": title, "content": content},
            timeout=10,
        )
    except Exception as e:
        print(f"[警告] PushPlus 推送失败: {e}")


def checkin_one(cookie, index):
    """对单个账号执行签到，返回结果字符串"""
    headers = {
        "cookie": cookie,
        "referer": REFERER,
        "origin": ORIGIN,
        "user-agent": useragent,
        "content-type": "application/json;charset=UTF-8",
    }

    # 1. 执行签到
    try:
        checkin_resp = requests.post(
            URL_CHECKIN,
            headers=headers,
            data=json.dumps(PAYLOAD),
            timeout=20,
        )
        checkin_json = checkin_resp.json()
    except Exception as e:
        return f"账号{index}: 签到请求异常: {e}"

    # 2. 查询状态
    try:
        state_resp = requests.get(URL_STATUS, headers=headers, timeout=20)
        state_json = state_resp.json()
    except Exception as e:
        return f"账号{index}: 状态查询异常: {e}"

    # 3. 校验返回数据
    if "data" not in state_json:
        return (
            f"账号{index}: 状态获取失败，服务器返回: {state_json}。"
            f"请检查 Cookie 是否失效，以及 User-Agent 是否与登录浏览器一致"
        )

    try:
        time_left = str(state_json["data"]["leftDays"]).split(".")[0]
        email = state_json["data"]["email"]
    except (KeyError, TypeError) as e:
        return f"账号{index}: 解析状态数据失败: {e}, 原始数据: {state_json}"

    # 4. 解析签到结果（适配新版 API）
    # 新版成功返回如："Checkin! Got 1 Points"，或者重复签到可能是 "Repeats" 等
    mess = checkin_json.get("message", "")
    code = checkin_json.get("code", -1)
    
    # 只要 code 为 0（成功），或者 message 包含 Checkin/Repeats，都视为成功
    if code == 0 or "Checkin" in mess or "Repeats" in mess:
        # 如果是今天已经签过了，提示一下
        if "Repeats" in mess or checkin_json.get("repeated"):
            return f"{email}----今日已签到----剩余({time_left})天"
        return f"{email}----{mess}----剩余({time_left})天"
    else:
        # 真正的失败，只打印 code 和 message，不打印超长的 list 账单
        return f"账号{index}({email}): 签到失败 [{code}] {mess} ----剩余({time_left})天"

def start():
    if not cookies or cookies[0] == "":
        print("未获取到 COOKIE 变量，退出")
        return

    print(f"共检测到 {len(cookies)} 个账号")
    print("checking cookies:")
    for i, c in enumerate(cookies, 1):
        # 只打印前后片段，避免完整泄露
        snippet = c[:20] + "..." + c[-10:] if len(c) > 30 else c
        print(f"  [{i}] {snippet}")

    results = []
    for i, cookie in enumerate(cookies, 1):
        if not cookie.strip():
            continue
        print(f"--- 处理第 {i} 个账号 ---")
        result = checkin_one(cookie.strip(), i)
        print(result)
        results.append(result)

    sendContent = "\n".join(results)

    if sckey and sendContent:
        send_push("GLaDOS 签到结果", sendContent)


def main_handler(event, context):
    """腾讯云函数 / 其他云函数入口"""
    return start()


if __name__ == "__main__":
    start()
