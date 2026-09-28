# InvenTree 采购 Agent API 契约（源码核对）

核对基准：`inventree/` 当前检出版本 `967f7a55d1b27a0536273e02f99ff974db4ee22d`（见 `docs/preflight.md`）。本文只核对源码及仓库测试，未启动服务，未对真实服务写入。实施时以部署实例的 `/api/schema/`、`OPTIONS`、只读响应及隔离测试实例复核。

## 1. 可调用端点

所有路径以 `/api/` 为根，末尾斜杠保留。根路由见 `inventree/src/backend/InvenTree/InvenTree/urls.py:53-69,164`。

| 目的 | 方法与路径 | 可用过滤或关键响应 | 证据 |
| --- | --- | --- | --- |
| 生产单列表／详情 | `GET /api/build/`、`GET /api/build/{pk}/` | 列表有 `status`、`active`/`outstanding` 等过滤；按目标生产单 PK 取详情 | `build/api.py:48-86,336-406,1222-1293`; `build/serializers.py:63` |
| 生产物料行 | `GET /api/build/line/?build={pk}`、`GET /api/build/line/{pk}/` | `build`、`bom_item` 过滤。行含 `pk,build,bom_item,part,quantity,consumed,allocated,in_production,scheduled_to_build,on_order,available_stock,available_substitute_stock,available_variant_stock` 等 | `build/api.py:449-456,590-718,1222-1230`; `build/serializers.py:1314-1390,1530-1700` |
| 物料详情／需求 | `GET /api/part/{pk}/`、`GET /api/part/{pk}/requirements/` | 详情含 `minimum_stock,purchaseable,active,total_in_stock,ordering,building,required_for_build_orders,required_for_sales_orders`；需求端点另含 `total_stock,unallocated_stock,allocated_to_*` | `part/api.py:554-568,1709-1737`; `part/serializers.py:535-610,1165-1225` |
| 库存明细 | `GET /api/stock/?part={pk}&include_variants=false` | `part` 默认**包含变体**，精确核对需显式 `include_variants=false`；响应含 `quantity,allocated,status,location,in_stock` 等 | `stock/api.py:596-680,1120-1160,1819-1856`; `stock/serializers.py:315-430` |
| 供应商物料 | `GET /api/company/part/?part={pk}&active=true&supplier_active=true`、`GET /api/company/part/{pk}/` | `supplier,part,SKU,active,primary,available,pack_quantity,pack_quantity_native,in_stock,on_order`；传 `price_breaks=true` 才请求可选报价列表 | `company/api.py:255-315,372-438,537-552`; `company/serializers.py:361-468` |
| 报价阶梯 | `GET /api/company/price-break/?part={supplier_part_pk}` | `quantity,price,price_currency,updated`；也可按 `base_part` 或 `supplier` 过滤 | `company/api.py:441-520,550-566`; `company/serializers.py:327-355,613-655` |
| 采购单 | `GET/POST /api/order/po/`、`GET /api/order/po/{pk}/` | 可按 `supplier`、精确 `reference`、`status`、`outstanding` 过滤 | `order/api.py:109-124,160-220,314-355,385-576,2697-2706`; `order/serializers.py:75-205,383-420` |
| 采购单行 | `GET/POST /api/order/po-line/`、`GET /api/order/po-line/{pk}/` | 可按 `order`、供应商物料 `part`、内部物料 `base_part`、`pending` 过滤 | `order/api.py:579-680,687-815`; `order/serializers.py:281-315,575-775` |

`BuildLineSerializer` 的库存值是带上下文的注解：若按 `build={pk}` 获取列表，生产单 `take_from` 会限制可用库存位置；`allocated` 是该行分配量，`available_stock` 是总库存扣销售及生产分配后的量，不能再无条件扣一次 `allocated`。多个生产单的 `available_stock` 也不能逐行相加。见 `build/api.py:590-718`、`build/serializers.py:1550-1700`。第一版按生产单物料行保留来源，再用内部物料的全局需求字段对照跨单汇总；库存分摊算法仍需固定案例验证。

## 2. 采购草稿写入契约

1. `OPTIONS /api/order/po/` 可取当前实例建议的 `reference`；`POST /api/order/po/` 至少传 `{"reference":"<经校验且唯一的编号>","supplier":<company_pk>}`。`reference` 和 `supplier` 在序列化器中均为必填；`description,target_date,destination,order_currency` 等按业务需要给出。POST 返回 201、`pk`，并把当前用户记录为 `created_by`。`status` 为只读，不能靠 POST 指定；模型默认 `PENDING=10`（尚未向供应商下单）。参考 `order/serializers.py:75-110,383-420`、`order/api.py:109-124`、`order/models.py:718-750`、`order/status_codes.py:8-36`、`order/test_api.py:330-365`。
2. 每个行项目 `POST /api/order/po-line/` 传 `{"order":<po_pk>,"part":<supplier_part_pk>,"quantity":<正数>,"merge_items":false}`。这里 `part` **不是内部 Part PK**，而是 SupplierPart PK；`quantity` 是供应商物料的订货数量，包装换算要先完成。`purchase_price,purchase_price_currency,target_date` 可按已核准报价填写；`auto_pricing` 会按 InvenTree 价格阶梯重算，默认是 `false`。对审计性方案显式给出价格与币种，并显式 `merge_items:false`，再回查响应及订单行。见 `order/serializers.py:575-665,695-775`、`order/api.py:708-760`、`order/test_api.py:1140-1235`。
3. 行项目 `clean()` 要求供应商物料的 `supplier` 与采购单 `supplier` 一致。`build_order` 字段只适用于标为 external 的外协生产单，不能拿它绑定普通生产单的缺料来源；Agent 应在自身审计记录保留生产单与行来源。见 `order/models.py:2246-2310`。
4. `merge_items` 的默认值由 `PURCHASEORDER_MERGE_LINE_ITEMS` 决定；默认合并时，相同 `part,order,target_date,destination` 的既有行会被加数量，且可能重算价格。POST 创建采购单和逐行 POST **不是一个事务**，部分成功、网络结果未知及重复提交需在 Agent 层持久化执行状态、以 `reference`/订单 PK 回查后恢复。源码未提供这组端点的幂等键。见 `order/api.py:708-758`、`order/test_api.py:1130-1235`。
5. 审批前复读行与库存/在途、供应商物料及报价；审批绑定方案版本、数据快照及请求参数。创建后 `GET /api/order/po/{pk}/` 和 `GET /api/order/po-line/?order={pk}` 核验 `status=10`、供应商、行、数量、币种和价格。不得调用 `issue` 动作；它会把待处理单变为已下单状态。状态定义见 `order/status_codes.py:8-36`，动作见 `order/api.py:470-575`。

## 3. 权限与服务端校验

DRF 默认要求已认证，并应用 Django 模型权限、InvenTree 角色权限及 OAuth scope 校验（`InvenTree/settings.py:515-526`）。角色动作映射为 GET→`view`、POST→`add`、PATCH→`change`（`InvenTree/permissions.py:17-28,169-252`）。读取生产单、物料、库存、供应商物料及报价须分别具备对应模型的 `view` 权限；采购单和行项目 POST 须有采购 `add` 权限。仓库测试用 `purchase_order.add` 创建采购单及行、并验证无对应权限时删除行得到 403（`order/test_api.py:330-365,1090-1170`）。UI 的“Order Parts”入口也用 `UserRoles.purchase_order` 的 add 权限隐藏（`frontend/src/tables/build/BuildLineTable.tsx:906-925`）。具体部署的用户规则、OAuth scope 与插件自身接口权限仍须运行时验证；不能仅凭 UI 可见性授权写入。

## 4. 已有向导与 Agent 增量

`OrderPartsWizard.tsx` 已从生产行入口取去重后的可采购物料，可选择／新建 SupplierPart 和采购单，再填写行数量、价格并添加行。它用 `minimum_stock + required_for_build_orders + required_for_sales_orders - total_in_stock - ordering - building` 给初始建议；选择供应商物料后按 `pack_quantity_native` 将原生数量换成订货数量。它不会自动按整包向上取整，界面中还有重新拉取需求量的计算路径，因此 Agent 应显式确定包装取整规则并对照原向导。见 `frontend/src/tables/build/BuildLineTable.tsx:906-925`、`frontend/src/components/wizards/OrderPartsWizard.tsx:40-105,172-456,497-558,638-679`。

Agent 的可验证增量应是跨生产单的来源追踪、报价资料提取及冲突澄清、候选供应商方案比较、审批与恢复执行；单单计算缺料或创建草稿已由现有功能覆盖。

## 5. 尚未由静态源码解决的问题

- `SupplierPart.multiple` 在模型有定义（`company/models.py:868-875`），但 `SupplierPartSerializer.Meta.fields` 没有暴露；`lead_time` 仍被注释（`company/models.py:876`）。外部报价中的最小订货倍数、交期及有效期不能当作 InvenTree 已核实字段。
- 报价阶梯的 `quantity` 单位及 `pack_quantity_native` 换算后的取整、税运费、币种汇率策略需用固定案例和运行实例确认；缺失价格不可当零价。相关字段见 `company/serializers.py:327-355,361-468`、`order/serializers.py:695-775`。
- 当前仓库测试证明基本写入和价格重算路径，但未覆盖本 Agent 的跨单库存分摊、审批后数据变化、断线重试及多单部分成功。实现前应在隔离实例验证最小请求、权限拒绝、OPTIONS 默认值和回查结构。
