# Commander + Executors Workflow

## 核心原则

**One Commander, N Executors.** 项目包含 2+ 硬件外设时使用此模式。

### Commander 职责（主对话）

1. 理解整个项目 — 用户要做什么？哪个 MCU？哪些外设？数据流怎么走？
2. 收集缺失信息 — 遵循 Rule 0，问引脚、总线配置、时序要求
3. 设计分层架构 — 模块拆分（.h/.c 文件）、层间接口结构体、数据流
4. 分解为子任务 — 每个子任务 = 一个独立的 Agent prompt
5. 分发给 Executor agents — 独立任务并行，依赖任务串行
6. 验证结果 — 分层正确、接口一致、命名规范、无重复代码

### Executor 职责（Agent 子任务）

每个 Executor 处理一个子任务。prompt 必须包含：
- **要做什么** — 具体文件、具体函数签名
- **接口契约** — 必须使用的结构体类型
- **约束** — 命名规范、分层规则、代码风格
- **参考文件** — 如 "Read references/hal-driver-template.md"
- **HAL 头文件** — 正确的 `#include`

---

## Sub-task Decomposition Protocol

### Step 1: 列出所有模块
```
output: module_list = [ModuleA, ModuleB, ModuleC, ...]
```

### Step 2: 分析依赖关系
对每个模块：
- 消费哪些结构体？（输入接口）
- 生产哪些结构体？（输出接口）
```
output: dependency_graph = {ModuleA: [consumes IMU_Data_t], ModuleB: [produces IMU_Data_t]}
```

### Step 3: 构建执行层
- Layer 0（并行）：无未生产依赖的模块 → 同时启动
- Layer 1（Layer 0 之后）：依赖 Layer 0 输出的模块 → 同时启动
- Layer N：重复直到所有模块调度完成
```
output: execution_plan = [[ModuleA, ModuleC], [ModuleB], [main.c]]
```

### Step 4: 为每个模块构建 executor prompt
- 包含：文件列表、接口契约（精确的结构体定义）、HAL 头文件、参考文件
- 一个模块一个 agent，不要打包不相关的模块
```
output: agent_prompts[] → dispatch via Agent tool
```

---

## Executor Prompt 模板

```
你是嵌入式开发 Executor。你的任务是写 [文件列表]。

## 硬件配置
- 芯片: [从 .ioc 读取]
- 外设: [引脚、总线参数]

## 接口契约（必须使用这些类型）
[粘贴结构体定义]

## 约束
- #include "[正确的 HAL 头文件]"
- 命名: Module_Action (PascalCase)
- 结构体: Module_Xxx_t
- 注释: 中文, @brief @param @return
- 错误处理: early return

## 参考
- Read references/hal-driver-template.md
- Code style: 嵌入式项目/ads1115库/

## 要写的内容
[具体函数签名和功能描述]
```

---

## Commander 验证清单

所有 Executor 完成后检查：

- [ ] 分层架构正确（无跨层调用）
- [ ] 结构体接口一致（相同类型定义、相同字段名）
- [ ] 命名规范统一
- [ ] 无重复代码
- [ ] `#include` 路径正确
- [ ] CubeMX USER CODE BEGIN/END 约束被遵守
- [ ] HAL 头文件匹配芯片系列
