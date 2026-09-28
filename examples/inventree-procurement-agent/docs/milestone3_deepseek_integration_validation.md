# 第三里程碑：DeepSeek 只读解释隔离联调

日期：2026-09-28。测试环境为本机 `inventree-spike` 专用 Compose 项目，InvenTree 源码固定在 `967f7a55d1b27a0536273e02f99ff974db4ee22d`，Web 仅监听 `127.0.0.1:18080`。插件安装在该项目的独立应用卷中，迁移 `0003_task_explanation` 成功。用户在被 Git 忽略、权限为 `0600` 的 `.env.local` 中配置 `DEEPSEEK_API_KEY`，隔离 Web 通过只含 `env_file` 路径的第三份 Compose 覆盖文件读取。没有记录或输出密钥。测试结束后关闭临时浏览器页、停用测试账号登录密码，并以 `down`（不带 `-v`）停止该 Compose 项目。

## 实测结果

| 项目 | 观察 |
| --- | --- |
| 真实模型 | 后端经 `ChatDeepSeek` 和 `create_deep_agent` 请求 `deepseek-flash`。两次独立 HTTP 生成成功，耗时 6.31 秒、4.27 秒。返回的中文解释均正确说明两条同物料需求 4+6=10、Build 范围可用库存 5 只计一次、初步缺口 5，并说明报价、交期、在途、替代料和可选/消耗性策略未核实。 |
| 工具证据 | 每个成功结果持久保存一条 `read_task_snapshot` 的 `success` 记录，含实际 `tool_call_id` 和工具结果 SHA-256。后端在写入前验证模型确实请求该工具、对应工具消息匹配且内容为当前任务绑定快照；这比只看模型最终文字多一层校验。没有单独导出原始提供方轨迹。 |
| HTTP 访问控制 | 集成脚本新建 owner 任务后，匿名 GET 为 401、其他用户 GET 为 404、首次 owner GET 为 409、无 CSRF 的 owner POST 为 403；带会话与 CSRF 的 owner POST 为 200。脚本为 `plugin/integration/verify_milestone3.py`，请求实际运行中的 Web 服务。 |
| 缓存与重启 | 同摘要下首次成功后的 GET 和重复 POST 与原结果完全相同。另一条由浏览器生成的任务在重启 Web 后，已认证 HTTP GET 仍为 200，模型、摘要及工具调用 ID 不变。 |
| 浏览器 | 非超级用户 `spike_buyer_reader` 在 Purchasing → Plugin Provided → Procurement tasks 输入 Build ID `1`，创建任务、看只读预览，再主动点击“生成 AI 解释”。页面展示中文解释、`deepseek-flash`、快照摘要、`read_task_snapshot` 调用 ID 与结果哈希；首次进入已有任务时也能显示缓存解释。 |
| 采购写入 | 浏览器生成并重启后，数据库 `PurchaseOrder=0`、`PurchaseOrderLineItem=0`；HTTP 集成脚本还比较了调用前后两表计数，均无新增。该角色无 `PurchaseOrder.add`。 |

测试快照为 Build `BO-9001`，BuildLine #1/#2 均指向 Part #2，需求分别为 `4.00000` 和 `6.00000`，可用库存 `5.00000`，初步缺口 `5.00000`。快照摘要为 `957cffc83352216bd30d805665f96c2896329c0f8155927bb48b553d5343a077`。第二次 HTTP 生成的任务是 `8ed373b8-7fbf-4e46-94ac-39e73985661d`，工具调用 ID `call_00_7Y6JEvOhzQoyJkthNpr67686`，结果哈希 `b62cb0bf962ba32bde1ee3017d57bf3bbcab8c5fea6bc6b160ea45db760d9293`。浏览器任务是 `f6bb724d-1b1c-46d4-bee3-db758dcd5c28`，工具调用 ID `call_00_ReP7sVghpiAR5bTju5yE6177`，结果哈希相同，因为读到的是同一份确定性快照。这些 ID 是测试证据，不是购买交易 ID。

## 离线验证与未完成项

后端单元测试 23 个、前端测试 5 个、示例根目录测试 19 个均通过；前端构建和 Python wheel 构建通过。前端 `dist/procurement-panel.js` 与插件静态副本的 SHA-256 同为 `57be42de4f4971ebef6d6c256e1da5e1c69ee9d313a0fad1f355745b0da38e1b`。单元测试覆盖缺 key、模型或工具返回异常等分支；这类替身测试不等于真实提供方故障演练。

真实并发、快照改变后的缓存失效、缺 key 的隔离 HTTP 测试、更多生产单的语义准确率，以及提供方超时/限流的真实表现尚未验证。当前是一次隔离实例的功能验证，不是生产稳定性或采购决策准确率证明。后续验收场景见[第三阶段计划](milestone3_deepseek_validation_plan.zh-CN.md)。
