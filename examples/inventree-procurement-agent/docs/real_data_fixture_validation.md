# InvenTree 真实数据与权限隔离验证

日期：2026-09-28。源码固定在 `inventree/` 的 `967f7a55d1b27a0536273e02f99ff974db4ee22d`。仅使用 `inventree-spike` Compose 项目、`127.0.0.1:18080` 和两个专用卷。执行脚本为 `plugin/integration/seed_real_data.py`；没有修改 InvenTree 源码或其他 Docker 项目。

## 可重复 fixture

先按 `integration_spike.md` 的覆盖配置启动专用数据库与 Web 容器，再从 `inventree/` 目录显式执行：

```bash
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  up -d --no-build inventree-dev-db inventree-dev-server
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  exec -T inventree-dev-server python src/backend/InvenTree/manage.py shell \
  < ../deepagents/examples/inventree-procurement-agent/plugin/integration/seed_real_data.py
docker compose --project-name inventree-spike --project-directory . \
  -f contrib/container/dev-docker-compose.yml -f /tmp/inventree-spike.override.yml \
  down
```

脚本检查 `INVENTREE_SITE_URL=http://127.0.0.1:18080`，只创建或更新 `SPIKE-*` 标记的物料、库位、库存及角色，并使用有效生产单编号 `BO-9001`。它为测试用户建立 InvenTree `UserProfile`，密码设为不可用，再通过 Django 测试 Client 生成会话 Cookie，向运行中的 Web 服务发送真实 HTTP GET。Cookie 不输出。`manage.py shell` 中 Build 的 post-save 自动建行钩子未运行，因此脚本显式调用可防重复的 `build.create_build_line_items()`。连续执行两次后，仍是同一 Build 和两条行项目。`down` 不带 `-v`；数据保留在 `inventree-spike` 专用卷。

| 数据 | 实测值 |
| --- | --- |
| 生产单 | `BO-9001`，PK 1，成品 Part PK 1，生产数量 2，`take_from=SPIKE-SOURCE`（库位 PK 1） |
| BOM / BuildLine | BOM `SPIKE-A` 每成品用 2，行 PK 1 需求 4；BOM `SPIKE-B` 每成品用 3，行 PK 2 需求 6。两行均指向组件 Part PK 2。 |
| 库存 | `SPIKE-SOURCE` 中状态 OK 数量 5；`SPIKE-OTHER` 中状态 OK 数量 7；`SPIKE-SOURCE` 中状态 QUARANTINED 数量 11。隔离状态库存不计入 `in_stock`。 |
| 用户 | `spike_build_reader` 仅加入 `SPIKE-BUILD-VIEW` 组，授予 `build.view` RuleSet；`spike_build_denied` 没有角色。二者均非 staff、非 superuser、没有可用密码。 |

## 实际请求与响应

下表是脚本用已认证会话发给隔离 Web 服务的真实 GET 的关键字段。数字是该专用卷首次建 fixture 的 PK；若重建卷，应以脚本输出的 PK 为准。

| 请求 | `spike_build_reader` | `spike_build_denied` |
| --- | --- | --- |
| `GET /api/build/1/` | 200：`{pk:1, reference:"BO-9001", part:1, quantity:2, take_from:1}` | 403 |
| `GET /api/build/line/?build=1` | 200：两行分别 `{pk:1, part:2, quantity:4, allocated:0, available_stock:5}` 和 `{pk:2, part:2, quantity:6, allocated:0, available_stock:5}` | 403 |
| `GET /api/build/line/1/` | 200：同一行的 `available_stock:12` | 403 |
| `GET /api/stock/?part=2&include_variants=false` | 200：库存数量 5、7、11；前两条 `in_stock:true`，隔离状态那条 `in_stock:false` | 403 |
| `GET /api/part/2/` | 200：`total_in_stock:12, unallocated_stock:12, required_for_build_orders:10` | 403 |
| `GET /api/part/2/requirements/` | 200：`total_stock:12, unallocated_stock:12, required_for_build_orders:10` | 403 |

模型方法 `BuildLine.allocated_quantity()` 在两行均返回 0；`unallocated_quantity()` 分别返回 4 和 6。没有创建采购单或进行任何写入端点请求。

## 对读取算法的约束

1. `BuildLine` 的 `part` 是 `bom_item.sub_part` 属性，不是 BuildLine 的外键字段。数据库唯一约束是 `(build, bom_item)`，同一 Build 可因不同 BOM 行产生两条指向同一 Part 的需求。来源行须保留，按 Part 计算总需求时须去重库存并汇总需求：本例需求 `4+6=10`，来源库位可用库存只有 5，不能把两行各自的 `available_stock=5` 相加得 10。
2. `GET /api/build/line/?build=1` 的查询传入 source Build，`BuildLineSerializer.annotate_queryset` 根据 `take_from` 限定库位及其子库位。单行详情的 `get_source_build()` 返回 `None`，同一行的 `available_stock` 因而是全局 12。两种响应不可混用。`available_stock` 注解按 `total_stock - allocated_to_sales_orders - allocated_to_build_orders` 计算并截到零；不能再次无条件扣当前行的 `allocated`。
3. Stock 的“可用”先受 `StockItem.IN_STOCK_FILTER` 控制：数量须大于零，不能已分配给销售、客户、其他装配、已消耗或正在生产，状态须属于 `AVAILABLE_CODES`。本例状态 75 的隔离库存 11 不计入 12。全局 `Part.total_stock` 与指定 `take_from` 的 BuildLine `available_stock` 服务于不同范围。
4. `users.permissions.check_user_permission(user, Build, 'view')` 会考虑 InvenTree RuleSet；裸 `user.has_perm('build.view_build')` 不能代替它。本例 reader 的 `check_user_role('build','view')`、`check_user_permission(Build,'view')` 都是 `true`，但 `user.has_perm('build.view_build')` 是 `false`，真实 HTTP 仍为 200。denied 的上述检查均为 `false`，HTTP 为 403。reader 的 `check_user_permission(PurchaseOrder,'add')` 是 `false`。插件服务端读取应调用 InvenTree 的 helper，并分别检查所需 Build、Part、Stock 等模型；采购写入应独立检查采购权限、审批和最新数据。源码见 `InvenTree/permissions.py` 的 `RolePermission` 与 `users/permissions.py` 的 `check_user_permission`。

本 fixture 没有销售分配、生产分配、变体、替代料、父子库位、外部库位或跨生产单。它验证了两行同料去重、来源库位过滤、库存状态以及角色访问的基本边界；更复杂的可用量与采购决策仍需单独案例。
