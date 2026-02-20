# TokenPony Token 获取教程

> **TokenPony（小马令牌）** 是国内流行的大模型中转/聚合平台，支持通过统一接口调用 GPT-4、Claude 3.5、Gemini、DeepSeek 等多种模型。

---

## 一、访问官网与注册

1. 打开官方网址：<https://tokenpony.com> 或 <https://tokenpony.cn>
2. 点击右上角 **「注册」** 按钮
3. 支持 **邮箱** 或 **微信扫码** 快速登录
4. 注册成功后，建议查看「公告」或「新手引导」，平台有时会赠送测试额度

<p align="center"><img src="/tutorial-assets/doc-08/img-001.jpg" width="600"></p>

---

## 二、申请 API Key（令牌）

1. 在左侧菜单栏点击 **「令牌」(Tokens)**
2. 点击 **「添加新的令牌」**
3. 设置信息：
   - **名称**：随意填写（如 `MyTest`）
   - **过期时间**：建议选「永不过期」
   - **额度**：可设为无限额度，或按需设置
4. 点击提交后，会生成一串以 `sk-` 开头的字符串

<p align="center"><img src="/tutorial-assets/doc-08/img-002.jpg" width="600"></p>

<p align="center"><img src="/tutorial-assets/doc-08/img-003.jpg" width="600"></p>

> **重要**：请务必立即复制并保存，该密钥仅显示一次。

---

## 三、获取 API URL（接口地址）

由于 TokenPony 是聚合平台，接口地址与官方不同：

| 配置项 | 值 |
| --- | --- |
| **API Base URL** | `https://api.tokenpony.com/v1` |

**使用方式**：在代码或聊天工具（如 NextChat、LobeChat）中，将原本的 `https://api.openai.com` 替换为上述地址即可。

<p align="center"><img src="/tutorial-assets/doc-08/img-004.jpg" width="600"></p>

<p align="center"><img src="/tutorial-assets/doc-08/img-005.png" width="600"></p>

<p align="center"><img src="/tutorial-assets/doc-08/img-006.png" width="600"></p>
