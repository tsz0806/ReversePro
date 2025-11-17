# ================================
# 完整版：支援多輪對話的 Grok API
# ================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import requests
import json
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Grok Mirror API - 多輪對話版",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROK_BASE_URL = "https://grok.ylsagi.com"

HEADERS = {
    "Content-Type": "application/json",
    "Cookie": 'share_token=aaf6c70a7ba8832ae9b09ac055cd1081947d2d897b3ca2b65d826ceeecbcf653; imgID=67e253bdd0b63c582005f9a7; i18nextLng=en; mp_ea93da913ddb66b6372b89d97b1029ac_mixpanel=%7B%22distinct_id%22%3A%2200a70e22-fed7-4713-b4c5-9b16ba9c856f%22%2C%22%24device_id%22%3A%229c284b9a-2aa5-4b8e-886e-78017fc21d9e%22%2C%22%24initial_referrer%22%3A%22https%3A%2F%2Fylsagi.com%2F%22%2C%22%24initial_referring_domain%22%3A%22ylsagi.com%22%2C%22__mps%22%3A%7B%7D%2C%22__mpso%22%3A%7B%7D%2C%22__mpus%22%3A%7B%7D%2C%22__mpa%22%3A%7B%7D%2C%22__mpu%22%3A%7B%7D%2C%22__mpr%22%3A%5B%5D%2C%22__mpap%22%3A%5B%5D%2C%22%24user_id%22%3A%2200a70e22-fed7-4713-b4c5-9b16ba9c856f%22%7D',
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:145.0) Gecko/20100101 Firefox/145.0",
    "Origin": "https://grok.ylsagi.com",
    "Referer": "https://grok.ylsagi.com/",
}

# ================================
# 資料模型（新增對話 ID 欄位）
# ================================

class ChatRequest(BaseModel):
    """
    聊天請求模型
    
    欄位說明：
    - message: 使用者的問題（必填）
    - model: 使用的模型（可選，預設 grok-3）
    - conversation_id: 對話 ID（可選，用於多輪對話）
    - parent_response_id: 上一次的回應 ID（可選，用於多輪對話）
    
    使用範例：
    
    # 第一次對話（新建對話）
    {
        "message": "你好"
    }
    
    # 第二次對話（繼續對話）
    {
        "message": "我剛才說了什麼？",
        "conversation_id": "上次回傳的 conversation_id",
        "parent_response_id": "上次回傳的 response_id"
    }
    """
    message: str
    model: Optional[str] = "grok-3"
    conversation_id: Optional[str] = None  # ⭐ 新增：對話 ID
    parent_response_id: Optional[str] = None  # ⭐ 新增：父回應 ID

class ChatResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# ================================
# 建構請求負載（支援兩種模式）
# ================================

def build_payload_new(message: str, model: str = "grok-3") -> dict:
    """
    建構「新對話」的請求負載
    用於第一次對話
    """
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
        "modelMode": "MODEL_MODE_AUTO",
        "modelName": model,
        "responseMetadata": {},
        "modelConfigOverride": {},
        "modelMap": {},
        "requestModelDetails": {
            "modelId": model
        },
        "returnImageBytes": False,
        "returnRawGrokInXaiRequest": False,
        "sendFinalMetadata": True,
        "temporary": False,
        "toolOverrides": {}
    }

def build_payload_continue(message: str, parent_response_id: str, model: str = "grok-3") -> dict:
    """
    建構「繼續對話」的請求負載
    用於第二次及之後的對話
    
    參數：
        message: 使用者的新問題
        parent_response_id: 上一次的回應 ID（重要！用來串連對話）
        model: 模型名稱
    """
    return {
        "customPersonality": "",
        "disableArtifact": False,
        "disableMemory": False,  # 不停用記憶
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
        "requestModelDetails": {
            "modelId": model,
            "modelMode": "MODEL_MODE_AUTO",
            "modelName": model
        },
        "parentResponseId": parent_response_id,  # ⭐ 關鍵：串連對話的 ID
        "returnImageBytes": False,
        "returnRawGrokInXaiRequest": False,
        "sendFinalMetadata": True,
        "skipCancelCurrentInflightRequests": False,
        "toolOverrides": {}
    }

# ================================
# 解析串流式回應（保持不變）
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
# API 路由端點
# ================================

@app.get("/")
async def root():
    return {
        "name": "Grok Mirror API - 多輪對話版",
        "version": "4.0.0",
        "status": "running",
        "features": [
            "支援單次對話（不傳 conversation_id）",
            "支援多輪對話（傳入 conversation_id 和 parent_response_id）"
        ]
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    智慧聊天端點 - 自動判斷新對話或繼續對話
    
    判斷邏輯：
    1. 如果有 conversation_id 和 parent_response_id → 繼續對話
    2. 如果沒有 → 建立新對話
    
    回傳內容：
    - response: Grok 的回覆
    - conversation_id: 對話 ID（請保存！下次要用）
    - response_id: 回應 ID（請保存！下次要用）
    - is_new_conversation: 是否為新對話（用於除錯）
    """
    try:
        if not request.message:
            return ChatResponse(success=False, error="Message is required")
        
        logger.info(f"收到請求: {request.message}")
        logger.info(f"對話 ID: {request.conversation_id}")
        logger.info(f"父回應 ID: {request.parent_response_id}")
        
        # ===== 關鍵邏輯：判斷是新對話還是繼續對話 =====
        
        is_new_conversation = False
        
        if request.conversation_id and request.parent_response_id:
            # 情況 1：繼續現有對話
            logger.info("模式：繼續對話")
            url = f"{GROK_BASE_URL}/rest/app-chat/conversations/{request.conversation_id}/responses"
            payload = build_payload_continue(request.message, request.parent_response_id, request.model)
            conversation_id = request.conversation_id  # 使用傳入的對話 ID
        else:
            # 情況 2：建立新對話
            logger.info("模式：新對話")
            url = f"{GROK_BASE_URL}/rest/app-chat/conversations/new"
            payload = build_payload_new(request.message, request.model)
            conversation_id = None  # 等待從回應中取得
            is_new_conversation = True
        
        # 準備請求標頭
        headers = HEADERS.copy()
        headers["x-xai-request-id"] = str(uuid.uuid4())
        headers["x-statsig-id"] = "JdqGp+hE6q0WsMpDDLRldv0O6ZNb+Mny24KLm/R/9pJdezRyT5a+PbxEdMFEOTVSTrW47iG05JO2DhUM3iJUk/pqbz4SJg"
        
        logger.info(f"發送請求到: {url}")
        
        # 發送請求
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            stream=True,
            timeout=60
        )
        
        logger.info(f"收到回應，狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            result = parse_streaming_response(response)
            
            # 如果是新對話，從回應中取得 conversation_id
            if is_new_conversation and result.get("conversation_id"):
                conversation_id = result.get("conversation_id")
            
            logger.info(f"解析結果: response_length={len(result.get('response', ''))}")
            
            if not result.get("response"):
                return ChatResponse(
                    success=False,
                    error="No response text extracted",
                    data={
                        "debug_info": {
                            "lines_processed": result.get("debug_line_count", 0),
                            "response_id": result.get("response_id"),
                            "conversation_id": conversation_id
                        }
                    }
                )
            
            # 成功回傳
            return ChatResponse(
                success=True,
                data={
                    "response": result.get("response", ""),
                    "conversation_id": conversation_id,  # ⭐ 重要：回傳給客戶端保存
                    "response_id": result.get("response_id"),  # ⭐ 重要：回傳給客戶端保存
                    "is_new_conversation": is_new_conversation,  # 是否為新對話
                    "message_received": request.message  # 除錯用：確認收到的訊息
                }
            )
        else:
            error_text = response.text[:200]
            logger.error(f"HTTP錯誤 {response.status_code}: {error_text}")
            return ChatResponse(
                success=False,
                error=f"Request failed with status {response.status_code}",
                data={"details": error_text}
            )
            
    except requests.Timeout:
        logger.error("請求逾時")
        return ChatResponse(success=False, error="Request timeout")
    except Exception as e:
        logger.error(f"未知錯誤: {str(e)}", exc_info=True)
        return ChatResponse(success=False, error=f"Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
