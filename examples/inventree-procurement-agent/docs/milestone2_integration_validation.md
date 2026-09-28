# 里程碑 2：隔离实例任务创建与只读预览联调

日期：2026-09-28。固定 InvenTree 源码 `967f7a55d1b27a0536273e02f99ff974db4ee22d`。只在 `inventree-spike` Compose 项目、`127.0.0.1:18080` 和既有专用卷内执行。使用 `real_data_fixture_validation.md` 中 BO-9001、同一 Part 的两条 BuildLine、源库位 5 件、其他库位 7 件和隔离库存 11 件。没有创建采购单、发起审批、改动生产数据或修改 InvenTree 源码。

## 安装与复现

在 `inventree/` 目录运行，先使用 `integration_spike.md` 所载的 `/tmp/inventree-spike.override.yml`。插件源码以只读方式挂载；复制到专用应用卷再安装。安装同一版本号的新代码须显式 `--force-reinstall`。`docker compose exec` 不会运行入口脚本的虚拟环境激活步骤，所以迁移、静态收集和校验脚本应明确使用 `/home/inventree/data/env/bin/python`；直接用系统 `python` 会看不到该插件。

```bash
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  up -d --no-build inventree-dev-db
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  run --rm --no-deps inventree-dev-server sh -c \
  'cp -a /opt/inventree-procurement-plugin/. /home/inventree/data/plugin-src/ && python -m pip install --no-deps --force-reinstall /home/inventree/data/plugin-src'
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
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  exec -T inventree-dev-server /home/inventree/data/env/bin/python \
  src/backend/InvenTree/manage.py shell \
  < ../deepagents/examples/inventree-procurement-agent/plugin/integration/verify_milestone2.py
```

`0002_task_preview` 迁移返回 `OK`。最新插件 JS 与前端 dist 的 SHA-256 均为 `aa8a589b1ba5f269fc3bf0af018442d2a23113f8fead6ede0bd16b43e254e0f2`，隔离静态目录中的文件也一致；实际 GET `/static/plugins/inventree_procurement/procurement-panel.js` 为 200、14533 字节。校验脚本使用 Django 测试 Client 生成真实会话 Cookie、用 Django `get_token` 生成 CSRF Cookie 和 `X-CSRFToken`，随后通过 `urllib` 向运行中的 Web 服务发送真实 HTTP 请求。它每次成功运行会创建一条新的测试分析任务，不会创建采购业务对象。

## HTTP 与持久化结果

| 条件 | 结果 |
| --- | --- |
| 匿名 GET health、GET tasks、POST tasks | 均为 401。 |
| 已登录 `spike_build_reader` POST tasks，缺少 CSRF Cookie/令牌 | 403，错误指出 `CSRF cookie not set`。 |
| `spike_build_denied` POST tasks（有 CSRF）、GET tasks | 均为 403，错误码 `forbidden`。 |
| `spike_build_reader` POST `/plugin/inventree_procurement/tasks/`，JSON `{"build_ids":[1]}`，带 CSRF | 201，状态 `analyzed`、`preview_available:true`，返回预览 URL 和 64 字符快照摘要。 |
| 创建者 GET 任务详情、GET `/tasks/{uuid}/preview/` | 均为 200，摘要与 POST 响应一致。 |
| 匿名 GET 预览 | 401。 |
| 无角色用户及另一位用户 GET 创建者的预览 | 均为 404：详情路由先按 owner 查找，再校验业务权限，以 404 隐藏他人任务。 |
| 重启 Web 容器 | 快照记录仍在，状态 `analyzed`、两条行、需求 10、可用 5、缺口 5 和摘要不变。重启后的浏览器任务列表也可读取持久记录。 |

一次成功的测试任务为 `d1bdbbc9-7bf6-4256-be0b-4a47c72e03df`，摘要 `957cffc83352216bd30d805665f96c2896329c0f8155927bb48b553d5343a077`。快照中的 Build 来源为 `build.Build #1`，`take_from_id=1`；两条来源为 `build.BuildLine #1/#2`，各自 `required/outstanding` 为 `4.00000/6.00000`。Part 2 的 `selected_build_outstanding=10.00000`，`available_stock.value=5.00000`，`preliminary_shortage.value=5.00000`。库存来源注明 `build.BuildLine.available_stock`、Build 上下文 1 与行 `[1,2]`；位置范围注明 `take_from location and descendants`。顶层和缺口字段均带警示：初步缺口未计入在途供应、替代料和可选/消耗性物料策略，不能当采购建议。

## 浏览器结果与权限边界

在采购页 `Plugin Provided → Procurement tasks`，隔离 `spike_owner` 输入生产单 ID `1`、点击“创建分析任务”，页面新增 `ANALYZED` 任务并自动打开只读预览。实际可见 BO-9001、BuildLine 1/2 的需求 4/6、按 Part 汇总的需求 10、可用库存 5、初步缺口 5、来源字段、位置范围和警示。浏览器中的创建任务 UUID 为 `9744b347-9fa9-4ce8-82f8-016be473d629`。

`spike_build_reader` 只有 `build.view` RuleSet：插件 API 可创建与读取分析任务，但 InvenTree 不显示 Purchasing 导航；直接打开采购页显示 `Permission Denied`。这是宿主采购页面的查看权限要求，和插件 API 的 Build/Part/Stock 服务端校验是两层不同检查。没有扩张这个对照用户的权限。

另建隔离非超级用户 `spike_buyer_reader`，只授予 `build.view` 与 `purchase_order.view` RuleSet。实测 `check_user_permission(PurchaseOrder, 'add')=false`；浏览器显示 Purchasing 导航与插件面板，采购单列表不显示“新增采购单”按钮。该用户输入 ID 1 后成功创建并打开分析预览，UUID `2d835a95-d944-4217-a7b5-63657ba9460a`，同样可见需求 4/6、汇总 10、库存 5、缺口 5。生产使用时应给采购分析人员组合授予所需只读角色，并单独限制采购写入权限。

完成后已退出浏览器测试页、使临时浏览器测试密码不可用，执行同一 Compose 前缀的 `down` 停止隔离容器和网络，保留两个专用卷。没有提交或推送。
