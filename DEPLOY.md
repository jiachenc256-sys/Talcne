# 部署上线指南：得到一个真实网址

目标：后端部署到 **Render**（免费，不需要信用卡），前端部署到 **Vercel**（免费），
最终你会得到一个真实的 `https://xxx.vercel.app` 网址，任何人都能打开使用。

整个过程大约需要20-30分钟，其中大部分是等待自动构建的时间。

---

## 准备：把代码推到 GitHub

Render 和 Vercel 都是通过连接 GitHub 仓库来部署的，所以第一步是建仓库。

```bash
cd tanci-ocr-mvp
git init
git add .
git commit -m "第一阶段MVP"
```

然后去 [github.com](https://github.com) 新建一个仓库（New repository），仓库名随意，比如 `tanci-ocr-mvp`，
创建时不要勾选"添加README"（避免冲突）。创建后，GitHub 会给你几行命令，形如：

```bash
git remote add origin https://github.com/你的用户名/tanci-ocr-mvp.git
git branch -M main
git push -u origin main
```

依次执行，代码就上传到 GitHub 了。**注意**：`.env` 文件已经在 `.gitignore` 里，
不会被上传，你的百度Key不会泄露到公开仓库，这是故意这样设计的。

---

## 第一步：部署后端到 Render

1. 注册 [Render](https://render.com/)（用 GitHub 账号登录最方便，不需要信用卡）
2. 点击 **New +** → **Web Service**
3. 选择你刚才创建的 GitHub 仓库，授权 Render 访问
4. 配置项目（如果 Render 没有自动读取到 `render.yaml`，就手动填写下面这些）：
   - **Root Directory**: `backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free
5. 展开 **Environment Variables**，添加：
   - `BAIDU_API_KEY` = 你的百度智能云API Key
   - `BAIDU_SECRET_KEY` = 你的百度智能云Secret Key
   - `CORS_ORIGINS` = `*` （先用 `*` 跑通，等前端部署好后再改成具体域名，见下方"收尾"）
6. 点击 **Create Web Service**，等待几分钟完成构建

完成后，Render 会给你一个地址，形如：`https://tanci-ocr-backend.onrender.com`。
打开 `https://你的地址.onrender.com/api/health`，看到 `{"status":"ok"}` 就说明后端上线成功了。

> **免费版有个限制**：闲置15分钟后服务会"休眠"，之后第一次请求需要等待30-60秒唤醒，
> 属于正常现象，不用担心。

---

## 第二步：部署前端到 Vercel

1. 注册 [Vercel](https://vercel.com/)（同样用 GitHub 账号登录最省事）
2. 点击 **Add New** → **Project**，选择同一个 GitHub 仓库并导入
3. 配置项目：
   - **Root Directory**: 点 Edit，选择 `frontend`
   - Framework Preset：Vercel 会自动识别成 **Vite**，保持默认即可
   - **Build Command**: `npm run build`（默认）
   - **Output Directory**: `dist`（默认）
4. 展开 **Environment Variables**，添加一项：
   - `VITE_API_BASE` = 你第一步拿到的 Render 后端地址（例如 `https://tanci-ocr-backend.onrender.com`，注意不要在结尾多加斜杠）
5. 点击 **Deploy**，等待1-2分钟

完成后 Vercel 会给你一个地址，形如：`https://tanci-ocr-mvp.vercel.app`，打开就能直接使用。

---

## 收尾：收紧后端的跨域权限（建议但非必须）

MVP阶段 `CORS_ORIGINS=*` 完全没问题。如果之后想更规范一点：

1. 回到 Render 的项目设置，把 `CORS_ORIGINS` 改成你的 Vercel 地址，
   例如 `https://tanci-ocr-mvp.vercel.app`
2. 保存后 Render 会自动重新部署（几十秒）

这样就只有你的前端页面能调用后端接口，其他网站没法白嫖你的百度OCR额度。

---

## 之后怎么更新

以后改了代码，只需要：

```bash
git add .
git commit -m "描述你改了什么"
git push
```

Render 和 Vercel 都配置了自动部署，push 之后会自动重新构建上线，不用再手动操作。

---

## 常见问题

- **前端页面能打开，但点"开始识别"报错/转圈不动**：八成是 `VITE_API_BASE` 没填对，
  或者后端刚好在"休眠唤醒"中，等一会儿重试。
- **Render 部署失败，日志里报找不到 main.py**：检查 Root Directory 是否填的是 `backend`。
- **想要不休眠、更快的免费方案**：目前免费平台里 Render 已经是不需要信用卡里比较友好的了，
  如果之后用户变多、对速度要求变高，可以考虑升级 Render 的付费实例（$7/月起）。
