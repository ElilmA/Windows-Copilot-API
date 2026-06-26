# Current Context

## Ongoing Tasks
- [Task 1]
- [Task 2]
- [Task 3]

## Known Issues
- [Issue 1]
- [Issue 2]

## Next Steps
- [Next step 1]
- [Next step 2]
- [Next step 3]

## Current Session Notes

- [12:17:06] [Unknown User] 开始排查 Codex 仍返回 WebSocket 401 错误: 用户截图显示回答内容仍为 `[error: Failed to perform, curl: (22) Refused WebSockets upgrade: 401...]`。初步判断：`/v1/responses` 兼容层已恢复，但 Copilot 上游 WebSocket 鉴权/会话 token 失效，错误被 Responses streaming 包装成 assistant 文本返回。接下来检查本地 API 日志、当前 endpoint、Codex 配置是否指向本地/隧道，以及 Copilot session/token 状态。
- [12:15:22] [Unknown User] 完成最小 /v1/responses 兼容层恢复: 已恢复最小 `/v1/responses` 兼容层：新增 `ResponsesRequest`、Responses payload/SSE helpers、`POST /v1/responses` 路由、`previous_response_id` 到 Copilot `conversation_id` 的映射。该路由复用现有完整 prompt 本地保存与 `COPILOT_MAX_PROMPT_CHARS` 预算发送逻辑。未恢复 API_KEY 鉴权、browser backend fallback 等其它历史扩展。验证：`python -m unittest discover -s tests` 通过 10 项；py_compile 通过；git diff --check 仅 Windows 换行提示。API 已重启，Python PID 27108，launcher PID 31124；`GET /v1/models` 返回 200，根路径 endpoints 包含 `/v1/responses`。
- [12:04:01] [Unknown User] 开始恢复最小 /v1/responses 兼容层: 用户中断上一轮文档任务，明确要求恢复最小 `/v1/responses` 兼容层。目标：在当前 upstream/master 基础和已保留 prompt 本地保存/预算发送逻辑上，仅恢复 Codex 所需 Responses API 最小兼容：接受 `input`/`instructions`/`stream`/`previous_response_id`，复用 Copilot chat 调用，支持 non-stream 与 streaming，保留完整 prompt 保存，不恢复 API_KEY 鉴权、browser backend fallback 等其它扩展。
- [11:54:37] [Unknown User] Decision Made: Restore To Upstream And Keep Only Prompt Preservation
- [11:54:07] [Unknown User] 完成 upstream 还原后最小保留不丢内容功能: 已将工作树从用户上一轮中断点继续完成：主线业务代码保持基于 upstream/master (`87baede Readme update`)；没有恢复 `/v1/responses`、API_KEY 鉴权、browser backend fallback 等本地扩展。仅新增 `server/context_manager.py`，在 `/v1/chat/completions` 通过 rate limit 后、调用 Copilot 前保存完整 flattened prompt 到 `.context-store/`，并按 `COPILOT_MAX_PROMPT_CHARS` 发送前后保留的预算内文本。新增配置 `COPILOT_MAX_PROMPT_CHARS`、`COPILOT_CONTEXT_STORE_DIR`，更新 `.gitignore` 和 README。验证：`python -m unittest discover -s tests` 通过 5 项；`python -m py_compile ...` 通过；`git diff --check` 仅 Windows 换行提示；API 已重启，Python PID 9600，launcher PID 1452，`GET /v1/models` 返回 200。
- [11:37:21] [Unknown User] 开始最小移植不截断/不丢内容能力: API 已按当前 upstream 版重启并通过 `/v1/models` 健康检查。现在继续用户原始目标的下一步：在保持业务代码尽量贴近 upstream/master 的前提下，只移植完整 prompt 本地保存与预算发送能力；不恢复 `/v1/responses`、API_KEY 鉴权、browser backend fallback 等其它本地扩展。
- [11:36:38] [Unknown User] 按 upstream 版重启本地 API: 用户要求先重启 API 再继续下一步。当前 master 已 reset 到 upstream/master (`87baede Readme update`)，未移植 smart context。已停止旧 8000 监听进程 PID 6980，并启动当前代码 `python app.py`：PowerShell 外壳 PID 26944，Python/Uvicorn 监听 PID 18440，监听 `127.0.0.1:8000`。验证 `GET http://127.0.0.1:8000/v1/models` 返回 200，模型 `copilot`。
- [Note 1]
- [Note 2]
