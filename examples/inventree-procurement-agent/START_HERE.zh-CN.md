# 从这里开始：InvenTree 采购 Agent

这个目录是基于 Deep Agents 的采购 Agent **开发原型**。目标是汇总生产单缺料、核对供应商报价、解释采购方案，并在有权限的人批准后创建待处理采购单。当前已有接入隔离 InvenTree 实例的原生插件：单张生产单只读预览、真实 DeepSeek 解释、手工粘贴报价抽取，以及[只读采购决策预览](docs/milestone6_decision_preview.zh-CN.md)。审批与真实采购单写入尚未接入。

## 先看哪几个文件

1. [README.md](README.md)：总体流程、已实现能力与明确缺口。
2. [procurement.py](procurement.py)：确定性的数量计算、方案摘要、审批和写入前复核。
3. [agent.py](agent.py)：把只读查询、方案计算和待批准写入封装为 Deep Agents 工具。
4. [inventree_adapter.py](inventree_adapter.py)：读取 InvenTree API 的适配器；写入方法当前关闭。
5. [接口契约](docs/inventree_api_contract.md)与[评测方案](docs/evaluation_plan.md)：业务字段依据及如何证明效果。
6. [第六阶段联调](docs/milestone6_decision_preview.zh-CN.md)：当前插件的完整只读决策链路与不能下单的原因。

## 现在可以亲自运行什么

在 `deepagents/` 仓库根目录运行：

```bash
python3.11 -m unittest discover -s examples/inventree-procurement-agent/tests -v
```

在本目录运行：

```bash
python3.11 -m unittest discover -s evals -p 'test_*.py' -v
python3.11 evals/offline.py
```

第一组检查采购规则和模拟 HTTP 接口；第二组检查评测程序。评测程序不带观测数据运行时会列出支持与未支持的案例，**不会产生 Agent 成绩**。这几项命令不需要模型密钥或 InvenTree 服务。

## 下一阶段的顺序

| 阶段 | 完成标志 |
| --- | --- |
| 1. 隔离开发环境 | InvenTree 的测试实例能启动；只读 API 与权限返回经过实测。见[集成核查](docs/integration_spike.md)。 |
| 2. 只读闭环 | 已接入单张生产单、报价和逐 Part 决策预览；初步缺口可追溯，未知的订货数量与总价保持空值。 |
| 3. 审批与草稿 | 审批记录可持久化；写入前复核数据；断线、重复请求与部分行成功均能恢复；只创建 `PENDING` 草稿。 |
| 4. 效果评测 | 已完成合成报价回归评测；真实匿名报价与原采购向导的完整对照仍待完成。 |

面试展示时，说明 Deep Agents 提供的基础能力，再展示自己实现的业务工具、采购规则、审批边界、接口适配和评测结果。只有真实运行并留下证据的阶段才能写成“已完成”。
