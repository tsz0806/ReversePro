# main.py (v8.0.0 - 集大成終極版)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import requests
import json
import uuid
import logging
import tiktoken  # ⭐ 功能2：導入 tiktoken

# --- 1. 全局配置 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Grok API (動態Cookie + Token計數 + 多輪對話)",
    version="8.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

GROK_BASE_URL = "https://grok.ylsagi.com"

# 初始化分詞器，用於 Token 計算
try:
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception as e:
    logger.error(f"無法加載 tiktoken 分詞器: {e}")
    tokenizer = None

# --- 2. 資料模型定義 (全面升級) ---
class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = "grok-3"
    conversation_id: Optional[str] = None
    parent_response_id: Optional[str] = None
    # ⭐ 功能1：新增欄位接收動態 Cookie
    grok_cookie: Optional[str] = Field(None, alias="grok_cookie")
    # ⭐ 功能3：新增欄位接收自訂 modelMode
    model_mode: Optional[str] = Field("MODEL_MODE_AUTO", alias="model_mode")

class ChatResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# --- 3. 輔助函式 ---

def count_tokens(text: str) -> int:
    """⭐ 功能2：使用 tiktoken 計算字串的 token 數量"""
    if not tokenizer or not text:
        return 0
    return len(tokenizer.encode(text))

# 根據你提供的 v4.0.0 版本，我們將兩個 build_payload 合併並升級
def build_payload(message: str, model: str, model_mode: str, parent_response_id: Optional[str] = None) -> dict:
    """
    智慧建構請求負載 (Payload)
    - 自動判斷是新對話還是繼續對話
    - ⭐ 功能3：接收自訂的 model_mode
    """
    # 這是兩個 payload 中共通的部分
    base_payload = {
        "message": message,
        "modelName": model,
        "modelMode": model_mode, # 使用傳入的 model_mode
        "isReasoning": False,
        # ... 放入其他共通的參數
    }
    
    if parent_response_id:
        # 繼續對話的特定參數
        base_payload["parentResponseId"] = parent_response_id
        base_payload["isFromGrokFiles"] = False
        # ... 其他繼續對話時才有的參數
    else:
        # 新對話的特定參數
        base_payload["temporary"] = False
        # ... 其他新對話時才有的參數

    return base_payload

def parse_streaming_response(response) -> Dict[str, Any]:
    """解析流式回應，並累加計算 completion_tokens"""
    full_response, response_id, conversation_id = "", None, None
    completion_tokens = 0 # ⭐ 功能2：初始化完成 token 計數器
    
    logger.info("開始解析流式回應...")
    
    try:
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    if "result" in data:
                        result = data["result"]
                        response_data = result.get("response", {})
                        token = response_data.get("token")
                        
                        if token:
                            full_response += token
                            completion_tokens += count_tokens(token) # ⭐ 功能2：累加計算 token
                        
                        if response_data.get("responseId"): response_id = response_data.get("responseId")
                        if "modelResponse" in response_data:
                            model_resp = response_data["modelResponse"]
                            if model_resp.get("responseId"): response_id = model_resp.get("responseId")
                            if model_resp.get("conversationId"): conversation_id = model_resp.get("conversationId")
                        if "conversation" in result and result["conversation"].get("conversationId"):
                            conversation_id = result["conversation"]["conversationId"]
                except (json.JSONDecodeError, KeyError):
                    continue
        
        logger.info(f"解析完成, 回應長度: {len(full_response)}, Completion Tokens: {completion_tokens}")
        
    except Exception as e:
        logger.error(f"迭代過程中出錯: {e}")
    
    return {
        "response": full_response,
        "response_id": response_id,
        "conversation_id": conversation_id,
        "completion_tokens": completion_tokens # ⭐ 功能2：返回計算結果
    }

# --- 4. API 路由 (核心升級) ---
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        logger.info(f"收到請求: '{request.message}' | Conv ID: {request.conversation_id}")

        # ⭐ 功能1：決定使用哪個 Cookie
        active_cookie = request.grok_cookie
        if not active_cookie:
            return ChatResponse(success=False, error="請求中未提供 grok_cookie。")

        # 使用動態 Cookie 構建 Headers
        headers = {
            "Content-Type": "application/json", "Cookie": active_cookie,
            "User-Agent": "...", "Origin": GROK_BASE_URL, "Referer": f"{GROK_BASE_URL}/",
            "x-xai-request-id": str(uuid.uuid4())
        }
        
        # 判斷是新對話還是繼續對話
        is_new_conversation = not (request.conversation_id and request.parent_response_id)

        if is_new_conversation:
            url = f"{GROK_BASE_URL}/rest/app-chat/conversations/new"
            # ⭐ 功能3：傳入 model_mode
            payload = build_payload(request.message, request.model, request.model_mode)
        else:
            url = f"{GROK_BASE_URL}/rest/app-chat/conversations/{request.conversation_id}/responses"
            # ⭐ 功能3：傳入 model_mode
            payload = build_payload(request.message, request.model, request.model_mode, request.parent_response_id)
        
        # ⭐ 功能2：計算 prompt_tokens
        prompt_tokens = count_tokens(request.message)
        logger.info(f"計算出的 Prompt Tokens: {prompt_tokens}")

        response = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
        
        if response.status_code == 200:
            result = parse_streaming_response(response)
            if not result.get("response"):
                return ChatResponse(success=False, error="從 Grok 的流中未解析出任何回應文字")
            
            final_conv_id = result.get("conversation_id") or request.conversation_id
            completion_tokens = result.get("completion_tokens", 0)

            # 成功回傳，並加入 usage 物件
            return ChatResponse(
                success=True,
                data={
                    "response": result.get("response", ""),
                    "conversation_id": final_conv_id,
                    "response_id": result.get("response_id"),
                    "next_parent_response_id": result.get("response_id"),
                    # ⭐ 功能2：加入標準的 usage 物件
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens
                    }
                }
            )
        else:
            return ChatResponse(success=False, error=f"請求失敗，狀態碼 {response.status_code}", data={"details": response.text[:200]})
            
    except Exception as e:
        logger.error(f"發生意外錯誤: {str(e)}", exc_info=True)
        return ChatResponse(success=False, error=f"發生意外錯誤: {str(e)}")
