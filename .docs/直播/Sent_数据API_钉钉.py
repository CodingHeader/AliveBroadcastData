import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import json

# 1. 替换为你自己的 Webhook 和 Secret
webhook_url = "https://oapi.dingtalk.com/robot/send?access_token=99c35c6a2ba5e99a11d3bed3eeb11bfc7e601f63d41bf30bc114ac7dd8070327"
secret = "SEC2afaa796acd4aa424735f6f4ef92a10550d0fb927fc6b15bb40120abcadeca1e"

# 2. 生成钉钉机器人所需的签名 (加签机制)
timestamp = str(round(time.time() * 1000))
string_to_sign = f"{timestamp}\n{secret}"
hmac_code = hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'), digestmod=hashlib.sha256).digest()
sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

# 3. 拼接最终的 URL
final_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"

# 4. 构造消息内容
# 注意：如果安全设置选了“自定义关键词”，content 中必须包含该关键词！
message = {
    "msgtype": "text",
    "text": {
        "content": "【客户数据更新】\n客户名称：吴昊科技有限公司\n最新状态：已签约\n请相关同事跟进处理。"
    },
    "at": {
        "atMobiles": [
            "15892289519",  # 替换为要 @ 的同事的钉钉绑定手机号
            "17076540806"   # 可以 @ 多个人
        ],
        "isAtAll": False    # 如果需要 @ 所有人，改为 True (此时 atMobiles 失效)
    }
}

# 5. 发送 POST 请求
headers = {'Content-Type': 'application/json'}
response = requests.post(final_url, headers=headers, data=json.dumps(message))

# 6. 打印结果
print(response.json())
# 成功会返回: {"errcode": 0, "errmsg": "ok"}