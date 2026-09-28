# 第三里程碑：DeepSeek 只读解释联调与验收

状态：**核心链路已验证，部分失败与并发场景待验证**。日期：2026-09-28。实际结果、任务 ID 与尚未运行的场景见[第三阶段隔离联调记录](milestone3_deepseek_integration_validation.md)。密钥由用户在本机配置到被 Git 忽略的 `.env.local`，只注入隔离服务；不写入仓库或测试工件。

## 当前实现契约

插件后端使用 `langchain_deepseek.ChatDeepSeek`（`deepseek-flash`）和 `deepagents.create_deep_agent`。本 Agent 仅有无参数的只读工具 `read_task_snapshot()`：路由先检查登录、任务 owner、Build/BuildLine/Part/StockItem view 权限，再把该任务已保存的 `preview` 和 `snapshot_digest` 绑定到工具闭包。模型不能指定另一任务、用户或外部查询。Deep Agents 的文件、shell、todo 和子 Agent 工具被排除，执行门禁也拒绝未知工具名。以 `plugin/backend/inventree_procurement_plugin/explanation.py` 和 `views.py` 为准；现有 `agent.py` 三工具离线采购原型不是此接口。[第二里程碑联调](milestone2_integration_validation.md)已验证快照与权限基线。

当前实现**没有具名 `tool_choice` 强制调用**。提示词要求调用一次；运行后代码核验恰有一个模型 `read_task_snapshot` 调用、一个匹配的成功工具结果、工具返回内容等于绑定快照，才缓存最终文本。未调用、重复调用、未知工具或无效文本应失败。DeepSeek 官方 [工具调用指南](https://api-docs.deepseek.com/guides/tool_calls/)说明模型提出调用、客户端实际执行；[Chat Completions API](https://api-docs.deepseek.com/api/create-chat-completion/)定义 `tool_calls` 与调用 ID。[入门文档](https://api-docs.deepseek.com/guides/harness)列出当前模型名和 base URL。这些是协议依据，不表示现有 LangChain 请求设置了 `tool_choice`。

接口为 `GET/POST /plugin/inventree_procurement/tasks/<uuid>/explanation/`。GET 在尚无对应摘要的缓存时返回 409；有缓存时返回 `{"explanation":{"text":"...","model":"deepseek-flash","snapshot_digest":"...","generated_at":"...","tool_calls":[{"name":"read_task_snapshot","status":"success","tool_call_id":"...","result_sha256":"..."}]}}`。POST 要求空请求体和会话 CSRF；成功时持久缓存同结构结果，同摘要重复 POST 返回缓存，生成中返回 409。缺 key 或 AI 可选依赖返回 503；模型或结果校验失败返回 502。当前代码限制快照 32 KiB、输出 600 tokens、每次提供方调用 15 秒、提供方重试 0 次；生成占用 60 秒后可重新领取。缓存只对同一 `snapshot_digest` 有效。成功、缓存、部分权限和 CSRF 路径已在隔离实例实测；其他分支按下表区分。

## 当前必须通过的验收

使用 BO-9001 已持久化快照：BuildLine #1/#2 未满足需求 4/6，同属 Part #2；Build #1 的 `take_from` 库位可用库存 5 **只计一次**，初步缺口为 5。输出需引用 Build、BuildLine、Part、`build.BuildLine.available_stock` 的 Build 上下文与快照摘要，并说明在途、替代料、可选/消耗性物料、供应商报价及交期尚未核实，5 不是可直接下单数量。不得编造供应商、价格、币种、交期、审批或采购单。

| 场景 | 必须观察的结果 |
| --- | --- |
| M3-01 真实工具链 | 授权 owner POST 解释。保留真实 DeepSeek 响应与 Agent 轨迹：模型发出 `read_task_snapshot()`，宿主实际执行一次并返回绑定快照，最终回答产生。持久 `tool_calls` 摘要和实际轨迹一致。模拟 `ToolMessage` 不能当真实模型证据。 |
| M3-02 数值与来源 | 回答正确解释 4+6=10、库位库存 5 只计一次、初步缺口 5，引用两条行、Part、库位范围和摘要，保留“非采购建议”警示。错误相加库存、把全局 12 当此 Build 可用库存，或编造报价/在途均失败。当前代码只校验工具轨迹和文本形状，**语义准确性须独立评测**。 |
| M3-03 缺 key/依赖 | 不注入 `DEEPSEEK_API_KEY` 时 POST 预期 503、GET 仍 409，快照不变、无假解释或外网请求；再用测试替身模拟可选依赖缺失。仅记录 `key_present` 布尔值。 |
| M3-04 模型/工具失败 | 用替身覆盖超时、提供方错误、未调用工具、重复/未知工具、结果不匹配、空或超长文本；预期 502（配置/依赖缺失为 503）、不缓存部分解释并释放占用。提供方 400/401/402/422/429/500/503 按官方 [错误码](https://api-docs.deepseek.com/quick_start/error_codes/)分类，错误原文不回传浏览器。 |
| M3-05 授权与 CSRF | 匿名 401、他人任务 404、owner 失去业务 view 权限 403、无 CSRF 的 POST 403、非空请求体 400。拒绝路径不调用模型或泄露快照。只有 `build.view` 可用插件 API，但采购页另需 `purchase_order.view`。 |
| M3-06 缓存与并发 | 首次成功后 GET 和重复 POST 返回相同 `text/model/snapshot_digest/generated_at/tool_calls`，不再调用模型。并发 POST 只有一个取得生成占用，另一个 409 或读到完成缓存；摘要改变后旧缓存不可见。记录任务 ID、摘要、状态与模型请求计数。 |
| M3-07 重启 | 重启隔离 Web 后，GET 读回持久结果，重复 POST 仍命中同一缓存，`generated_at` 与摘要不变且无新模型请求。DeepSeek [Context Caching](https://api-docs.deepseek.com/guides/kv_cache/)是提供方的请求前缀缓存，不能代替插件数据库缓存。 |
| M3-08 浏览器 | 非超级用户有 `build.view`、`purchase_order.view`、无 `PurchaseOrder.add`；在采购页对自己的任务触发解释并刷新，来源、限制和结果仍可见。已在隔离实例完成创建、生成及缓存展示；结果见联调记录。 |

采购单及行项目新增数必须为零。真实模型成绩、替身测试、第二里程碑的 HTTP/浏览器成绩分别报告。未来增强可包括结构化引用与语义判定器、提供方请求 ID/token/费用脱敏审计、跨进程 exactly-once 计数证明和更多生产单案例；不得把这些写成当前已实现。

## 隔离复现步骤模板

以下是复现框架；本次实际使用了仅引用被忽略 `.env.local` 路径的 `/tmp/inventree-spike.deepseek.override.yml`，具体实测步骤见[联调记录](milestone3_deepseek_integration_validation.md)。先使用 [integration_spike.md](integration_spike.md) 的 `/tmp/inventree-spike.override.yml`，在 `inventree/` 目录执行。安装 AI extra 只改 `inventree-spike` 专用应用卷。不要运行会展开环境变量的 `docker compose config`、`docker inspect` 或带密钥的 shell 跟踪。

```bash
cd /Users/qiang/Mycodex/agent/inventree-agent/inventree
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  up -d --no-build inventree-dev-db
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  run --rm --no-deps inventree-dev-server sh -c \
  'cp -a /opt/inventree-procurement-plugin/. /home/inventree/data/plugin-src/ && python -m pip install --force-reinstall "/home/inventree/data/plugin-src[ai]"'
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  run --rm --no-deps inventree-dev-server python src/backend/InvenTree/manage.py migrate inventree_procurement_plugin --noinput
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  up -d --no-build inventree-dev-db inventree-dev-server
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  exec -T inventree-dev-server /home/inventree/data/env/bin/python \
  src/backend/InvenTree/manage.py shell -c \
  "from plugin.staticfiles import copy_plugin_static_files; copy_plugin_static_files('inventree_procurement')"
```

先不注入 key 启动 Web。对一个已有预览且属于当前测试用户的任务：首次 GET explanation 应为 409；带真实会话与 CSRF、空体的 POST 应为 503。复用现有 `plugin/integration/verify_milestone2.py` 的 `Client.force_login`、`get_token` 和 `urllib` 方法发送真实 HTTP 请求，不打印 Cookie/CSRF。用他人与无权限用户核对 404/403。此阶段不应发生 DeepSeek 请求。

真实模型阶段由用户在本机将 `DEEPSEEK_API_KEY` 写入被 Git 忽略且权限为 `0600` 的 `.env.local`。在 `/tmp` 创建只含该文件路径、不含密钥值的第三份 Compose 覆盖文件：

```bash
cat > /tmp/inventree-spike.deepseek.override.yml <<'YAML'
services:
  inventree-dev-server:
    env_file:
      - /Users/qiang/Mycodex/agent/inventree-agent/deepagents/examples/inventree-procurement-agent/.env.local
YAML
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  -f /tmp/inventree-spike.deepseek.override.yml \
  up -d --no-build inventree-dev-db inventree-dev-server
```

再以 owner 会话发送空体 `POST /plugin/inventree_procurement/tasks/<uuid>/explanation/`，含 CSRF Cookie 与 `X-CSRFToken`；检查 200 和解释字段。重复 GET/POST，制造并发 POST，重启 Web 后再次 GET/POST，比较缓存与模型调用计数。浏览器登录只读采购角色，打开 `Plugin Provided → Procurement tasks` 检查解释交互。收尾用**同样三个** Compose 文件执行 `down`（不带 `-v`）。不要把付费请求藏在自动测试或页面初次加载中。

## 必留证据与当前状态

记录 InvenTree/插件提交、0003 迁移、依赖版本、模型名和参数、owner 与角色、任务 UUID 与快照摘要、每次 GET/POST 状态和脱敏响应、Agent 模型调用与匹配工具消息、实际工具执行次数、最终文本及来源核对、`generated_at`、重启前后缓存一致性、采购单/行项目增量零。若未来取得提供方请求 ID、token 与费用，单独记录；当前接口不暴露这些字段。不得保存密钥、Authorization、Cookie、CSRF 或未脱敏的提供方错误。

本次已验证真实模型调用、解释缓存、重启 GET 与浏览器生成；缺 key 的隔离 HTTP 路径、真实并发、摘要变化、更多 Build 案例及提供方故障注入仍待运行。离线替身测试与[既有评测方案](evaluation_plan.md)的合成案例，均不当作真实模型成绩。
