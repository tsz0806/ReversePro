# ================================
# 完整版：支援多輪對話 + OpenAI 兼容的 Grok API
# ================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Literal
import requests
import json
import uuid
import logging
import tiktoken
import time
import asyncio
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Grok Mirror API - 雙協議版",
    version="6.0.0",
    description="同時支援原生 API 和 OpenAI 兼容格式"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROK_BASE_URL = "https://grok.ylsagi.com"

# 從環境變數讀取預設 Cookie（可選）
DEFAULT_COOKIE = os.getenv("GROK_COOKIE", 
    'share_token=aaf6c70a7ba8832ae9b09ac055cd1081947d2d897b3ca2b65d826ceeecbcf653; imgID=67e253bdd0b63c582005f9a7; i18nextLng=en; mp_ea93da913ddb66b6372b89d97b1029ac_mixpanel=%7B%22distinct_id%22%3A%2200a70e22-fed7-4713-b4c5-9b16ba9c856f%22%2C%22%24device_id%22%3A%229c284b9a-2aa5-4b8e-886e-78017fc21d9e%22%2C%22%24initial_referrer%22%3A%22https%3A%2F%2Fylsagi.com%2F%22%2C%22%24initial_referring_domain%22%3A%22ylsagi.com%22%2C%22__mps%22%3A%7B%7D%2C%22__mpso%22%3A%7B%7D%2C%22__mpus%22%3A%7B%7D%2C%22__mpa%22%3A%7B%7D%2C%22__mpu%22%3A%7B%7D%2C%22__mpr%22%3A%5B%5D%2C%22__mpap%22%3A%5B%5D%2C%22%24user_id%22%3A%2200a70e22-fed7-4713-b4c5-9b16ba9c856f%22%7D'
)

# 支援的 modelMode 選項
MODEL_MODES = [
    "MODEL_MODE_AUTO",
    "MODEL_MODE_FAST",
    "MODEL_MODE_ACCURATE",
    "MODEL_MODE_REASONING"
]

# ================================
# Token 計算工具
# ================================

class TokenCounter:
    """Token 計算工具類"""
    
    def __init__(self):
        try:
            self.encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
            self.use_tiktoken = True
        except Exception as e:
            logger.warning(f"無法載入 tiktoken，使用簡單計算: {e}")
            self.use_tiktoken = False
    
    def count_tokens(self, text: str) -> int:
        """計算文字的 token 數量"""
        if not text:
            return 0
            
        if self.use_tiktoken:
            try:
                return len(self.encoder.encode(text))
            except:
                pass
        
        # 簡單計算：中文字約 2 個 token，英文單詞約 1 個 token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        english_words = len(text.split())
        return chinese_chars * 2 + english_words

token_counter = TokenCounter()

# ================================
# 原生 API 資料模型
# ================================

class ChatRequest(BaseModel):
    """原生聊天請求模型"""
    message: str
    model: Optional[str] = "grok-3"
    model_mode: Optional[str] = "MODEL_MODE_AUTO"
    cookie: Optional[str] = None
    conversation_id: Optional[str] = None
    parent_response_id: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# ================================
# OpenAI 兼容資料模型
# ================================

class OpenAIMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str

class OpenAIRequest(BaseModel):
    model: str = "grok-3"
    messages: List[OpenAIMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    # 自定義擴展欄位（不影響標準兼容性）
    metadata: Optional[Dict[str, Any]] = {}

class OpenAIChoice(BaseModel):
    index: int
    message: OpenAIMessage
    finish_reason: str

class OpenAIUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class OpenAIResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[OpenAIChoice]
    usage: OpenAIUsage

class OpenAIStreamChoice(BaseModel):
    index: int
    delta: Dict[str, Any]
    finish_reason: Optional[str]

class OpenAIStreamResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[OpenAIStreamChoice]

# ================================
# 建構請求負載
# ================================

def build_payload_new(message: str, model: str = "grok-3", model_mode: str = "MODEL_MODE_AUTO") -> dict:
    """建構新對話的請求負載"""
    return {
        "disableMemory": False,
        "disableSearch": False,
        "disableSelfHarmShortCircuit": False,
        "disableTextFollowUps": False,
        "enableImageGeneration": True,
        "enableImageStreaming": True,
        "enableSideBySide": True,
        "fileAttachments": [],
        "forceConcise": False,
        "forceSideBySide": False,
        "imageAttachments": [],
        "imageGenerationCount": 2,
        "isAsyncChat": False,
        "isReasoning": False,
        "message": message,
        "modelMode": model_mode,
        "modelName": model,
        "responseMetadata": {},
        "modelConfigOverride": {},
        "modelMap": {},
        "requestModelDetails": {
            "modelId": model,
            "modelMode": model_mode,
            "modelName": model
        },
        "returnImageBytes": False,
        "returnRawGrokInXaiRequest": False,
        "sendFinalMetadata": True,
        "temporary": False,
        "toolOverrides": {}
    }

def build_payload_continue(message: str, parent_response_id: str, model: str = "grok-3", model_mode: str = "MODEL_MODE_AUTO") -> dict:
    """建構繼續對話的請求負載"""
    return {
        "customPersonality": "",
        "disableArtifact": False,
        "disableMemory": False,
        "disableSearch": False,
        "disableSelfHarmShortCircuit": False,
        "disableTextFollowUps": False,
        "enableImageGeneration": True,
        "enableImageStreaming": True,
        "enableSideBySide": True,
        "fileAttachments": [],
        "forceConcise": False,
        "forceSideBySide": False,
        "imageAttachments": [],
        "imageGenerationCount": 2,
        "isAsyncChat": False,
        "isFromGrokFiles": False,
        "isReasoning": False,
        "isRegenRequest": False,
        "message": message,
        "metadata": {},
        "modelConfigOverride": {},
        "modelMap": {},
        "request_metadata": {
            "mode": "auto",
            "model": model
        },
        "mode": "auto",
        "model": model,
        "modelMode": model_mode,
        "requestModelDetails": {
            "modelId": model,
            "modelMode": model_mode,
            "modelName": model
        },
        "parentResponseId": parent_response_id,
        "returnImageBytes": False,
        "returnRawGrokInXaiRequest": False,
        "sendFinalMetadata": True,
        "skipCancelCurrentInflightRequests": False,
        "toolOverrides": {}
    }

# ================================
# 解析串流式回應
# ================================

def parse_streaming_response(response) -> Dict[str, Any]:
    """解析 Grok 的串流式回應"""
    full_response = ""
    response_id = None
    conversation_id = None
    line_count = 0
    
    logger.info("開始解析串流式回應...")
    
    try:
        for line in response.iter_lines():
            if line:
                line_count += 1
                try:
                    line_str = line.decode('utf-8')
                    
                    if line_count <= 5:
                        logger.info(f"Line {line_count}: {line_str[:200]}")
                    
                    data = json.loads(line_str)
                    
                    if "result" in data:
                        result = data["result"]
                        
                        if "response" in result:
                            inner_response = result["response"]
                            
                            if "token" in inner_response:
                                token = inner_response["token"]
                                if token:
                                    full_response += token
                            
                            if "responseId" in inner_response:
                                response_id = inner_response["responseId"]
                            
                            if "modelResponse" in inner_response:
                                model_resp = inner_response["modelResponse"]
                                if "message" in model_resp:
                                    full_response = model_resp["message"]
                                    logger.info(f"Got full message: {full_response[:100]}")
                                if "responseId" in model_resp:
                                    response_id = model_resp["responseId"]
                            
                            if inner_response.get("isSoftStop", False):
                                logger.info("Received soft stop")
                                break
                        
                        if "conversation" in result:
                            conv = result["conversation"]
                            if "conversationId" in conv:
                                conversation_id = conv["conversationId"]
                                logger.info(f"Got conversationId: {conversation_id}")
                        
                        if "token" in result:
                            token = result["token"]
                            if token:
                                full_response += token
                        
                        if "conversationId" in result:
                            conversation_id = result["conversationId"]
                        
                        if "responseId" in result:
                            response_id = result["responseId"]
                
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error parsing line: {e}")
                    continue
        
        logger.info(f"Parsing completed. Lines: {line_count}, Response length: {len(full_response)}")
        
    except Exception as e:
        logger.error(f"Error during iteration: {e}")
    
    return {
        "response": full_response,
        "response_id": response_id,
        "conversation_id": conversation_id,
        "debug_line_count": line_count
    }

# ================================
# 核心處理函數
# ================================

async def process_chat_request(
    message: str,
    model: str = "grok-3",
    model_mode: str = "MODEL_MODE_AUTO",
    cookie: Optional[str] = None,
    conversation_id: Optional[str] = None,
    parent_response_id: Optional[str] = None
) -> Dict[str, Any]:
    """處理聊天請求的核心函數"""
    
    # 驗證 modelMode
    if model_mode not in MODEL_MODES:
        logger.warning(f"不支援的 modelMode: {model_mode}，使用預設值 MODEL_MODE_AUTO")
        model_mode = "MODEL_MODE_AUTO"
    
    logger.info(f"處理請求: {message[:100]}")
    
    # 計算輸入 Token
    input_tokens = token_counter.count_tokens(message)
    
    # 判斷是新對話還是繼續對話
    is_new_conversation = False
    
    if conversation_id and parent_response_id:
        logger.info("模式：繼續對話")
        url = f"{GROK_BASE_URL}/rest/app-chat/conversations/{conversation_id}/responses"
        payload = build_payload_continue(message, parent_response_id, model, model_mode)
    else:
        logger.info("模式：新對話")
        url = f"{GROK_BASE_URL}/rest/app-chat/conversations/new"
        payload = build_payload_new(message, model, model_mode)
        is_new_conversation = True
    
    # 準備請求標頭
    headers = {
        "Content-Type": "application/json",
        "Cookie": cookie if cookie else DEFAULT_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "Origin": "https://grok.ylsagi.com",
        "Referer": "https://grok.ylsagi.com/",
        "x-xai-request-id": str(uuid.uuid4()),
        "x-statsig-id": "JdqGp+hE6q0WsMpDDLRldv0O6ZNb+Mny24KLm/R/9pJdezRyT5a+PbxEdMFEOTVSTrW47iG05JO2DhUM3iJUk/pqbz4SJg"
    }
    
    # 發送請求
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        stream=True,
        timeout=60
    )
    
    if response.status_code == 200:
        result = parse_streaming_response(response)
        
        # 如果是新對話，從回應中取得 conversation_id
        if is_new_conversation and result.get("conversation_id"):
            conversation_id = result.get("conversation_id")
        
        response_text = result.get("response", "")
        
        if not response_text:
            raise Exception("No response text extracted")
        
        # 計算輸出 Token
        output_tokens = token_counter.count_tokens(response_text)
        total_tokens = input_tokens + output_tokens
        
        return {
            "response": response_text,
            "conversation_id": conversation_id,
            "response_id": result.get("response_id"),
            "is_new_conversation": is_new_conversation,
            "model_used": model,
            "model_mode_used": model_mode,
            "token_usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens
            }
        }
    else:
        error_text = response.text[:500]
        raise Exception(f"Request failed with status {response.status_code}: {error_text}")

# ================================
# 原生 API 路由
# ================================

@app.get("/")
async def root():
    return {
        "name": "Grok Mirror API - 雙協議版",
        "version": "6.0.0",
        "status": "running",
        "endpoints": {
            "native": {
                "chat": "/api/chat",
                "count_tokens": "/api/count-tokens",
                "model_modes": "/api/model-modes"
            },
            "openai_compatible": {
                "chat": "/v1/chat/completions",
                "models": "/v1/models"
            }
        },
        "features": [
            "支援原生 API 格式",
            "支援 OpenAI 兼容格式",
            "支援多輪對話",
            "支援自定義 Cookie",
            "支援 Token 計算",
            "支援設定 modelMode"
        ]
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """原生 API 聊天端點"""
    try:
        if not request.message:
            return ChatResponse(success=False, error="Message is required")
        
        result = await process_chat_request(
            message=request.message,
            model=request.model,
            model_mode=request.model_mode,
            cookie=request.cookie,
            conversation_id=request.conversation_id,
            parent_response_id=request.parent_response_id
        )
        
        return ChatResponse(
            success=True,
            data=result
        )
        
    except requests.Timeout:
        logger.error("請求逾時")
        return ChatResponse(success=False, error="Request timeout")
    except Exception as e:
        logger.error(f"錯誤: {str(e)}", exc_info=True)
        return ChatResponse(success=False, error=f"Error: {str(e)}")

@app.post("/api/count-tokens")
async def count_tokens(request: Dict[str, str]):
    """計算文字的 Token 數量"""
    text = request.get("text", "")
    tokens = token_counter.count_tokens(text)
    return {
        "text": text,
        "token_count": tokens,
        "method": "tiktoken" if token_counter.use_tiktoken else "simple"
    }

@app.get("/api/model-modes")
async def get_model_modes():
    """取得支援的 modelMode 列表"""
    return {
        "supported_modes": MODEL_MODES,
        "default": "MODEL_MODE_AUTO",
        "descriptions": {
            "MODEL_MODE_AUTO": "自動選擇最適合的模式",
            "MODEL_MODE_FAST": "快速回應模式",
            "MODEL_MODE_ACCURATE": "精確模式",
            "MODEL_MODE_REASONING": "推理模式"
        }
    }

# ================================
# OpenAI 兼容 API 路由
# ================================

@app.post("/v1/chat/completions")
async def openai_chat(request: OpenAIRequest):
    """
    OpenAI 兼容聊天端點
    可直接在 Dify 中作為模型供應商使用
    """
    try:
        # 從 messages 中提取最後一條用戶訊息
        user_message = ""
        system_message = ""
        
        for msg in request.messages:
            if msg.role == "system":
                system_message = msg.content
            elif msg.role == "user":
                user_message = msg.content
        
        if not user_message:
            raise HTTPException(status_code=400, detail="No user message found")
        
        # 如果有系統訊息，可以加到用戶訊息前面
        if system_message:
            user_message = f"{system_message}\n\n{user_message}"
        
        # 從 metadata 中提取自定義參數（如果有）
        metadata = request.metadata or {}
        
        # 處理聊天請求
        result = await process_chat_request(
            message=user_message,
            model=request.model,
            model_mode=metadata.get("model_mode", "MODEL_MODE_AUTO"),
            cookie=metadata.get("cookie"),
            conversation_id=metadata.get("conversation_id"),
            parent_response_id=metadata.get("parent_response_id")
        )
        
        # 如果是串流模式
        if request.stream:
            async def generate_stream():
                # 首先發送角色
                chunk = OpenAIStreamResponse(
                    id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                    created=int(time.time()),
                    model=request.model,
                    choices=[OpenAIStreamChoice(
                        index=0,
                        delta={"role": "assistant"},
                        finish_reason=None
                    )]
                )
                yield f"data: {chunk.json()}\n\n"
                
                # 發送內容（這裡簡化處理，實際應該逐字發送）
                content = result.get("response", "")
                chunk = OpenAIStreamResponse(
                    id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                    created=int(time.time()),
                    model=request.model,
                    choices=[OpenAIStreamChoice(
                        index=0,
                        delta={"content": content},
                        finish_reason=None
                    )]
                )
                yield f"data: {chunk.json()}\n\n"
                
                # 發送結束標記
                chunk = OpenAIStreamResponse(
                    id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
                    created=int(time.time()),
                    model=request.model,
                    choices=[OpenAIStreamChoice(
                        index=0,
                        delta={},
                        finish_reason="stop"
                    )]
                )
                yield f"data: {chunk.json()}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream"
            )
        
        # 非串流模式
        response = OpenAIResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=request.model,
            choices=[OpenAIChoice(
                index=0,
                message=OpenAIMessage(
                    role="assistant",
                    content=result.get("response", "")
                ),
                finish_reason="stop"
            )],
            usage=OpenAIUsage(
                prompt_tokens=result.get("token_usage", {}).get("prompt_tokens", 0),
                completion_tokens=result.get("token_usage", {}).get("completion_tokens", 0),
                total_tokens=result.get("token_usage", {}).get("total_tokens", 0)
            )
        )
        
        return response.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OpenAI endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/models")
async def list_models():
    """
    列出可用的模型
    Dify 在配置模型供應商時可能會呼叫此端點
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "grok-3",
                "object": "model",
                "created": 1677610602,
                "owned_by": "grok",
                "permission": [],
                "root": "grok-3",
                "parent": None
            },
            {
                "id": "grok-2",
                "object": "model",
                "created": 1677610602,
                "owned_by": "grok",
                "permission": [],
                "root": "grok-2",
                "parent": None
            },
            {
                "id": "grok-1",
                "object": "model",
                "created": 1677610602,
                "owned_by": "grok",
                "permission": [],
                "root": "grok-1",
                "parent": None
            }
        ]
    }

# ================================
# 健康檢查（OpenAI 格式）
# ================================

@app.get("/v1/health")
async def openai_health():
    """OpenAI 格式的健康檢查"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
