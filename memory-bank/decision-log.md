# Decision Log

## Decision 1
- **Date:** [Date]
- **Context:** [Context]
- **Decision:** [Decision]
- **Alternatives Considered:** [Alternatives]
- **Consequences:** [Consequences]

## Decision 2
- **Date:** [Date]
- **Context:** [Context]
- **Decision:** [Decision]
- **Alternatives Considered:** [Alternatives]
- **Consequences:** [Consequences]

## Restore To Upstream And Keep Only Prompt Preservation
- **Date:** 2026-06-26 11:54:37
- **Author:** Unknown User
- **Context:** 用户要求整体还原成原 fork 项目最新，同时只保留我们做的不截断/不丢内容功能。当前 upstream/master 为 87baede，上一轮本地大改包含多个扩展，用户现在要求收窄范围。
- **Decision:** 将 master 工作树对齐 upstream/master 后，只移植完整 prompt 本地保存与预算发送逻辑；不恢复 /v1/responses、API_KEY 鉴权、browser backend fallback、Responses SSE 等其它本地扩展。
- **Alternatives Considered:** 
  - 保留上一轮所有合入/扩展，但这不符合“就行了”的收窄要求。
  - 只做硬截断避免 text-too-long，但会丢失完整输入，不符合“不丢内容”。
  - 完全发送全文不做预算，但 Copilot 上游仍可能报 text-too-long。
- **Consequences:** 
  - 代码更接近 upstream，维护面更小。
  - .context-store/ 会保存完整 flattened prompt，便于后续恢复/审计。
  - 发送给 Copilot 的单次 prompt 仍是预算内文本，默认 6000 字符；如果上游限制变化可调整 COPILOT_MAX_PROMPT_CHARS。
