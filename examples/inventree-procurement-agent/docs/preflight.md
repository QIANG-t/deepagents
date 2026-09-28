# InvenTree 采购 Agent：开工前核查

核查日期：2026-09-28
上游仓库：`inventree/`，`master`，`967f7a55d1b27a0536273e02f99ff974db4ee22d`（浅克隆）
核查方式：阅读当前检出的源码与仓库文档。尚未启动 InvenTree，也未运行插件。

## 1. 项目定位

InvenTree 已提供库存、生产单、供应商物料和采购单。新增项目的候选目标是**生产采购决策与执行 Agent**：根据多个生产目标收集结构化数据，读取供应商报价等非结构化资料，提出可解释的供应商与采购单分组方案，处理缺失信息，经人工批准后创建待处理采购单并核验结果。

第一版不要把“自动计算缺料”或“创建采购单”写成新增核心能力；现有界面已经提供这些能力。Agent 的价值必须体现在跨对象的信息收集、方案选择、人工澄清及可审计的执行流程上。

### Agent 适配性判断

**只有跨生产单汇总缺料、按规则选最低价并建单时，不应称为 Agent。**这些步骤适合确定性程序。要保留 Agent 方向，必须加入需要基于上下文选择下一步的任务：例如从供应商报价单或邮件中提取价格、包装量、交期及有效期；发现相互冲突或缺失的条件后向人追问；在预算与交付要求变化后重新提出方案。数量、价格计算及规则校验仍由确定性代码执行，模型负责信息理解、工具选择、澄清和方案解释。

若后续无法获得或构造可核验的报价资料与多轮决策案例，应将项目定位为“采购规划扩展”，而不是为简历强行贴 Agent 标签。演示用合成报价须明确标注为模拟数据。

## 2. 已有能力与拟新增能力

| 业务环节 | 当前源码已确认 | 拟新增能力与边界 |
| --- | --- | --- |
| 生产物料 | `build/serializers.py` 的 `BuildLineSerializer` 暴露需求量、已分配、在制、在途、可用及替代库存等字段。 | 汇总多个生产单的需求，保留每个建议所依据的生产单和物料行。跨单合并后的库存分配规则需要先定义并测试。 |
| 建议采购量 | `OrderPartsWizard.tsx` 已按最低库存、生产与销售需求、现货、在途、在制计算 `to_order`。 | 复用或对照现有计算口径；Agent 不自行编造库存数字。须证明跨单建议优于逐行使用原向导。 |
| 下单操作 | 生产物料表已有“Order Parts”入口；向导支持选择数量、供应商物料及采购单；`PurchaseOrderViewSet` 与采购单行 API 支持创建。 | 对多个候选方案作比较，批准后创建 **PENDING** 采购单；记录审批、请求与回查结果，避免重复创建。 |
| 多层 BOM | `Part.getRequiredParts(recursive=True)` 可递归列出所需物料，但返回的是物料集合，不含逐层展开后的总数量。 | 多层 BOM 数量汇总不能直接套用该函数；先以已生成的生产单物料行为第一版输入。 |
| 供应商 | `SupplierPartSerializer` 暴露供应商、可用量、包装量及价格阶梯等信息。 | 读取供应商报价等资料，提取并核对价格、包装量、交期和有效期；当前源码中 `lead_time` 字段被注释，不能仅靠 InvenTree 自动判断交期。 |

关键源码：

- `inventree/src/frontend/src/tables/build/BuildLineTable.tsx`：约 906–925 行，现有采购入口。
- `inventree/src/frontend/src/components/wizards/OrderPartsWizard.tsx`：约 497–558 行，数量与供应商选择；约 638–679 行，建议采购量公式。
- `inventree/src/backend/InvenTree/build/serializers.py`：约 1314–1380 行，生产物料字段。
- `inventree/src/backend/InvenTree/part/models.py`：约 2161–2183 行，递归物料集合。
- `inventree/src/backend/InvenTree/order/api.py`：约 385–400、687–700 行，采购单及行项目 API。

## 3. 数据字段与已知缺口

| 数据 | 已确认来源 | 用途／注意点 |
| --- | --- | --- |
| 生产单、物料行及需求量 | `BuildLineSerializer` 的 `build`、`bom_item`、`quantity`、`part` | 用生产单物料行作为第一版需求输入。 |
| 已分配、在制、在途、可用库存 | 同一序列化器的 `allocated`、`in_production`、`on_order`、`available_stock` 等 | 必须明确这些字段的单位和是否包含本生产单的分配，防止重复扣减。 |
| 全局建议采购量输入 | `PartSerializer` 中的 `minimum_stock`、`required_for_build_orders`、`required_for_sales_orders`、`total_in_stock`、`ordering`、`building` | 现有向导使用这些字段；跨单计算应与其对照，不直接相加两套需求。 |
| 供应商、包装与报价 | `SupplierPartSerializer` 的 `supplier`、`available`、`pack_quantity_native`、`price_breaks` | 价格阶梯和币种的选择规则尚未验证。模型不得把缺失报价当作零价。 |
| 订货倍数 | `SupplierPart.multiple` 模型字段 | 在所查 `SupplierPartSerializer.Meta.fields` 中未出现；若走外部 REST API，需要进一步核对是否能从其他端点取得。 |
| 交期 | `SupplierPart` 中仅见被注释的 `lead_time` | 可从注明来源和有效期的供应商报价中提取，并经人确认；没有可靠来源时从方案评价中移除。 |
| 采购状态 | `PurchaseOrderStatus.PENDING` 与 `PLACED` | Agent 第一版仅创建待处理单，不自动执行“向供应商下单”的状态转换。 |

字段定义位置：`inventree/src/backend/InvenTree/build/serializers.py`、`part/serializers.py`、`company/serializers.py`、`company/models.py`、`order/status_codes.py`。

## 4. 插件可行性：静态核查结果

| 能力 | 源码／文档证据 | 结论 |
| --- | --- | --- |
| 在原界面显示 Agent 面板 | `docs/docs/plugins/frontend.md` 与 `mixins/ui.md` 描述 `UserInterfaceMixin`，并提供 `@inventreedb/ui` 类型和界面组件。 | 有官方扩展点；**未运行验证**构建和挂载。 |
| 提供后端接口 | `docs/docs/plugins/mixins/urls.md` 描述 `UrlsMixin`，插件路由位于 `/plugin/{slug}/`。 | 有官方扩展点；**未运行验证**请求认证和权限。 |
| 保存任务与审批状态 | `docs/docs/plugins/mixins/app.md` 允许自定义 Django 模型，但明确提示深度集成风险；`metadata.md` 可存对象附加信息。 | 技术上可行；独立任务与审批记录更适合自定义模型，必须做迁移及权限验证。 |
| 后台执行 | 仓库使用 Django-Q2；插件文档提供事件和定时任务扩展点。 | 存在执行基础；**未验证**长时间模型调用、重试和幂等策略。 |
| 用户权限 | InvenTree API 文档说明用户权限限制；插件自定义模型需显式实现权限检查。 | 不得假定插件自动继承采购权限；需在接口和审批动作分别验证。 |

**当前首选架构：原生 InvenTree 插件。**新增插件内部仍拆分 Python 后端与 React/TypeScript 前端。先用一个最小插件核验界面挂载、认证接口、任务持久化与权限，再决定是否需要额外的独立 Agent 服务。此前提出的 FastAPI 独立服务尚未通过这些验证，不应写入最终技术栈。

## 5. 下一阶段的通过条件

1. **集成验证**：最小插件能在指定上游提交运行；显示一个面板；已登录用户可调用插件接口；无权限用户被拒绝；任务状态能在重启后恢复。每项保留运行命令和结果。
2. **业务定义**：用固定案例写清跨生产单需求如何合并、库存如何分配、在途订单如何扣减、包装和报价如何比较。缺少供应商数据时明确转人工。
3. **执行契约**：审批绑定方案版本和数据快照；批准前重新核查关键库存；建单请求有幂等键；遇到不确定的网络结果先查询是否已建单，再决定是否重试。
4. **评估基线**：同一案例分别记录原采购向导、确定性采购规划程序与新 Agent 能完成什么。至少覆盖库存充足、部分缺料、已有在途、重复提交、权限不足、缺少报价、报价冲突、用户变更预算或交付条件，以及审批后数据变化。若 Agent 不能在信息理解和条件变化场景中提供可验证的额外能力，就收缩 Agent 定位。
5. **版本与归属**：决定新插件的 Git 仓库结构，固定 InvenTree 上游版本，保留原项目署名和 MIT 许可信息。简历只写亲自实现和实际测出的能力。

在以上条件通过前，目录布局、数据库、模型供应商和 Agent 编排库都保持为待定项。
