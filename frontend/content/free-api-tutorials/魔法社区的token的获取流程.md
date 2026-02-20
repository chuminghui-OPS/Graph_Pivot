# 魔搭社区（ModelScope）Token 获取教程

> **魔搭（ModelScope）** 是国内的 "Hugging Face"，提供丰富的开源模型资源和标准化的 API 调用流程。

---

## 一、访问官网与注册

1. 打开官方网址：<https://www.modelscope.cn>
2. 点击右上角 **「登录/注册」**
3. 推荐使用 **手机号、淘宝、钉钉、GitHub 或阿里云账号** 关联登录

<p align="center"><img src="/tutorial-assets/doc-03/img-001.jpg" width="600"></p>

---

## 二、获取 API Token（SDK 令牌）

1. 登录后，点击右上角头像，选择 **「个人中心」**
2. 在左侧菜单栏找到 **「访问控制」→「访问令牌 (Access Token)」**
3. 点击 **「新增令牌」** 或直接复制现有令牌

<p align="center"><img src="/tutorial-assets/doc-03/img-002.jpg" width="600"></p>

> **快捷链接**：
> - 个人中心：<https://modelscope.cn/my/overview>
> - API 令牌页面：<https://modelscope.cn/my/tokens>

> **注意**：请妥善保管令牌，不要发布在公开代码中。

<p align="center"><img src="/tutorial-assets/doc-03/img-003.jpg" width="600"></p>

---

## 三、寻找模型名称（Model ID）

1. 在首页搜索框搜索感兴趣的模型（如 Qwen、Yi、Llama-3）
2. 进入模型详情页
3. 在页面顶部标题下方，找到类似 `damo/nlp_structbert_sentence-similarity_chinese-base` 的字符串
4. 点击旁边的 **复制图标**，即为代码中需要的 `model_id`

---

## 四、申请 API 服务的 URL

根据模型详情页的接口文档，获取对应的 API 调用地址，配合 Token 即可开始使用。
