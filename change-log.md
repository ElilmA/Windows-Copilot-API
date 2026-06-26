# Change Log

## 2026-06-26 11:35:46 +08:00

- 涉及对象：本地运行进程、`.api.pid`、`server.log`、`server.err.log`、`conversation-log.md`、`change-log.md`、Memory Bank。
- 具体变更：按用户要求先重启 API；旧监听进程 PID `6980` 已停止，新 upstream 版 API 已启动。
- 运行状态：PowerShell 启动外壳 PID `26944`，Python/Uvicorn 监听 PID `18440`，监听 `127.0.0.1:8000`。
- 验证结果：`GET /v1/models` 返回 200，响应模型 `copilot`。
- 注意事项：当前业务代码仍是 `upstream/master` 版本；后续才会开始最小移植“不截断/不丢内容”功能。

## 2026-06-26 11:53:00 +08:00

- 涉及文件：`.gitignore`、`README.md`、`server/api.py`、`server/config.py`、`server/context_manager.py`、`tests/test_api_context.py`、`tests/test_context_manager.py`、`conversation-log.md`、`change-log.md`、`memory-bank/*`。
- 具体变更：新增 `server/context_manager.py`，完整保存 flattened prompt 到本地，再返回预算内 upstream prompt；在 `server/api.py` 的 `/v1/chat/completions` 路由中接入该逻辑。
- 配置变更：新增 `COPILOT_MAX_PROMPT_CHARS`（默认 `6000`，`0` 表示发送全文）和 `COPILOT_CONTEXT_STORE_DIR`（默认 `.context-store`）。
- 文档与忽略：README 记录长 prompt 保存与预算发送行为；`.gitignore` 忽略 `.context-store/`、本地 key、pem、日志和 pid 文件。
- 测试变更：新增上下文纯逻辑测试与路由级 fake client 测试，确认完整 prompt 已保存，发送给 Copilot 的文本不超过预算且保留开头/最新请求。
- 验证结果：`python -m unittest discover -s tests` 通过 5 项；`py_compile` 通过；`git diff --check` 无实质错误，仅 Windows 换行提示；API 已重启并通过 `/v1/models` 健康检查。

## 2026-06-26 12:17:00 +08:00

- 涉及文件：`server/api.py`、`server/schemas.py`、`server/openai_format.py`、`tests/test_responses_api.py`、`README.md`、`conversation-log.md`、`change-log.md`、`memory-bank/*`。
- 具体变更：恢复最小 `POST /v1/responses` 兼容层；支持 `input`、`instructions`、`stream`、`previous_response_id`、`conversation_id`；复用 Copilot `client.chat()` / `client.stream()`。
- 响应变更：新增最小 Responses 非流式 `response` payload；流式输出包含 `response.created`、`response.output_text.delta`、`response.completed` 和 `data: [DONE]` 等 Codex 需要的完成事件。
- 状态映射：新增 `_response_conversations`，把 Responses `id` 映射到 Copilot `conversation_id`，支持 `previous_response_id` 续聊。
- 测试变更：新增 `tests/test_responses_api.py`，覆盖 prompt 转换、非流式映射、长 prompt 保存/预算发送、流式 completed + DONE。
- 验证结果：`python -m unittest discover -s tests` 通过 10 项；`py_compile` 通过；`git diff --check` 仅 Windows 换行提示；API 已重启，`/` endpoint 列表包含 `/v1/responses`。
