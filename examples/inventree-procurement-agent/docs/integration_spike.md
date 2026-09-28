# InvenTree × Deep Agents 隔离集成核查

核查日期：2026-09-28。InvenTree 检出版本：`967f7a55d1b27a0536273e02f99ff974db4ee22d`。用户已选择**原生 InvenTree 插件优先**。本次在本机的 `inventree-spike` 隔离实例安装插件，验证认证端点、任务持久化及采购页渲染。Deep Agents 的真实采购数据适配和采购草稿写入仍未接通。没有连接生产服务、创建采购业务数据或修改 InvenTree 源码。

## 已验证结果

| 步骤 | 实际结果 |
| --- | --- |
| 环境 | Docker daemon 29.6.2、Compose v5.3.1 可用。现有其他服务占用 8000 与 5173；核查时 18080 空闲。裸机没有 InvenTree venv 或 Django。 |
| 离线原型 | 在 `deepagents/` 执行 `python3.11 -m unittest discover -s examples/inventree-procurement-agent/tests -v`，19 个合成测试通过。只证明纯 Python 规划与 REST 适配器的离线逻辑。 |
| Deep Agents SDK 导入 | `uv run --no-sync` 失败于缺少 `packaging`：没有先安装依赖。产生的临时 `.venv` 已清理，不能据此判断 SDK 有问题。 |
| 镜像构建 | 先前一次构建在前端 `yarn install` 中主动中止，退出码 130。本次复用缓存后执行 `docker compose ... build inventree-dev-server`，前端编译完成，`inventree-dev-image:latest` 构建成功，退出码 0。 |
| 隔离实例 | 使用 `inventree-spike` Compose 项目、`127.0.0.1:18080` 和两个专用卷。运行 `invoke migrate` 后，Django 系统检查显示 0 个问题，开发服务器监听容器内 8000。 |
| API | 匿名 `GET http://127.0.0.1:18080/api/schema/` 返回 **200**，Content-Type 为 `application/vnd.oai.openapi`；匿名 `GET /api/version/` 返回 **401**、JSON，日志标为 Unauthorized。后者证明请求到达了服务，但没有证明已认证访问可用，也未读到版本号。 |
| 插件安装 | 将只读挂载的插件源码复制到隔离应用数据卷后，用 `pip install --no-deps` 安装 0.1.0。注册表识别 `inventree_procurement`，启用插件配置；`inventree_procurement_plugin.0001_initial` 迁移成功。 |
| 访问控制 | 匿名 GET `/plugin/inventree_procurement/health/` 和 `/tasks/` 均返回 **401**。`spike_owner` 登录后健康端点返回 **200**、`writes_enabled:false`；任务列表和详情返回其测试任务。`spike_other` 的列表为空，对该任务详情返回 **404**。 |
| 持久化 | 创建一条插件任务，UUID `7ce290a5-0270-4069-8c0f-a10b0f538f15`，`build_ids=[12345]`，状态 `created`。重启 Web 容器后，数据库查询和已认证 HTTP 列表仍能读到它。`12345` 只是测试标识，不对应真实 Build。 |
| UI 注册及静态文件 | `/api/plugins/ui/features/panel/?target_model=purchasing` 返回插件面板注册项，source 为 `/static/plugins/inventree_procurement/procurement-panel.js:RenderProcurementPanel`。首次静态 GET 为 **404**；执行 `copy_plugin_static_files('inventree_procurement')` 后为 **200**，`text/javascript`，4194 字节。 |
| 浏览器渲染 | 用隔离测试账号登录 InvenTree 前端，采购页出现 `Plugin Provided → Procurement tasks`；打开后显示测试任务 UUID、`CREATED` 和 `AVAILABLE`。首次登录 **500** 的原因是测试用户缺少 InvenTree `UserProfile`；补建 profile 后成功。 |
| 收尾 | 最终执行 `docker compose ... down`，停止隔离容器；保留 `inventree-spike_inventree-spike-db` 与 `inventree-spike_inventree-spike-app` 两个卷。 |

### 启动过程中碰到并解决的问题

1. 官方 `dev-docker-compose.yml` 默认把源码目录挂进容器，且映射主机 8000。主机 8000 已被占用。首次隔离覆盖尝试将整个源码目录只读挂载，再把专用卷挂到其子目录 `/home/inventree/data`，Docker 因无法在只读父挂载内创建子挂载点而拒绝启动。最终覆盖配置使用**已构建镜像里的源码**，只挂应用数据卷；这适合本次固定版本核查，不提供源码热重载。
2. 开发镜像默认入口脚本指向源码挂载内的 `./contrib/container/init.sh`。改用镜像内的 `./init.sh` 后，Compose 覆盖 `entrypoint` 同时使默认 `command` 为空，容器退出码 0 并循环重启。最终覆盖配置显式设置 `command: ['invoke', 'dev.server', '-a', '0.0.0.0:8000']`。
3. 首次真正启动 Django 时，空数据库报 `relation "django_q_schedule" does not exist`。在**隔离数据库**运行 `invoke migrate` 成功后重启，两个 GET 才得到上述 HTTP 响应。
4. 插件源码以只读方式挂载，直接从该路径执行 `pip install` 时，setuptools 无法写入 egg-info。复制到专用数据卷后安装成功。
5. 手工创建的测试用户没有自动生成 `UserProfile`，浏览器登录触发 `User.profile.RelatedObjectDoesNotExist`。为两个测试用户补建 profile 后，登录与面板渲染成功。

## 可复现命令

在 `inventree/` 目录执行。以下临时覆盖文件只写到 `/tmp`；与默认 Compose 的源码挂载不同，它直接运行本地检出源码构建出的镜像。`!override` 需要本次核查使用的 Compose 版本支持。

```bash
cd /Users/qiang/Mycodex/agent/inventree-agent/inventree
cat > /tmp/inventree-spike.override.yml <<'YAML'
services:
  inventree-dev-db:
    volumes: !override
      - inventree-spike-db:/var/lib/postgresql/data
  inventree-dev-server:
    entrypoint: ['/bin/bash', './init.sh']
    command: ['invoke', 'dev.server', '-a', '0.0.0.0:8000']
    ports: !override
      - '127.0.0.1:18080:8000'
    volumes: !override
      - inventree-spike-app:/home/inventree/data
      - /Users/qiang/Mycodex/agent/inventree-agent/deepagents/examples/inventree-procurement-agent/plugin/backend:/opt/inventree-procurement-plugin:ro
    environment:
      INVENTREE_SITE_URL: http://127.0.0.1:18080
      INVENTREE_GLOBAL_SETTINGS: '{"ENABLE_PLUGINS_APP":true,"ENABLE_PLUGINS_URL":true,"ENABLE_PLUGINS_INTERFACE":true}'
  inventree-dev-worker:
    entrypoint: ['/bin/bash', './init.sh']
    command: ['invoke', 'worker']
    volumes: !override
      - inventree-spike-app:/home/inventree/data
      - /Users/qiang/Mycodex/agent/inventree-agent/deepagents/examples/inventree-procurement-agent/plugin/backend:/opt/inventree-procurement-plugin:ro
    environment:
      INVENTREE_GLOBAL_SETTINGS: '{"ENABLE_PLUGINS_APP":true,"ENABLE_PLUGINS_URL":true,"ENABLE_PLUGINS_INTERFACE":true}'
volumes:
  inventree-spike-db:
  inventree-spike-app:
YAML
```

确认 18080 未占用后，依次构建、迁移、安装插件并启动。数据库卷已经迁移过时，`invoke migrate` 可再次运行；不要对其他 Compose 项目执行该命令。以下命令中的 `COMPOSE` 只作用于 `inventree-spike` 项目。

```bash
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  config --quiet
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  build inventree-dev-server
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  up -d --no-build inventree-dev-db
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  run --rm --no-deps inventree-dev-server invoke migrate
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  run --rm --no-deps inventree-dev-server sh -c \
  'cp -a /opt/inventree-procurement-plugin /home/inventree/data/plugin-src && python -m pip install --no-deps /home/inventree/data/plugin-src'
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  run --rm --no-deps inventree-dev-server python src/backend/InvenTree/manage.py shell -c \
  "from plugin.models import PluginConfig; c,_=PluginConfig.objects.get_or_create(key='inventree_procurement', defaults={'name':'InvenTreeProcurementAgent','active':True}); c.active=True; c.save(no_reload=True)"
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  run --rm --no-deps inventree-dev-server python src/backend/InvenTree/manage.py migrate inventree_procurement_plugin --noinput
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  up -d --no-build inventree-dev-db inventree-dev-server
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  exec -T inventree-dev-server python src/backend/InvenTree/manage.py shell -c \
  "from plugin.staticfiles import copy_plugin_static_files; copy_plugin_static_files('inventree_procurement')"
curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:18080/api/schema/
curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' \
  http://127.0.0.1:18080/api/version/
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  down
```

本次匿名响应分别为 `200` 和 `401`。`down` 不带 `-v`，因此两个专用卷仍在。若需要排查启动，执行同一 Compose 前缀的 `ps` 与 `logs --tail 100 inventree-dev-server`；不要把旧日志中的迁移前报错当作当前启动状态。插件包是安装时复制到数据卷的快照：修改工作区源码后须重新复制、安装、收集静态文件并重启 Web 容器。

## 已验证边界与下一步

| 路径 | 已有基础 | 尚缺 |
| --- | --- | --- |
| 原生插件（已选） | 插件已在隔离实例安装、启用并迁移；认证端点、任务按 owner 隔离、重启持久化、采购页原生面板及静态 JS 均经实测。浏览器面板显示 UUID `7ce290a5-0270-4069-8c0f-a10b0f538f15`、Build IDs `12345`、`CREATED`、`AVAILABLE` 和只读预览提示。 | 尚未连接真实 Build、库存、供应商零件、报价文档，也未验证采购草稿写入或完整审批流程。 |
| 独立 Agent 服务 | `agent.py` 提供 `create_procurement_agent(model, workflow, checkpointer)`；`procurement.py` 提供纯 Python 规划与审批契约；`inventree_adapter.py` 有未连接真实实例的 GET-only 适配器。 | 当前目录没有 HTTP 入口、身份传递、供应与报价回调的真实实现，或持久化审批/幂等记录，不能直接作为服务启动。 |

下一步把 `ProcurementWorkflow.read_snapshot` 接到真实 API 数据，核对 `docs/inventree_api_contract.md` 中的字段和单位。草稿写入应留到审批、重新读取、权限和行级恢复均通过隔离测试后进行。插件扩展点的源码文档位于 `inventree/docs/docs/plugins/frontend.md`、`plugins/mixins/ui.md` 和 `plugins/mixins/urls.md`；当前原型的能力边界见本示例 `README.md`。
