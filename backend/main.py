"""
弹词文字识别 MVP —— 后端服务

运行方式：
  1) cd backend
  2) pip install -r requirements.txt
  3) 复制 .env.example 为 .env，填入你的百度智能云 API Key / Secret Key
  4) uvicorn main:app --reload
     （启动后接口地址为 http://localhost:8000/api/ocr）
"""

import base64
import os
import time

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")

app = FastAPI(title="弹词文字识别 MVP")

# CORS 允许的来源：默认 "*" 方便本地开发和快速上线体验
# 部署上线后，建议在环境变量 CORS_ORIGINS 里设置为你的 Vercel 前端域名（多个用逗号分隔），
# 例如 CORS_ORIGINS=https://tanci-ocr.vercel.app
_cors_origins_env = os.getenv("CORS_ORIGINS", "*")
_cors_origins = ["*"] if _cors_origins_env == "*" else [o.strip() for o in _cors_origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# access_token 有效期较长（约30天），做一个简单的内存缓存，避免每次识别都重新申请
_token_cache = {"token": None, "expires_at": 0.0}


def get_baidu_access_token() -> str:
    """获取百度 API 的访问令牌，带缓存，避免频繁请求"""
    if not BAIDU_API_KEY or not BAIDU_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="未配置百度API Key / Secret Key，请检查 backend/.env 文件",
        )

    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"]:
        return _token_cache["token"]

    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": BAIDU_API_KEY,
        "client_secret": BAIDU_SECRET_KEY,
    }
    resp = requests.post(url, params=params, timeout=10)
    data = resp.json()

    if "access_token" not in data:
        raise HTTPException(status_code=502, detail=f"获取百度access_token失败: {data}")

    _token_cache["token"] = data["access_token"]
    # 保守起见提前5天视为过期，触发刷新
    _token_cache["expires_at"] = now + data.get("expires_in", 2592000) - 60 * 60 * 24 * 5
    return _token_cache["token"]


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/ocr")
async def perform_ocr(file: UploadFile = File(...)):
    """
    接收一张图片，调用百度「通用文字识别（高精度版）」，
    返回整体文字，以及每个文字块的位置(location)和识别置信度(confidence)，
    供前端做「图文对照」和「低置信度标红」使用。
    """

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片文件")

    image_data = await file.read()

    # 百度OCR接口限制：base64编码后的图片不超过4MB
    if len(image_data) > 4 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片过大，请上传小于4MB的图片")

    image_base64 = base64.b64encode(image_data).decode("utf-8")

    access_token = get_baidu_access_token()
    ocr_url = (
        "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
        f"?access_token={access_token}"
    )

    payload = {
        "image": image_base64,
        "detect_direction": "true",   # 自动检测图片方向
        "language_type": "CHN_ENG",   # 中英文混合
        "probability": "true",        # 返回每个文字块的识别置信度
    }

    try:
        response = requests.post(ocr_url, data=payload, timeout=15)
        result = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"调用百度OCR接口失败: {e}")

    if "error_code" in result:
        raise HTTPException(
            status_code=502,
            detail=f"百度OCR返回错误: {result.get('error_msg', result)}",
        )

    words_result = result.get("words_result", [])
    if not words_result:
        return {"success": False, "error": "未识别到文字，请确认图片清晰且包含文字内容"}

    blocks = []
    for item in words_result:
        blocks.append(
            {
                "text": item.get("words", ""),
                "location": item.get("location", {}),  # {left, top, width, height}
                "confidence": item.get("probability", {}).get("average", 1.0),
            }
        )

    full_text = "\n".join(b["text"] for b in blocks)

    return {"success": True, "text": full_text, "blocks": blocks}
