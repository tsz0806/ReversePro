# ReversePro

## ✨ 升級功能
1. 動態 Cookie：
  - 修改 ChatRequest 模型，增加一個 grok_cookie 欄位。
  - 在 chat 函數中，優先使用從請求傳入的 grok_cookie 來構建請求標頭。

2. Token 計算：
  - 引入 tiktoken 函式庫。
  - 增加 count_tokens 輔助函式。
  - 在 chat 函數中，計算 prompt_tokens。
  - 在 parse_streaming_response 函數中，累加計算 completion_tokens。
  - 在最終的 ChatResponse 中，加入 usage 物件回報 token 數量。

3. 自訂 modelMode：
  - 修改 ChatRequest 模型，增加一個可選的 model_mode 欄位。
  - 修改 build_payload 函式，讓它可以接收並使用傳入的 model_mode，如果沒有提供，則使用預設值。

## ✨ 一個 API，兩種身份

1.  **一個 `/v1/chat/completions` 端點**：
    *   嚴格模仿 OpenAI API。
    *   接收 OpenAI 格式的請求 (`messages` 列表)。
    *   返回 OpenAI SSE 流式格式的響應。
    *   它將使用**寫死在程式碼中**或從**環境變數**讀取的 `Cookie`（因為 Dify 的模型供應商模式無法傳遞自訂 Cookie）。
    *   這個版本為了簡化，將**不處理多輪對話**（每次都是新對話），但會**計算 Token**。

2.  **一個 `/api/chat` 端點**：
    *   使用我們自訂的 API 格式。
    *   接收包含 `message`, `conversation_id`, `grok_cookie`, `model_mode` 等自訂欄位的請求。
    *   返回我們自訂的 JSON 格式響應。
    *   它**支援多輪對話**和所有你需要的自訂功能。

### 這個雙模式版本是如何工作的？

1.  **代碼結構分離**：
    *   我們為兩種模式分別定義了不同的 Pydantic 請求模型 (`CustomChatRequest` 和 `OpenAIChatRequest`)。
    *   我們創建了兩個獨立的 API 路由函數 `custom_chat` 和 `openai_chat_completions`，並將它們綁定到不同的路徑 (`/api/chat` 和 `/v1/chat/completions`)。

2.  **`custom_chat` (HTTP 工具模式)**：
    *   這就是我們之前 v8.0.0 的完整邏輯。
    *   它處理所有你需要的自訂功能：動態 Cookie、多輪對話狀態傳遞、自訂 `modelMode`。
    *   返回一個自訂格式的 JSON。

3.  **`openai_chat_completions` (模型供應商模式)**：
    *   它**只能**使用寫死或從環境變數讀取的 `FALLBACK_COOKIE`，因為 Dify 不會傳遞自訂 Cookie。
    *   它**不處理**多輪對話（每次都是新對話），因為 Dify 的 `messages` 歷史很難直接映射到 Grok 的 `parentResponseId`。
    *   它**會**計算 Token。
    *   它**必須**返回 OpenAI 標準的 SSE 流式數據。

## ✨ 使用方式：

### 1. **原生 API 使用（保持不變）：**

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "model": "grok-3",
    "model_mode": "MODEL_MODE_AUTO",
    "cookie": "your_custom_cookie"
  }'
```

### 2. **OpenAI 兼容格式（可在 Dify 中使用）：**

```bash
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "grok-3",
    "messages": [
      {"role": "user", "content": "你好"}
    ],
    "metadata": {
      "model_mode": "MODEL_MODE_AUTO",
      "cookie": "your_custom_cookie"
    }
  }'
```

### 3. **在 Dify 中配置：**

在 Dify 的「設定」→「模型供應商」→「自定義」中：

```
API Base URL: http://your-server:5000/v1
API Key: any-key-here
模型名稱: grok-3
```

## 主要特點：

1. **雙協議支援**：同時提供原生 API 和 OpenAI 兼容格式
2. **完全兼容**：可以直接在 Dify 中作為模型供應商使用
3. **保留所有功能**：Cookie、Token 計算、modelMode 設定等
4. **串流支援**：OpenAI 格式支援串流回應（SSE）
5. **模型列表**：提供 `/v1/models` 端點供 Dify 查詢

## 安裝依賴：

```bash
pip install fastapi uvicorn requests tiktoken
```

現在您可以：
- 使用原本的 `/api/chat` 進行直接呼叫
- 在 Dify 中透過 `/v1/chat/completions` 作為模型供應商使用

兩種方式可以同時運作，互不影響！


---

<div align="center">

# 0️⃣ 功能更新

</div>


<div align="center">

# 1️⃣ API 調用

</div>



<div align="center">

# 2️⃣ Dify 配置

</div>



<div align="center">

# 3️⃣ Langfuse

</div>
https://cloud.langfuse.com

sk-lf-c5e820c3-e4e0-4926-87a7-d436494c6869
pk-lf-a49f58f4-0cca-4f8d-805b-63f7d6acd9dd

sk-lf-7849095e-f0f1-4c36-bc12-6e1dfca432b3
pk-lf-fdae8353-bb8b-4cd4-9b4f-72b8eb7d01ba
