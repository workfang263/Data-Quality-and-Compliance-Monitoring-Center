from flask import Flask, request
app = Flask(__name__)

@app.route("/callback")
def cb():
    code = request.args.get('code')
    state = request.args.get('state')
    
    # 在终端打印（方便查看）
    print("\n" + "="*50)
    print("✅ 收到 TikTok 回调！")
    print("="*50)
    if code:
        print(f"📋 CODE: {code}")
    else:
        print("⚠️  警告：没有收到 code，可能是直接访问了回调地址")
    if state:
        print(f"📋 STATE: {state}")
    print("="*50 + "\n")
    
    # 在浏览器显示
    if code:
        return f"""
        <html>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: green;">✅ 授权成功！</h1>
            <h2>请复制下面的 CODE：</h2>
            <div style="background: #f0f0f0; padding: 20px; margin: 20px; border-radius: 5px;">
                <code style="font-size: 18px; color: #333;">{code}</code>
            </div>
            <p style="color: #666;">这个 code 已经打印在你的 Flask 终端窗口了</p>
        </body>
        </html>
        """
    else:
        return f"""
        <html>
        <body style="font-family: Arial; padding: 50px; text-align: center;">
            <h1 style="color: orange;">⚠️ 没有收到 code</h1>
            <p>可能是直接访问了回调地址，请通过授权 URL 访问</p>
        </body>
        </html>
        """

app.run(host="0.0.0.0", port=8000)