# main.py (v9.0.0 - 雙模式終極版)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import requests
import json
import uuid
import time
import logging
import os
import tiktoken

# --- 1. 全局配置 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Grok API (雙模式)", version="9.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

GROK_BASE_URL = "https://grok.ylsagi.com"
# 從環境變數讀取備用 Cookie，用於「模型供應商」模式
FALLBACK_COOKIE = os.getenv("GROK_COOKIE", "your_static_fallback_cookie_if_needed")

try:
    tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception:
    tokenizer = None

# --- 2. 輔助函式 ---
def count_tokens(text: str) -> int:
    return len(tokenizer.encode(text)) if tokenizer and text else 0

# ... (build_payload 和 parse_streaming_response 函式保持不變，但我們稍後會重用它們)

# --- 3. 模式一：「HTTP 工具模式」的相關定義 ---

# 自訂請求模型
class CustomChatRequest(BaseModel):
    message: str
    model: Optional[str] = "grok-3"
    conversation_id: Optional[str] = None
    parent_response_id: Optional[str] = None
    grok_cookie: Optional[str] = Field(None, alias="grok_cookie")
    model_mode: Optional[str] = Field("MODEL_MODE_AUTO", alias="model_mode")

# 自訂回應模型
class CustomChatResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# 為自訂模式編寫的解析函式
def parse_for_custom_api(response) -> Dict[str, Any]:
    full_response, response_id, conversation_id = "", None, None
    completion_tokens = 0
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
                        completion_tokens += count_tokens(token)
                    if response_data.get("responseId"): response_id = response_data.get("responseId")
                    if "modelResponse" in response_data:
                        model_resp = response_data["modelResponse"]
                        if model_resp.get("responseId"): response_id = model_resp.get("responseId")
                        if model_resp.get("conversationId"): conversation_id = model_resp.get("conversationId")
                    if "conversation" in result and result["conversation"].get("conversationId"):
                        conversation_id = result["conversation"]["conversationId"]
            except (json.JSONDecodeError, KeyError): continue
    return {"response": full_response, "response_id": response_id, "conversation_id": conversation_id, "completion_tokens": completion_tokens}

# --- 4. 模式二：「模型供應商模式」的相關定義 ---

# OpenAI 標準請求模型
class OpenAIMessage(BaseModel):
    role: str
    content: str

class OpenAIChatRequest(BaseModel):
    model: str
    messages: List[OpenAIMessage]
    stream: Optional[bool] = True

# 為 OpenAI 模式編寫的流式生成器
async def stream_for_openai_api(prompt: str, prompt_tokens: int):
    url = f"{GROK_BASE_URL}/rest/app-chat/conversations/new"
    headers = {
        "Content-Type": "application/json", "Cookie": FALLBACK_COOKIE,
        "User-Agent": "...", "Origin": GROK_BASE_URL, "Referer": f"{GROK_BASE_URL}/",
        "x-xai-request-id": str(uuid.uuid4())
    }
    payload = {"message": prompt, "modelName": "grok-3", "modelMode": "MODEL_MODE_AUTO"}
    
    try:
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=60) as response:
            response.raise_for_status()
            model_name = "grok-as-provider"
            response_id = f"chatcmpl-{uuid.uuid4()}"
            created_time = int(time.time())
            completion_tokens = 0

            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if "result" in data:
                            response_data = data["result"].get("response", {})
                            token = response_data.get("token")
                            if token:
                                completion_tokens += count_tokens(token)
                                chunk = {
                                    "id": response_id, "object": "chat.completion.chunk", "created": created_time, "model": model_name,
                                    "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}]
                                }
                                yield f"data: {json.dumps(chunk)}\n\n"
                    except (json.JSONDecodeError, KeyError): continue
            
            end_chunk = {
                "id": response_id, "object": "chat.completion.chunk", "created": created_time, "model": model_name,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens}
            }
            yield f"data: {json.dumps(end_chunk)}\n\n"
            yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"OpenAI 模式請求 Grok 失敗: {e}")
        # 返回一個符合 OpenAI 錯誤格式的資訊
        error_payload = {"error": {"message": str(e), "type": "grok_request_error"}}
        yield f"data: {json.dumps(error_payload)}\n\n"
        yield "data: [DONE]\n\n"

# --- 5. API 路由定義 ---

# 路由一：HTTP 工具模式 (自訂 API)
@app.post("/api/chat", response_model=CustomChatResponse)
async def custom_chat(request: CustomChatRequest):
    # (這部分是我們 v8.0.0 的 chat 函數邏輯，保持不變)
    try:
        active_cookie = request.grok_cookie
        if not active_cookie: return CustomChatResponse(success=False, error="請求中未提供 grok_cookie。")

        headers = { "Content-Type": "application/json", "Cookie": active_cookie, "User-Agent": "...", "Origin": GROK_BASE_URL, "Referer": f"{GROK_BASE_URL}/", "x-xai-request-id": str(uuid.uuid4()) }
        
        is_new = not (request.conversation_id and request.parent_response_id)
        if is_new:
            url = f"{GROK_BASE_URL}/rest/app-chat/conversations/new"
            payload = {"message": request.message, "modelName": request.model, "modelMode": request.model_mode}
        else:
            url = f"{GROK_BASE_URL}/rest/app-chat/conversations/{request.conversation_id}/responses"
            payload = {"message": request.message, "modelName": request.model, "modelMode": request.model_mode, "parentResponseId": request.parent_response_id}
        
        prompt_tokens = count_tokens(request.message)
        response = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
        
        if response.status_code == 200:
            result = parse_for_custom_api(response)
            if not result.get("response"): return CustomChatResponse(success=False, error="未解析出回應文字")
            
            final_conv_id = result.get("conversation_id") or request.conversation_id
            completion_tokens = result.get("completion_tokens", 0)
            return CustomChatResponse(success=True, data={
                "response": result.get("response", ""), "conversation_id": final_conv_id,
                "next_parent_response_id": result.get("response_id"),
                "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens, "total_tokens": prompt_tokens + completion_tokens}
            })
        else:
            return CustomChatResponse(success=False, error=f"請求失敗，狀態碼 {response.status_code}", data={"details": response.text[:200]})
    except Exception as e:
        return CustomChatResponse(success=False, error=f"發生意外錯誤: {str(e)}")

# 路由二：模型供應商模式 (OpenAI 相容)
@app.post("/v1/chat/completions")
async def openai_chat_completions(request: OpenAIChatRequest):
    if not FALLBACK_COOKIE or "your_static_fallback_cookie" in FALLBACK_COOKIE:
        async def error_stream():
            error_payload = {"error": {"message": "伺服器未配置備用 Cookie (FALLBACK_COOKIE)。", "type": "configuration_error"}}
            yield f"data: {json.dumps(error_payload)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    user_prompt = ""
    for msg in reversed(request.messages):
        if msg.role == "user":
            user_prompt = msg.content
            break
    
    prompt_tokens = count_tokens(user_prompt)
    return StreamingResponse(stream_for_openai_api(user_prompt, prompt_tokens), media_type="text/event-stream")
