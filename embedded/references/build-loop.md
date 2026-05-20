# Build Verification Loop

## 触发条件

代码修改完成后（新建、重构、移植），自动进入编译验证循环。不要等用户要求。

## 前置条件

- 项目有 Keil `.uvprojx` 文件
- Keil MDK 已安装（默认路径 `C:/Keil_v5/UV4/UV4.exe`）

## 编译命令

```bash
"C:/Keil_v5/UV4/UV4.exe" -b "<项目绝对路径>.uvprojx" -o "<项目目录>/build_output.txt" -j0
```

- `-b`: 批量编译模式
- `-o`: 输出日志路径
- `-j0`: 不弹窗

### Exit Code

| 值 | 含义 |
|----|------|
| 0 | 无编译（已是最新） |
| 1 | 编译成功 |
| 2 | 编译有错误 |

注意：exit code 1 也表示成功，不要误判为失败。

## 循环协议

```
prev_error_count = infinity
stale_rounds = 0

loop:
    1. 运行 UV4.exe -b
    2. 读取 build_output.txt
    3. grep "Error:" 和 "error:" 统计错误数 → current_errors
    4. 如果 0 errors → 跳出，报告 warnings 数
    5. 如果有 errors:
       a. 逐条分析错误原因
       b. 修复（注意全局影响，不要随便删改）
       c. 如果 current_errors >= prev_error_count:
            stale_rounds++
          else:
            stale_rounds = 0
       d. 如果 stale_rounds >= 3 → 停止，报告剩余错误
       e. prev_error_count = current_errors
       f. 继续下一轮
```

**停止条件**：连续 3 轮错误数不减少（说明当前方法解不了剩余错误，需要人工介入或换思路）。无上限轮次，只要错误还在减少就继续修。

## 错误解析规则

### 常见错误类型和修复策略

| 错误模式 | 原因 | 修复 |
|----------|------|------|
| `unresolved external symbol` | 变量/函数只有声明没有定义 | 在对应 .c 文件添加定义 |
| `undefined symbol` (linker) | 同上 | 同上 |
| `identifier "xxx" is undefined` | 缺少 #include 或变量未声明 | 添加正确的 #include 或 extern 声明 |
| `#include "xxx.h" not found` | 头文件路径不在 IncludePath | 检查文件是否存在，更新 .uvprojx IncludePath |
| `redefinition of 'xxx'` | 同一符号在多个文件中定义 | 保留一个定义，其他改为 extern 或删除 |
| `previous definition` | 同上，附带之前定义位置 | 同上 |
| `declared implicitly` | 函数调用前未声明 | 在调用者 .c 顶部或对应 .h 添加声明 |
| `expression has no effect` | 宏展开错误（如 LIMIT 宏缺少参数） | 检查宏定义和调用是否匹配 |
| `function "xxx" declared implicitly` | ISR 函数在 stm32f1xx_it.c 中调用但未 include | 添加正确的 include |
| `unknown type name 'u8'` | StdPeriph 兼容类型未定义 | 在 all_data.h 添加 typedef |

### 修复原则

1. **先看全局影响**：修改头文件前，grep 确认哪些文件 include 了它
2. **不要随便删代码**：理解错误根因再修，不要注释掉报错行
3. **优先添加而非修改**：缺声明就加声明，不要改现有代码结构
4. **一个错误修一类**：同类型的多个错误通常一次修复就能全部解决

## Warnings 处理

编译成功后，分析 warnings：

| Warning | 处理 |
|---------|------|
| `#177-D: variable was declared but never referenced` | 可忽略（移植遗留），或删除 |
| `#174-D: expression has no effect` | 检查宏展开，通常是 LIMIT 宏缺参数 |
| `#223-D: function declared implicitly` | 添加 #include 或函数声明 |
| `#1-D: last line of file ends without a newline` | 文件末尾加空行 |
| `#550-D: variable was set but never used` | 可忽略或删除 |

## 报告格式

循环结束后，输出：

```
## 编译结果

- 编译轮次: N
- 最终状态: 0 errors, M warnings
- 修复内容:
  - 轮次 1: 修复了 XXX（具体描述）
  - 轮次 2: 修复了 YYY
  - ...
- 剩余 warnings: 列出是否需要关注
```

## 特殊情况

### Keil 路径不在默认位置
搜索注册表或让用户提供：
```bash
where UV4.exe 2>/dev/null || reg query "HKLM\SOFTWARE\Keil\Products\MDK" /v Path
```

### 编译超时
UV4.exe 默认超时 120 秒。大项目可能需要更长时间，用 `timeout` 参数调整。

### 无 .uvprojx 文件
跳过自动编译，提醒用户手动编译验证。
