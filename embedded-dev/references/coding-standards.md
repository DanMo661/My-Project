# 代码规范说明

## 命名规范

### 文件命名
- **应用层**：`App_` 前缀（如 `App_flight.c`, `App_freeRTOS_Task.c`）
- **通用算法**：`Com_` 前缀（如 `Com_pid.c`, `Com_filter.c`）
- **硬件接口**：`Int_` 前缀（如 `Int_motor.c`, `Int_mpu6050.c`）

### 函数命名
- 使用下划线命名法
- 格式：`模块名_功能名`
- 示例：
  - `Int_MPU6050_Init()` - 初始化 MPU6050
  - `Com_PID_Calculate()` - PID 计算
  - `App_Flight_Get_Euler_Angle()` - 获取欧拉角

### 变量命名
- 全局变量：使用下划线命名法
- 局部变量：使用驼峰命名法或下划线命名法
- 示例：
  - `gyro_x_offset` - 陀螺仪 X 轴偏移
  - `current_accel` - 当前加速度

## 代码结构

### 头文件结构
```c
#ifndef INT_XXX_H
#define INT_XXX_H

#include "main.h"

// 宏定义
#define XXX_ADDR 0x68

// 结构体定义
typedef struct {
    int16_t x;
    int16_t y;
    int16_t z;
} XXX_Data_t;

// 函数声明
void Int_XXX_Init(void);
void Int_XXX_Read(XXX_Data_t *data);

#endif
```

### 源文件结构
```c
#include "Int_xxx.h"

// 全局变量
int32_t xxx_offset = 0;

/**
 * @brief 初始化 XXX 设备
 *
 */
void Int_XXX_Init(void)
{
    // 初始化代码
}

/**
 * @brief 读取 XXX 数据
 *
 * @param data 数据指针
 */
void Int_XXX_Read(XXX_Data_t *data)
{
    // 读取代码
}
```

## 注释规范

### 函数注释
使用 Doxygen 格式的中文注释：
```c
/**
 * @brief 函数功能简述
 *
 * @param param1 参数1说明
 * @param param2 参数2说明
 * @return 返回值说明
 */
```

### 行内注释
- 使用中文注释
- 注释要清晰、简洁
- 解释"为什么"而不是"做什么"

## 代码组织

### 目录结构
```
MDK-ARM/
├── Application/         ← 应用层
├── common/              ← 通用算法
├── interface/           ← 硬件接口层
│   └── fix_height/      ← 子模块（如定高）
└── freeRTOS/            ← FreeRTOS 内核
```

### 模块依赖
- interface/ 可以调用 Drivers/ 中的 HAL 库
- common/ 可以调用 interface/
- Application/ 可以调用 common/ 和 interface/
- 避免循环依赖
