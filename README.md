# 沉浸式精听 Demo 使用指南

本仓库提供基于 FastAPI 的“AI 沉浸式精听”演示，涵盖文本上传、MiniMax 同步 TTS 合成、波纹声纹触发字幕显示、点击字幕解析（6 秒自动消散）、播放/暂停与进度拖拽等功能。前端可通过 `/web` 直接访问，后端同时暴露 `/api/listening` 音频生成接口和 `/ws/chat` WebSocket 会话通道。

## 目录结构
- `backend/`：FastAPI 应用与服务层。
  - `main.py`：接口路由（REST + WebSocket），静态资源挂载、字幕时间轴生成逻辑。
  - `services/voice_service.py`：MiniMax 同步 WebSocket TTS 封装。
  - `services/llm_service.py`：Poe GPT-5-Chat 访问封装（WebSocket 会话使用）。
  - `services/stt_service.py`：Dashscope ASR 封装。
  - `generated_audio/`：TTS 输出目录（已被 `.gitignore`）。
- `frontend/`：静态沉浸式精听界面（黑灰绿配色）。
- `.gitignore`：忽略编译缓存与生成音频。

## 前置条件
- Python 3.9+ 环境。
- 可访问 MiniMax、Poe 与 Dashscope（需有效 API Key）。
-（可选）若要在线上播放生成的 MP3，确保浏览器支持音频播放；无需本地 mpv 播放器。

## 快速开始
1. 克隆仓库并进入目录：
   ```bash
   git clone <your_repo_url>
   cd english-learning-practice
   ```
2. 准备虚拟环境并安装依赖：
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows 用 .venv\\Scripts\\activate
   pip install -r backend/requirements.txt
   ```
3. 配置环境变量（推荐写入根目录下的 `.env` 文件）：
   ```bash
   cat <<'ENV' > .env
   MINIMAX_API_KEY=your_minimax_api_key
   POR_API_KEY=your_poe_api_key
   DASHSCOPE_API_KEY=your_dashscope_api_key
   ENV
   ```
   说明：
   - `MINIMAX_API_KEY` 用于同步 TTS（必填）。
   - `POR_API_KEY` 供 `/ws/chat` 使用 Poe GPT-5-Chat（如只演示精听，可暂留空）。
   - `DASHSCOPE_API_KEY` 用于 ASR 识别（如不跑 WebSocket 语音对话，可暂留空）。
4. 启动后端（默认 8000 端口）：
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```
5. 打开前端体验：浏览器访问 `http://localhost:8000/web`，按照界面提示上传/粘贴文本，点击“生成听力音频”后即可播放，并用声纹/字幕交互。

## 接口说明
### `POST /api/listening`
- **入参**：`{ "text": "需要精听的文本" }`
- **返回**：`audio_url`（服务器保存的 MP3 路径），`subtitles`（基于句子长度的启发式时间轴）。
- **用途**：前端调用以生成听力音频与字幕流。

### 静态资源
- `GET /web`：沉浸式精听 UI。
- `GET /media/<filename>`：访问生成的音频文件（默认保存在 `backend/generated_audio/`）。

### `GET /`（健康检查）
- 返回 `{ "message": "AI IELTS Speaking Assistant Backend" }`，用于确认服务可用。

### `WebSocket /ws/chat`
- 支持上传音频字节 → Dashscope ASR → Poe GPT-5-Chat 生成回复 → MiniMax TTS 返回音频流的会话链路。当前精听 Demo 不需要此通道，但保留以便扩展口语对话训练。

## 前端操作流
1. **加载阶段**：进入 `/web` 时展示声纹动效与佩戴耳机提示，1.4s 后自动淡出。
2. **准备材料**：
   - 直接在文本框粘贴内容，或上传 `.txt` 文件（示例为雅思 2025 真题、6.5-7 分到 8.5 的场景）。
3. **生成音频**：点击“生成听力音频”后，后端调用 MiniMax TTS 合成；完成后自动加载音频与字幕，状态栏提示已生成。
4. **播放与交互**：
   - 点击绿色圆形声纹/波纹切换字幕显示；字幕使用波纹动效开关。
   - 点击任意字幕行弹出解析（重音节奏、口音提示、复述校验），6 秒自动消散。
   - 使用播放/暂停按钮或拖拽进度条跳转，时间轴实时同步。

## 常见问题
- **MiniMax Key 失效或未配置**：`/api/listening` 将返回 500，检查 `.env` 中的 `MINIMAX_API_KEY`。
- **音频未播放**：确认浏览器允许站点播放音频，或等待 `audio` 元数据加载完成（进度条显示总时长后再播放）。
- **生成文件位置**：TTS 输出位于 `backend/generated_audio/`，可定期清理；`.gitignore` 已忽略该目录。

## 测试
- 运行基础语法检查：
  ```bash
  python -m compileall backend
  ```

## 后续可扩展方向
- 将字幕时间戳改为真实对齐（通过 ASR 或 TTS 返回时长）。
- 为 `/ws/chat` 增加前端入口，支持听说一体化训练。
- 增加多语种/多音色选择及生成队列管理。
