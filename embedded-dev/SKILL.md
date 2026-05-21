---
name: embedded-dev
description: >
  嵌入式软件开发助手，用于 STM32 项目的新建、重构、优化和代码编写。
  使用 Keil MDK + STM32CubeMX HAL 库进行开发。
  触发条件：任何涉及嵌入式相关代码的任务，包括重构代码、优化代码、写新功能、修复 bug。
  前置条件：用户已用 CubeMX 生成基础代码，需要明确说明需求和引脚功能。
  不适用于：前端/后端代码、非嵌入式项目。
  工作模式：主 agents 协调 + 多子 agents 协作（类似 FreeRTOS 模块化设计）
  Hooks 机制：每个模块完成后触发代码检查，整体完成后触发编译，编译通过后触发整体检查。
  最终输出：完整可编译的嵌入式代码 + README.md 文档
---

# Embedded Development Skill

## 概述

本 skill 用于嵌入式软件开发，采用**主 agents 协调 + 多子 agents 协作**的架构，类似 FreeRTOS 的模块化设计。

适用于：STM32 项目重构、代码优化、新功能开发、Bug 修复等。

---

## 工作流程

### 1. 需求确认阶段（必须）

在开始编写代码前，**必须明确以下信息**：

**必须确认的信息：**

- 用户的具体需求（什么功能？解决什么问题？）
- CubeMX 已生成的基础代码位置
- 引脚配置和功能定义
- 使用的外设（I2C、SPI、UART、定时器等）
- 是否使用 FreeRTOS
- 编译工具链和编译命令

**如果需求不明确，必须追问用户，不得盲目开始工作**

### 2. 架构设计阶段

主 agents 完成以下工作：

1. 理解整体需求
2. 分析 CubeMX 生成的代码结构
3. 设计模块划分方案（模仿 FreeRTOS 的模块化结构）
4. 制定代码风格规范（参照参考项目）

**目录结构约定：**

```
项目根目录/
├── Core/                    ← CubeMX 生成的基础代码
│   ├── Inc/
│   └── Src/
├── Drivers/                 ← HAL 驱动库
├── MDK-ARM/                 ← Keil 项目目录
│   ├── Application/         ← 应用层（App_ 前缀）
│   ├── common/              ← 通用算法（Com_ 前缀）
│   ├── interface/           ← 硬件接口层（Int_ 前缀）
│   └── freeRTOS/            ← FreeRTOS 内核（若使用）
└── README.md
```

### 3. 多 Agents 协作阶段

#### Agent 分工模式

**主 Agents（1个）**：

- 职责：需求理解 + 架构设计 + 协调分配 + 编译检查 + 整体检查
- 工作：将任务拆分成多个模块，分发给子 agents

**子 Agents（多个，按模块划分）**：

- 每个子 agent 负责一个或多个模块的实现
- 示例分工：
  - Agent A：负责 `interface/`（硬件接口层）
  - Agent B：负责 `common/`（通用算法）
  - Agent C：负责 `Application/`（应用层）

#### 并行工作方式

```
主 Agents 发起任务分配
  ├─ Agent A: interface/ 模块 → 独立工作
  ├─ Agent B: common/ 模块 → 独立工作
  └─ Agent C: Application/ 模块 → 独立工作

每个 Agent 完成后触发 Hook 1
所有 Hook 1 通过后 → 触发编译 Hook 2
```

**并行优势：**

- 缩短开发时间
- 各模块独立，减少冲突
- 符合嵌入式模块化设计思想

**注意事项：**

- 各模块接口需要提前定义
- 主 Agents 需要协调模块间的依赖关系
- 避免多个 Agent 同时修改同一个文件

详见 `references/coding-standards.md`

### 4. Hooks 机制

详见 `references/hooks-checklist.md`

- **Hook 1**：子 Agents 完成模块后触发代码检查
- **Hook 2**：整体代码完成后触发编译
- **Hook 3**：编译通过后触发整体检查
- **Hook 4**：编译失败触发修复流程（最大重试 5 次）

### 5. 最终交付阶段

**全部检查通过后，生成：**

1. 完整代码：所有模块的源代码
2. README.md 文档（使用 `references/readme-template.md` 模板）

---

## 编译命令

```bash
# 增量编译
"Keil安装路径\UV4\UV4.exe" -b "项目路径\项目名.uvprojx" -o "build.log"

# 完全重新编译
"Keil安装路径\UV4\UV4.exe" -r "项目路径\项目名.uvprojx" -o "build.log"
```

**参数说明：**
| 参数 | 说明 |
|------|------|
| `-b` | Build（增量编译） |
| `-r` | Rebuild（完全重新编译） |
| `-o` | 输出日志文件 |

---

## 使用示例

**触发词：**

- "帮我重构这个 STM32 项目的代码"
- "优化这个嵌入式项目的代码结构"
- "帮我写一个 XXX 功能的嵌入式代码"
- "这个代码太屎了，帮我重构一下"

---

## 参考资源

- `references/coding-standards.md`：代码规范说明
- `references/hooks-checklist.md`：Hooks 检查清单
- `references/readme-template.md`：README.md 输出模板

---

## 版本信息

- **Skill 版本**：1.5
- **最后更新**：2026-05-21
- **适用范围**：STM32 系列芯片，Keil MDK 5.x
- **作者**：Unknown
