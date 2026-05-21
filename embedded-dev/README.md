# Embedded Development Skill

嵌入式软件开发助手，用于 STM32 项目的新建、重构、优化和代码编写。

## 功能特点

- ✅ **多 Agents 协作**：主 Agents 协调 + 多子 Agents 并行工作
- ✅ **模块化设计**：模仿 FreeRTOS 的模块化架构
- ✅ **Hooks 机制**：每个模块完成后自动检查，编译后整体验证
- ✅ **代码规范**：统一的命名规范和代码风格
- ✅ **自动化编译**：支持 Keil MDK 命令行编译
- ✅ **完整输出**：生成完整代码 + README.md 文档

## 适用范围

- STM32 全系列芯片
- Keil MDK 5.x
- STM32CubeMX HAL 库

## 工作流程

```
需求确认 → 架构设计 → 多 Agents 协作 → Hooks 检查 → 编译 → 整体检查 → 交付
```

### Hooks 机制

| Hook   | 触发时机          | 检查内容                             |
| ------ | ----------------- | ------------------------------------ |
| Hook 1 | 子 Agent 完成模块 | 代码错误、任务完成度、注释、代码风格 |
| Hook 2 | 整体代码完成      | 自动编译                             |
| Hook 3 | 编译通过          | 模块配合、主逻辑验证、硬件初始化     |
| Hook 4 | 编译失败          | 修复流程（最大重试 5 次）            |

## 文件结构

```
embedded-dev/
├── SKILL.md                      ← 主指令文件
└── references/
    ├── coding-standards.md       ← 代码规范说明
    ├── hooks-checklist.md        ← Hooks 检查清单
    └── readme-template.md        ← README.md 输出模板
```

## 使用方法

### 触发词

- "帮我重构这个 STM32 项目的代码"
- "优化这个嵌入式项目的代码结构"
- "帮我写一个 XXX 功能的嵌入式代码"
- "这个代码太屎了，帮我重构一下"

### 使用流程

1. 用户提供需求和项目路径
2. Skill 自动触发，确认需求和引脚功能
3. 主 Agents 设计架构，分发任务给子 Agents
4. 子 Agents 并行工作，每个完成后触发 Hook 1
5. 所有模块完成后触发编译 Hook
6. 编译通过后触发整体检查 Hook
7. 检查通过后输出完整代码和 README.md

## 编译命令

```bash
# 增量编译
"Keil安装路径\UV4\UV4.exe" -b "项目路径\项目名.uvprojx" -o "build.log"

# 完全重新编译
"Keil安装路径\UV4\UV4.exe" -r "项目路径\项目名.uvprojx" -o "build.log"
```

### 参数说明

| 参数 | 说明                    |
| ---- | ----------------------- |
| `-b` | Build（增量编译）       |
| `-r` | Rebuild（完全重新编译） |
| `-o` | 输出日志文件            |

## 目录结构约定

```
项目根目录/
├── Core/                    ← CubeMX 生成的基础代码
├── Drivers/                 ← HAL 驱动库
├── MDK-ARM/                 ← Keil 项目目录
│   ├── Application/         ← 应用层（App_ 前缀）
│   ├── common/              ← 通用算法（Com_ 前缀）
│   ├── interface/           ← 硬件接口层（Int_ 前缀）
│   └── freeRTOS/            ← FreeRTOS 内核（若使用）
└── README.md
```

## 代码规范

### 命名规范

- 应用层：`App_` 前缀
- 通用算法：`Com_` 前缀
- 硬件接口：`Int_` 前缀

### 注释规范

使用 Doxygen 格式的中文注释

详见 `references/coding-standards.md`

## 版本信息

- **版本**：1.5
- **更新日期**：2026-05-21
- **适用范围**：STM32 系列芯片，Keil MDK 5.x
- **作者**：Unknown

## 许可证

MIT License
