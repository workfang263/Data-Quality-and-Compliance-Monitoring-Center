import requests
import json

# 1. 把你的 Webhook 地址填在这里
url = "https://oapi.dingtalk.com/robot/send?access_token=c6b65b8d81265d2fdd3248e5a66ce4974ad4460a11e6ab4e9b303ab4aa1e3a2a"

# 2. 构造消息内容，必须包含你的关键词：告警
data = {
    "msgtype": "text",
    "text": {
        "content": "告警：Python 发送测试成功！数据同步监控已上线。"
    }
}

# 3. 发送请求
headers = {"Content-Type": "application/json"}
response = requests.post(url, data=json.dumps(data), headers=headers)

# 4. 打印结果
print(response.text)