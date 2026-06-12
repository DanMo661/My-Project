# 项目名称

## 概述

简要描述项目功能和目标（2-3 句话）

## 功能特性

- 功能 1：描述
- 功能 2：描述
- 功能 3：描述

## 模块架构

```
MDK-ARM/
├── Application/        ← 应用层
│   ├── App_flight.c    ← 飞行控制逻辑
│   └── App_receive.c   ← 数据接收处理
├── common/             ← 通用算法
│   ├── Com_pid.c       ← PID 控制器
│   └── Com_filter.c    ← 滤波算法
└── interface/          ← 硬件接口
    ├── Int_motor.c     ← 电机控制
    └── Int_sensor.c    ← 传感器驱动
```

## 环境要求

- Keil MDK 5.x
- STM32CubeMX
- STM32 系列芯片

## 编译步骤

### 方法 1：Keil IDE 编译
1. 打开项目文件 `MDK-ARM/项目名.uvprojx`
2. 点击编译按钮（F7）

### 方法 2：命令行编译
```bash
"C:\Keil_v5\UV4\UV4.exe" -b "项目路径\项目名.uvprojx" -o "build.log"
```

### 编译参数说明
| 参数 | 说明 |
|------|------|
| `-b` | 增量编译（只编译修改的文件） |
| `-r` | 完全重新编译 |
| `-o` | 输出日志文件 |
| `-j0` | 串行编译 |

## 烧录运行

使用 ST-Link 或 J-Link 烧录到目标板。

## 硬件连接

| 引脚 | 功能 | 外设 |
|------|------|------|
| PA0  | GPIO | LED |
| PB6  | I2C1_SCL | MPU6050 |
| PB7  | I2C1_SDA | MPU6050 |
| ... | ... | ... |

## 模块说明

### Application 层
- `App_flight.c`：飞行控制主逻辑
- `App_freeRTOS_Task.c`：FreeRTOS 任务管理
- `App_receive_data.c`：数据接收处理

### Common 层
- `Com_pid.c`：PID 控制器实现
- `Com_filter.c`：滤波算法
- `Com_imu.c`：IMU 数据处理
- `Com_debug.c`：调试工具

### Interface 层
- `Int_motor.c`：电机控制接口
- `Int_mpu6050.c`：陀螺仪驱动
- `Int_SI24R1.c`：无线通信接口
- `Int_led.c`：LED 控制

## 注意事项

1. CubeMX 生成的代码不要手动修改
2. FreeRTOS 任务栈大小要根据实际情况调整
3. 注意中断优先级配置
4. 硬件初始化顺序要正确

## 参考资料

- 参考项目：`P01_flight_hal`
- STM32 HAL 库文档
- FreeRTOS 官方文档

## 版本信息

- 版本：1.0
- 日期：2026-05-21
- 作者：Unknown
