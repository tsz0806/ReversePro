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

### 如何使用

部署這個 `v9.0.0` 版本的 `main.py` 後，你的單一 API 服務就擁有了兩種能力：

*   **當你需要完整的多輪對話和動態 Cookie 功能時**：
    *   在 Dify 中使用「HTTP 工具模式」。
    *   將 `HTTP 請求` 節點的 URL 設定為 `.../api/chat`。
    *   搭建我們之前討論的完整工作流。

*   **當你想要在任何 Dify 應用中快速、便捷地使用，且不介意每次都是新對話時**：
    *   在 Dify 中使用「模型供應商模式」。
    *   去 `設置 -> 模型供應商` 添加一個新模型。
    *   將 `API 基礎 URL` 設定為 `.../v1`。
    *   在 `main.py` 的 `FALLBACK_COOKIE` 變數中填入一個有效的 Cookie（或者在部署平台的環境變數中設定 `GROK_COOKIE`）。

這個雙模式的設計，讓你的專案在**靈活性**和**易用性**之間達到了完美的平衡。你可以根據不同的應用場景，選擇最適合的整合方式。
