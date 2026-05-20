---
name: embedded
description: >
  Universal STM32 embedded firmware development using Keil MDK + STM32CubeMX HAL.
  Auto-detects chip and peripheral configuration from .ioc files. Builds new projects,
  refactors existing code, and designs serial protocols.
  Trigger on: 嵌入式, STM32, Keil, CubeMX, HAL库, I2C, SPI, UART, FreeRTOS, PWM, ADC,
  重构, 代码太乱, 代码太臃肿. NOT for Arduino, ESP32, RISC-V, Linux drivers.
---

# STM32 Embedded Development

Works with any STM32 series (F0/F1/F4/F7/G0/G4/H7/L0/L4/WB/etc.). Chip and peripherals auto-detected from CubeMX `.ioc`.

---

## Phase 0: 项目自动检测（必须先执行）

### Step 0.1: 找到 .ioc 文件
在当前目录或子目录找 CubeMX 项目（`.ioc`）。多个则问用户选哪个。

### Step 0.2: 从 .ioc 提取芯片信息
读 `.ioc`（纯文本 key=value），提取：
- `Mcu.CPN` / `Mcu.Family` — 芯片型号和系列
- `RCC.SYSCLKFreq` — 系统时钟
- `RCC.APB1CLKFreq` / `RCC.APB2CLKFreq` — 外设总线时钟

### Step 0.3: 从 .ioc 提取外设配置
扫描已启用的外设（I2C、SPI、USART、TIM、ADC、FREERTOS 等），记录引脚和参数。

### Step 0.4: 验证 HAL 库
检查 `Drivers/` 目录有正确的 HAL driver（如 `STM32F4xx_HAL_Driver/`）。缺少则让 CubeMX 重新生成。

### Step 0.5: 展示配置表，问用户要做什么

---

## Rule 0: 写代码前必须确认硬件

嵌入式没有默认引脚。需求不精确时必须问：

1. **引脚分配**：I2C1/2/3？SCL/SDA 在哪？UART TX/RX 引脚？
2. **总线参数**：I2C 标准(100kHz)还是快速(400kHz)？UART 波特率？SPI CPOL/CPHA？
3. **中断 vs 轮询**：数据怎么读？
4. **总线上其他设备**：是否有其他传感器/执行器共享同一总线？

不要一次性问完。先问引脚，再问细节。

---

## Commander + Executors 工作流

**适用条件**：2+ 文件且 2+ 外设时使用。

### Commander（你）
1. 理解项目 → 2. 收集信息（Rule 0）→ 3. 设计分层架构 → 4. 分解子任务 → 5. 分发 Agent → 6. 验证

### Executors（Agent 子任务）
每个 Executor 处理一个模块，prompt 必须包含：文件列表、接口契约（结构体定义）、约束、参考文件、正确 HAL 头文件。

详细协议和 prompt 模板见 `references/commander-protocol.md`。

---

## Rule 1: 分层架构（必须遵守）

```
Application Layer (User/)     业务逻辑，FreeRTOS 任务
       ↓ calls
Hardware Abstraction (Hardware/)  驱动模块，结构体封装
       ↓ depends on
Driver Layer (Core/)          CubeMX 生成，不要改
```

- **User/**: 只调 Hardware/ API，不直接调 HAL
- **Hardware/**: 每个外设一个 .h+.c，.h 暴露结构体+API，.c 隐藏寄存器细节
- **Core/**: CubeMX 生成，代码只写在 `/* USER CODE BEGIN/END */` 之间

详细架构见 `references/layered-architecture.md`。

---

## Rule 2: 命名规范（必须遵守）

| 类别 | 规范 | 示例 |
|------|------|------|
| 函数 | `Module_Action` | `ADS1115_Init`, `Motor_SetSpeed` |
| 局部变量 | `snake_case` | `adc_raw`, `angle_pitch` |
| 全局变量 | `g_snake_case` | `g_system_tick` |
| 结构体/枚举 | `Module_Xxx_t` | `IMU_Data_t`, `PID_Config_t` |
| 宏/常量 | `UPPER_SNAKE` | `ADS1115_ADDR_GND` |
| Include guard | `MODULE_H`（无 `__` 前缀） | `ADS1115_H` |
| 文件名 | `ModuleName.h/.c` | `ADS1115.h` |

详细规范见 `references/naming-conventions.md`。

---

## Rule 3: 结构体设计（必须遵守）

所有硬件模块用结构体封装状态和配置：

```c
// 设备结构体（address 在前）
typedef struct {
    uint8_t address;
    I2C_HandleTypeDef *hi2c;
} Sensor_Device_t;

// 数据结构体
typedef struct {
    float x, y, z;
    uint8_t data_valid;
} IMU_Data_t;
```

---

## Rule 4: 代码简洁性（必须遵守）

- I2C 写寄存器：3 字节 buffer + `HAL_I2C_Master_Transmit`
- I2C 读寄存器：`Master_Transmit` 发地址 + `Master_Receive` 读数据
- 错误处理：early return（`if (status != HAL_OK) return status;`）
- 状态用枚举，不用魔法数字

详细代码模式见 `references/hal-driver-template.md`。

---

## HAL 头文件选择

从 `.ioc` 读 `Mcu.Family` 字段，自动选择正确的 HAL 头文件：
- F4 系列 → `stm32f4xx_hal.h`
- F1 系列 → `stm32f1xx_hal.h`
- G0 系列 → `stm32g0xx_hal.h`
- 以此类推

Family 不在常见列表中时，检查 `Drivers/` 目录的 HAL driver 文件夹名。

---

## 代码风格基准：ADS1115 库

所有 Hardware/ 下的驱动以 `嵌入式项目/ads1115库/ADS1115.h/.c` 为基准：
- 中文注释，`@brief @param @return` 格式
- I2C 用 `Master_Transmit` + `Master_Receive`，不用 `HAL_I2C_Mem_*`
- 包含滤波函数：均值、滑动平均、中值

---

## 重构现有代码

用户说"重构"、"重写"、"代码太乱"时，遵循 `references/refactoring-rules.md`：
1. 先评估原作者水平（初学/中级/高级）
2. 捕获风格指纹（命名、注释语言、缩进）
3. 匹配他们的抽象水平改写
4. 每个函数加注释

---

## 项目目录规范

### HAL 项目（CubeMX）
```
Project/
├── Project.ioc
├── Core/Inc/          ← HAL 自动生成头文件
├── Core/Src/          ← HAL 自动生成源文件
├── Hardware/          ← 你的驱动
├── Drivers/           ← CMSIS + HAL 库，不要改
└── MDK-ARM/           ← Keil 项目文件
```

---

## 项目文档（完成后必须生成）

完成新项目或重构后，生成 `项目说明.md` 放在项目根目录。模板见 `references/project-documentation.md`。

---

## Build Verification Loop（代码改完后自动执行）

代码修改完成后，**不要等用户要求**，自动进入编译验证循环。

### 触发条件
- 新建/重构/移植代码完成后
- 用户说"编译"、"build"、"看看有没有错"

### 流程
1. 找到 `.uvprojx` 文件，运行 Keil 命令行编译：
   ```bash
   "C:/Keil_v5/UV4/UV4.exe" -b "<path>.uvprojx" -o "<dir>/build_output.txt" -j0
   ```
2. 读取 `build_output.txt`，grep `Error:` 统计错误数
3. 如果 0 errors → 报告 warnings 数，完成
4. 如果有 errors → 逐条分析、修复、重新编译（连续 3 轮错误数不减少才停止）
5. 修复时注意全局影响，不要随便删改文件

### 关键规则
- Exit code 1 = 成功，2 = 有错误，0 = 未编译
- 同类错误批量修复，不要一个一个来
- 修头文件前先 grep 确认影响范围
- 详细协议见 `references/build-loop.md`

---

## Reference Files

| 文件 | 何时读取 |
|------|---------|
| `references/layered-architecture.md` | 设计新项目或重构架构时 |
| `references/naming-conventions.md` | 审查或标准化命名时 |
| `references/hal-driver-template.md` | 写新 I2C/SPI/UART 驱动时 |
| `references/commander-protocol.md` | 使用 Commander+Executors 工作流时 |
| `references/refactoring-rules.md` | 重构现有代码时 |
| `references/common-patterns.md` | 需要串口调试、FreeRTOS 模板、错误调试时 |
| `references/serial-protocol.md` | 设计上下位机串口协议时 |
| `references/freertos-setup.md` | 添加或调试 FreeRTOS 任务时 |
| `references/project-documentation.md` | 生成项目文档时 |
| `references/peripheral-specifics.md` | 用到 ADS1115、MPU6050、HMC5883L、nRF24L01、OLED 时 |
| `references/build-loop.md` | 代码改完后自动编译验证时 |
