# InvenTree × Deep Agents 最小集成核查

核查日期：2026-09-28。InvenTree 源码固定为 `967f7a55d1b27a0536273e02f99ff974db4ee22d`。本文的“已验证”只指本机实际执行的命令；源码提供的能力与后续步骤另列。端到端集成未打通，未连接运行中的 InvenTree，也未创建采购单。

## 当前结论

| 路径 | 当前具备 | 当前缺口 | 下一步判断 |
| --- | --- | --- | --- |
| 原生 InvenTree 插件 | 官方 `UserInterfaceMixin` 可注入面板；`UrlsMixin` 可挂 `/plugin/{slug}/` 路由。当前仓库的采购向导已覆盖建草稿基本操作。 | 本示例没有插件包、数据库任务模型、认证端点、UI 构建或运行实例验证；插件接口权限须显式检查。 | 优先做**最小插件**：一个只读面板、一个登录态接口、一个可持久化任务，验证权限及重启恢复。通过后把本示例工作流放到插件后端或经插件调用。 |
| 独立 Agent 服务 | `agent.py` 提供 `create_procurement_agent(model, workflow, checkpointer)`；`procurement.py` 有纯 Python 规划与审批契约。可通过 InvenTree REST API 设计适配器。 | 目录内没有 HTTP 服务、InvenTree REST 适配器、身份传递、持久化审批/幂等记录或 CORS/反向代理配置。当前不能把它当可启动的独立服务。 | 若插件内运行模型和后台任务经实测有依赖冲突或时限问题，再把模型运行移至独立服务；插件仍负责 InvenTree 用户授权、审批和写入边界。 |

选型依据：插件的 UI 与 URL 扩展点见 `inventree/docs/docs/plugins/frontend.md`、`plugins/mixins/ui.md`、`plugins/mixins/urls.md`；示例能力边界见本目录 `README.md`、`agent.py`、`procurement.py`。此表是静态架构判断，尚非端到端集成结论。

## 本机实际执行记录

| 步骤 | 命令或检查 | 结果 |
| --- | --- | --- |
| Docker 工具与 daemon | `docker compose version`; `docker info --format '{{.ServerVersion}}'` | 已验证：Compose v5.3.1，daemon 29.6.2。 |
| 官方开发 Compose 解析 | 在 `inventree/` 执行 `docker compose --project-directory . -f contrib/container/dev-docker-compose.yml config --quiet` | 已验证：退出码 0。省略 `--project-directory .` 时失败，Compose 把 env 文件解析成 `contrib/container/contrib/container/docker.dev.env`。 |
| 隔离覆盖配置解析 | 使用下文覆盖配置，通过 `-f - config --quiet` 输入 | 已验证：退出码 0。仅证明配置语法可解析，没有证明服务启动。 |
| 端口 | `docker ps --format '{{.Names}} {{.Ports}}'`；`lsof -nP -iTCP:18080 -sTCP:LISTEN` | 已验证：本机已有容器占用 8000、5173；原开发配置的 `8000:8000` 会冲突。18080 在核查时无监听进程。 |
| 本地裸机依赖 | 检查 `inventree/dev/venv/bin/python`、InvenTree 配置、`deepagents/libs/deepagents/.venv`，用系统 Python 查 Django | 已验证：均未就绪；系统 Python 无 Django。不能直接执行 `invoke dev.server`。 |
| 离线工作流 | 在 `deepagents/` 执行 `python3 -m unittest discover -s examples/inventree-procurement-agent/tests -v` | 已验证：8 个合成测试通过，0.001 秒；仅测试纯 Python 工作流，不证明 InvenTree 或模型接入。 |
| Deep Agents SDK 导入 | 在 `deepagents/libs/deepagents/` 执行 `uv run --no-sync python -c 'from deepagents import create_deep_agent'` | 失败：缺少 `packaging`；`--no-sync` 新建空 `.venv` 而没有安装依赖。已清理该临时环境；不能据此推断 SDK 有缺陷。 |
| InvenTree 开发镜像 | `docker compose --project-name inventree-spike --project-directory . -f contrib/container/dev-docker-compose.yml build inventree-dev-server` | 已实际尝试：系统与 Python 依赖阶段完成，进入 `invoke int.frontend-compile --extract` 的 `yarn install`，在依赖链接阶段按本次核查的时间界限主动中止，退出码 130。没有得到完成镜像，不能声称服务可启动。中止前的 peer dependency 警告不是构建失败原因。 |

### 本机隔离启动配置（待运行验证）

在 `inventree/` 下执行。下面的覆盖配置已通过标准输入送给 Compose，且 `config --quiet` 返回 0；它把数据库和应用数据放进不同的隔离卷，使源代码挂载为只读，并改用 18080 端口：

```bash
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f - config --quiet <<'YAML'
services:
  inventree-dev-db:
    volumes: !override
      - inventree-spike-db:/var/lib/postgresql/data
  inventree-dev-server:
    ports: !override
      - '127.0.0.1:18080:8000'
    volumes: !override
      - ./:/home/inventree:ro
      - inventree-spike-app:/home/inventree/data
    environment:
      INVENTREE_SITE_URL: http://127.0.0.1:18080
  inventree-dev-worker:
    volumes: !override
      - ./:/home/inventree:ro
      - inventree-spike-app:/home/inventree/data
volumes:
  inventree-spike-db:
  inventree-spike-app:
YAML
```

本次只验证了覆盖语法。要继续启动，先把上面从 `services:` 到 `inventree-spike-app:` 的 YAML 内容保存为 `/tmp/inventree-spike.override.yml`，不要把 `docker compose` 命令行或末尾 `YAML` 保存进去。然后运行：

```bash
cd /Users/qiang/Mycodex/agent/inventree-agent/inventree
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  config --quiet
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  build inventree-dev-server
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  up -d --no-build inventree-dev-db inventree-dev-server
curl -i http://127.0.0.1:18080/api/version/
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  down
```

上述重新构建、`up`、`curl`、`down` 是后续命令，尚未跑通。开发镜像包含 Python、Node 和前后端构建，首次构建可能很慢。只使用隔离卷，不复用现有数据库；`down` 不带 `-v`，因此不会删除已有测试数据。

## 给初学者的下一步

1. 先完成隔离实例的 `GET /api/version/` 和 `GET /api/schema/`；记录 HTTP 状态、InvenTree 版本及服务日志。若失败，先修容器启动，再处理 Agent。不要在已有生产服务上运行迁移或测试写入。
2. 用官方插件创建器或手工最小插件建立一个仅返回固定文本的面板和 `/plugin/{slug}/health/`。确认登录用户可访问、匿名用户被拒绝、无采购权限用户看不到审批动作。插件自定义视图不能假设自动继承采购权限。
3. 增加本地持久化任务和审批记录，重启容器后确认记录还在；再接 `ProcurementWorkflow` 的只读 `read_snapshot`，按 `docs/inventree_api_contract.md` 核对字段与单位。先只展示方案和缺失信息，不提交采购单。
4. 最后在隔离数据库用测试账号验证草稿写入：审批绑定方案摘要，写前重读，按供应商分组创建 `PENDING=10` 采购单与行，回查每行，演练断线和部分成功。当前原型不具备行级恢复，补齐前不要用真实采购数据。

`deepagents` SDK 应在 `deepagents/libs/deepagents/` 按 `libs/DEVELOPMENT.md` 执行 `uv sync --all-groups` 后再检验 `create_deep_agent` 导入。若将工作流做成独立服务，还需新建 HTTP 入口及 InvenTree 适配器，并验证由插件传递的用户身份与权限；当前目录没有可直接执行的服务命令。
