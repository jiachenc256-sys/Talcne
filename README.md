# 弹词文字识别助手 · MVP

这是第一阶段MVP：上传一张清晰的弹词刻本图片 → 调用百度OCR识别 → 左图右文对照校对。

- 想先在自己电脑上跑起来试试 → 看下面「本地运行」
- 想部署上线，得到一个真实网址让别人也能用 → 看 [`DEPLOY.md`](./DEPLOY.md)

```
tanci-ocr-mvp/
├── backend/          FastAPI 服务，负责调用百度OCR
│   ├── main.py
│   ├── requirements.txt
│   └── .env.example  复制为 .env 并填入你的百度Key
└── frontend/          Vue3 + Vite 页面，负责上传图片和展示结果
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.js
        └── App.vue
```

## 本地运行

## 准备工作

1. 安装 [Python 3.9+](https://www.python.org/)、[Node.js 18+](https://nodejs.org/)
2. 注册 [百度智能云](https://cloud.baidu.com/)，实名认证后开通「文字识别」服务，
   在控制台创建应用，获取 **API Key** 和 **Secret Key**
   （免费额度足够MVP阶段测试使用）

## 第一步：启动后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env      # 然后编辑 .env，填入你的 API Key / Secret Key
uvicorn main:app --reload
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即代表启动成功。
可以在浏览器打开 http://localhost:8000/api/health 确认返回 `{"status":"ok"}`。

## 第二步：启动前端

```bash
cd frontend
npm install
npm run dev
```

终端会提示一个本地地址，通常是 http://localhost:5173，用浏览器打开即可。

> 注意：本项目的前端文件已经写好，**不需要**再运行 `npm create vue@latest`，
> 直接 `npm install` 安装依赖、`npm run dev` 启动即可。

## 使用

1. 点击「选择图片」上传一张清晰的弹词刻本照片或扫描图
2. 点击「开始识别文字」，等待几秒
3. 左侧是原图，右侧是识别出的文字：
   - 鼠标悬停在文字上，左图对应的文字块会高亮，方便逐字核对原文
   - 置信度较低的文字会标红，提示你重点校对
   - 下方文本框里的全文可以直接编辑修改

## 已实现 vs 后续计划

**已实现（第一阶段MVP）**
- 图片上传、OCR识别接口（步骤1）
- 基础上传/展示页面（步骤2）
- 左图右文对照、悬停联动高亮、低置信度标红（步骤3）

**尚未实现，可作为下一阶段**
- 识别结果的手动编辑保存/导出（目前编辑框内容不会持久化）
- 针对弹词刻本字体、竖排版式的专用模型微调
- 批量上传、历史记录、多用户账号体系

## 常见问题

- **前端点击识别后报错"无法连接后端服务"**：确认 `uvicorn main:app --reload`
  是否仍在运行，以及是否是 8000 端口。
- **识别返回"未配置百度API Key"**：检查 `backend/.env` 是否已正确创建并填写。
- **图片识别不准**：百度通用OCR并非针对古籍刻本训练，竖排、异体字、模糊拓印
  效果有限，这也是后续需要微调专用模型的原因。
