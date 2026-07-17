"""
弹词文字识别 MVP —— 后端服务

运行方式：
  1) cd backend
  2) pip install -r requirements.txt
  3) 复制 .env.example 为 .env，填入你的百度智能云 API Key / Secret Key，
     以及百度翻译开放平台的 APP ID / 密钥（如果要用翻译功能）
  4) uvicorn main:app --reload
     （启动后接口地址为 http://localhost:8000/api/ocr）
"""

import base64
import hashlib
import os
import random
import time

import pymupdf
import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")

# 共享密钥：只有带上这个口令的请求才会被接受，用来挡住"随手扫到网址就乱调用"的脚本/爬虫。
# 注意：这不是真正的账号密码保护——前端是纯静态网站，这个值最终会被打包进公开的JS代码里，
# 懂行的人打开浏览器"检查"面板还是能看到，只是能挡住大部分不会专门逆向这个网站的自动化滥用。
# 留空（不设置）则不做校验，方便本地开发；部署上线时建议设置成一个随机字符串。
APP_SHARED_SECRET = os.getenv("APP_SHARED_SECRET", "")

# 百度翻译开放平台的Key，跟上面OCR的Key是两套完全不同的东西，
# 在 https://fanyi-api.baidu.com 单独申请，叫 APP ID / 密钥（不叫API Key/Secret Key）
BAIDU_TRANSLATE_APP_ID = os.getenv("BAIDU_TRANSLATE_APP_ID", "")
BAIDU_TRANSLATE_SECRET_KEY = os.getenv("BAIDU_TRANSLATE_SECRET_KEY", "")

# PDF最多处理的页数：免费版OCR接口是逐页调用的，页数太多会很慢、也容易把免费额度用光，
# 先用一个保守的上限保护一下，之后有需要可以调大。
MAX_PDF_PAGES = 10

# 百度OCR接口限制：base64编码后的图片不超过4MB
MAX_IMAGE_BYTES = 4 * 1024 * 1024

# PDF原始文件大小上限（渲染前），避免超大文件把服务器内存耗尽
MAX_PDF_BYTES = 20 * 1024 * 1024

# 百度翻译单次请求的文本长度上限（官方要求控制在6000字节以内）
MAX_TRANSLATE_BYTES = 6000

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

# ---- 简单的接口保护：限流 + 共享密钥 ----
# 目的是防止免费额度（百度OCR每月1000次、百度翻译每月200万字符）被脚本/爬虫刷爆。

# 内存滑动窗口限流：同一个IP在时间窗口内最多允许多少次请求。
# 注意：这个状态存在内存里，Render免费实例只有一个进程，够用；
# 如果以后升级成多实例部署，各实例的内存不共享，限流会不准，需要换成Redis等外部存储。
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 20
_rate_limit_state: dict[str, list[float]] = {}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(request: Request) -> None:
    ip = _get_client_ip(request)
    now = time.time()
    timestamps = _rate_limit_state.setdefault(ip, [])
    while timestamps and now - timestamps[0] > _RATE_LIMIT_WINDOW_SECONDS:
        timestamps.pop(0)
    if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="请求太频繁了，请稍后再试")
    timestamps.append(now)


def verify_app_secret(x_app_token: str = Header(default="")) -> None:
    # 没配置密钥就跳过校验，方便本地开发；部署上线建议一定要配置
    if APP_SHARED_SECRET and x_app_token != APP_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="未授权的请求")

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


def ocr_image_bytes(image_bytes: bytes) -> list[dict]:
    """
    把一张图片的原始字节丢给百度「通用文字识别（高精度版）」，
    返回每个文字块的 text / location / confidence 列表。
    这是图片识别和PDF逐页识别共用的核心逻辑。
    """
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片过大，请上传小于4MB的图片")

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

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
        response = requests.post(ocr_url, data=payload, timeout=20)
        result = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"调用百度OCR接口失败: {e}")

    if "error_code" in result:
        raise HTTPException(
            status_code=502,
            detail=f"百度OCR返回错误: {result.get('error_msg', result)}",
        )

    blocks = []
    for item in result.get("words_result", []):
        blocks.append(
            {
                "text": item.get("words", ""),
                "location": item.get("location", {}),  # {left, top, width, height}
                "confidence": item.get("probability", {}).get("average", 1.0),
            }
        )
    return blocks


def render_pdf_page_to_png(doc: "pymupdf.Document", page_index: int, dpi: int = 200) -> bytes:
    """把PDF的某一页渲染成PNG图片字节，供OCR和前端预览使用"""
    page = doc.load_page(page_index)
    zoom = dpi / 72  # PDF默认是72dpi，按目标dpi算缩放倍数
    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    png_bytes = pixmap.tobytes("png")

    # 如果渲染出来的图超过百度接口的4MB限制，降低dpi重新渲染一次
    if len(png_bytes) > MAX_IMAGE_BYTES and dpi > 100:
        return render_pdf_page_to_png(doc, page_index, dpi=150)

    return png_bytes


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/ocr")
async def perform_ocr(
    file: UploadFile = File(...),
    _rate_limit: None = Depends(check_rate_limit),
    _auth: None = Depends(verify_app_secret),
):
    """
    接收一张图片或一个PDF文件，调用百度OCR识别文字。

    - 图片：识别一次，返回单页结果
    - PDF：逐页渲染成图片再分别识别，返回每一页的结果（含该页渲染出的图片，供前端预览用）

    统一的返回结构：
    {
      "success": true,
      "type": "image" | "pdf",
      "text": "全部页面拼接起来的全文",
      "pages": [
        {
          "page": 1,
          "text": "这一页的文字",
          "blocks": [{ "text", "location", "confidence" }, ...],
          "image": "data:image/png;base64,...."   # 仅PDF会有这个字段，图片模式前端本来就有原图不需要
        },
        ...
      ]
    }
    """

    is_pdf = (file.content_type == "application/pdf") or (
        file.filename and file.filename.lower().endswith(".pdf")
    )
    is_image = file.content_type and file.content_type.startswith("image/")

    if not is_pdf and not is_image:
        raise HTTPException(status_code=400, detail="请上传图片或PDF文件")

    raw_bytes = await file.read()

    if is_image:
        blocks = ocr_image_bytes(raw_bytes)
        if not blocks:
            return {"success": False, "error": "未识别到文字，请确认图片清晰且包含文字内容"}
        full_text = "\n".join(b["text"] for b in blocks)
        return {
            "success": True,
            "type": "image",
            "text": full_text,
            "pages": [{"page": 1, "text": full_text, "blocks": blocks}],
        }

    # ---- PDF 分支 ----
    if len(raw_bytes) > MAX_PDF_BYTES:
        raise HTTPException(status_code=400, detail="PDF文件过大，请上传小于20MB的文件")

    try:
        doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无法打开这个PDF文件: {e}")

    page_count = doc.page_count
    if page_count == 0:
        raise HTTPException(status_code=400, detail="这个PDF没有可识别的页面")
    if page_count > MAX_PDF_PAGES:
        raise HTTPException(
            status_code=400,
            detail=f"PDF页数过多（{page_count}页），目前MVP阶段最多支持{MAX_PDF_PAGES}页，请拆分后重试",
        )

    pages = []
    all_text_parts = []
    for i in range(page_count):
        png_bytes = render_pdf_page_to_png(doc, i)
        blocks = ocr_image_bytes(png_bytes)
        page_text = "\n".join(b["text"] for b in blocks)
        image_data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("utf-8")

        pages.append(
            {
                "page": i + 1,
                "text": page_text,
                "blocks": blocks,
                "image": image_data_url,
            }
        )
        all_text_parts.append(f"—— 第{i + 1}页 ——\n{page_text}")

    doc.close()

    if not any(p["blocks"] for p in pages):
        return {"success": False, "error": "未识别到文字，请确认PDF清晰且包含文字内容"}

    return {
        "success": True,
        "type": "pdf",
        "text": "\n\n".join(all_text_parts),
        "pages": pages,
    }


class TranslateRequest(BaseModel):
    text: str
    to: str = "en"  # 目标语言代码，比如 en（英语）、jp（日语）、kor（韩语）


@app.post("/api/translate")
async def translate_text(
    payload: TranslateRequest,
    _rate_limit: None = Depends(check_rate_limit),
    _auth: None = Depends(verify_app_secret),
):
    """
    调用百度翻译「通用文本翻译API」，把识别出来的中文翻译成目标语言。
    这是一套独立于OCR的Key（APP ID + 密钥），需要单独在
    https://fanyi-api.baidu.com 申请。
    """
    if not BAIDU_TRANSLATE_APP_ID or not BAIDU_TRANSLATE_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="未配置百度翻译 APP ID / 密钥，请检查后端环境变量 BAIDU_TRANSLATE_APP_ID / BAIDU_TRANSLATE_SECRET_KEY",
        )

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="没有可翻译的文字")
    if len(text.encode("utf-8")) > MAX_TRANSLATE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="待翻译文字过长（单次最多约2000个汉字），请分段翻译，比如一次翻译一页",
        )

    # 百度翻译的签名规则：md5(appid + 待翻译文本 + salt + 密钥)
    salt = str(random.randint(32768, 65536))
    sign_raw = f"{BAIDU_TRANSLATE_APP_ID}{text}{salt}{BAIDU_TRANSLATE_SECRET_KEY}"
    sign = hashlib.md5(sign_raw.encode("utf-8")).hexdigest()

    params = {
        "q": text,
        "from": "zh",
        "to": payload.to,
        "appid": BAIDU_TRANSLATE_APP_ID,
        "salt": salt,
        "sign": sign,
    }

    try:
        response = requests.post(
            "https://fanyi-api.baidu.com/api/trans/vip/translate",
            data=params,
            timeout=15,
        )
        result = response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"调用百度翻译接口失败: {e}")

    if "error_code" in result:
        raise HTTPException(
            status_code=502,
            detail=f"百度翻译返回错误 {result.get('error_code')}：{result.get('error_msg', '')}",
        )

    translated = "\n".join(item.get("dst", "") for item in result.get("trans_result", []))
    return {"success": True, "translated": translated}
