# HAL Peripheral Driver Template

Use this template whenever writing a new I2C/SPI/UART peripheral driver. Replace `Module` / `MODULE` with the chip name (e.g., `ADS1115`, `MPU6050`).

**风格对齐 ADS1115 库：** 注释用中文、include guard 无 `__` 包裹、设备结构体 address 在前、I2C 直接用 Master_Transmit/Master_Receive、early return 错误处理。

## Header File Template: `Hardware/MODULE.h`

```c
#ifndef MODULE_H
#define MODULE_H

#include "stm32fXxx_hal.h"               // Device header (auto-detected from chip family)

// MODULE I2C 地址 (根据 ADDR 引脚连接)
#define MODULE_ADDR_GND         0x68  // ADDR 引脚接地
#define MODULE_ADDR_VDD         0x69  // ADDR 引脚接 VDD

// 寄存器地址
#define MODULE_REG_WHOAMI       0x75
#define MODULE_REG_CONFIG       0x1A
#define MODULE_REG_DATA_X       0x3B

// 配置寄存器位定义
#define MODULE_CONFIG_RESET     (1 << 7)

// 通道选择枚举
typedef enum {
    MODULE_MUX_AIN0_GND = 0x4000,  // AIN0 单端
    MODULE_MUX_AIN1_GND = 0x5000,  // AIN1 单端
    MODULE_MUX_AIN2_GND = 0x6000,  // AIN2 单端
    MODULE_MUX_AIN3_GND = 0x7000   // AIN3 单端
} MODULE_Channel_t;

// 量程选择枚举
typedef enum {
    MODULE_RANGE_2G = 0x0000,       // ±2g
    MODULE_RANGE_4G = 0x0800,       // ±4g
    MODULE_RANGE_8G = 0x1000,       // ±8g
    MODULE_RANGE_16G = 0x1800       // ±16g
} MODULE_Range_t;

// 设备结构体
typedef struct {
    uint8_t address;
    I2C_HandleTypeDef *hi2c;
} MODULE_Device_t;

// 数据输出结构体
typedef struct {
    float x;
    float y;
    float z;
} MODULE_Data_t;

// API 函数
HAL_StatusTypeDef MODULE_Init(MODULE_Device_t *dev);
HAL_StatusTypeDef MODULE_ReadData(MODULE_Device_t *dev, MODULE_Data_t *data);
HAL_StatusTypeDef MODULE_ReadChannel(MODULE_Device_t *dev, MODULE_Channel_t channel, float *value, MODULE_Range_t range);
HAL_StatusTypeDef MODULE_Getdata(MODULE_Device_t *dev, float data[3]);

// 滤波函数
float MODULE_ReadFiltered(MODULE_Device_t *dev, MODULE_Channel_t channel,
                          MODULE_Range_t range, uint8_t sample_count);
float MODULE_ReadMovingAverage(MODULE_Device_t *dev, MODULE_Channel_t channel,
                               MODULE_Range_t range, uint8_t window_size);
float MODULE_ReadMedianFilter(MODULE_Device_t *dev, MODULE_Channel_t channel,
                              MODULE_Range_t range, uint8_t sample_count);

#endif
```

## Source File Template: `Hardware/MODULE.c`

```c
#include "module.h"
#include <math.h>

// MODULE 初始化
HAL_StatusTypeDef MODULE_Init(MODULE_Device_t *dev)
{
    // 写配置寄存器默认值
    uint16_t config = 0x8000;  // 复位并进入测量模式

    uint8_t config_data[3] = {
        MODULE_REG_CONFIG,
        (uint8_t)(config >> 8),  // 高字节
        (uint8_t)(config & 0xFF) // 低字节
    };

    return HAL_I2C_Master_Transmit(dev->hi2c, dev->address << 1, config_data, 3, HAL_MAX_DELAY);
}

// 读取数据
HAL_StatusTypeDef MODULE_ReadData(MODULE_Device_t *dev, MODULE_Data_t *data)
{
    uint8_t reg_addr = MODULE_REG_DATA_X;
    uint8_t rx_data[6];

    // 先发寄存器地址
    HAL_StatusTypeDef status = HAL_I2C_Master_Transmit(dev->hi2c, dev->address << 1, &reg_addr, 1, HAL_MAX_DELAY);
    if (status != HAL_OK)
    {
        return status;
    }

    // 再读数据
    status = HAL_I2C_Master_Receive(dev->hi2c, dev->address << 1, rx_data, 6, HAL_MAX_DELAY);
    if (status == HAL_OK)
    {
        // 合并两个字节 (MSB first)
        data->x = (int16_t)((rx_data[0] << 8) | rx_data[1]) / 16384.0f;
        data->y = (int16_t)((rx_data[2] << 8) | rx_data[3]) / 16384.0f;
        data->z = (int16_t)((rx_data[4] << 8) | rx_data[5]) / 16384.0f;
    }

    return status;
}

// 读取指定通道
HAL_StatusTypeDef MODULE_ReadChannel(MODULE_Device_t *dev, MODULE_Channel_t channel, float *value, MODULE_Range_t range)
{
    int16_t raw_value;

    // 启动转换
    uint16_t config = 0x8000 | channel | range;

    uint8_t config_data[3] = {
        MODULE_REG_CONFIG,
        (uint8_t)(config >> 8),
        (uint8_t)(config & 0xFF)
    };

    HAL_StatusTypeDef status = HAL_I2C_Master_Transmit(dev->hi2c, dev->address << 1, config_data, 3, HAL_MAX_DELAY);
    if (status != HAL_OK)
    {
        return status;
    }

    // 等待转换完成
    HAL_Delay(10);

    // 读取结果
    uint8_t reg_addr = MODULE_REG_DATA_X;
    uint8_t rx_data[2];

    status = HAL_I2C_Master_Transmit(dev->hi2c, dev->address << 1, &reg_addr, 1, HAL_MAX_DELAY);
    if (status != HAL_OK)
    {
        return status;
    }

    status = HAL_I2C_Master_Receive(dev->hi2c, dev->address << 1, rx_data, 2, HAL_MAX_DELAY);
    if (status == HAL_OK)
    {
        raw_value = (int16_t)((rx_data[0] << 8) | rx_data[1]);
        *value = (raw_value * 4.096f) / 32768.0f;  // 根据实际量程调整
    }

    return status;
}

// 便捷读取函数
HAL_StatusTypeDef MODULE_Getdata(MODULE_Device_t *dev, float data[3])
{
    HAL_StatusTypeDef status;

    status = MODULE_ReadChannel(dev, MODULE_MUX_AIN0_GND, &data[0], MODULE_RANGE_4G);
    if (status != HAL_OK)
        return status;

    status = MODULE_ReadChannel(dev, MODULE_MUX_AIN1_GND, &data[1], MODULE_RANGE_4G);
    if (status != HAL_OK)
        return status;

    status = MODULE_ReadChannel(dev, MODULE_MUX_AIN2_GND, &data[2], MODULE_RANGE_4G);

    return status;
}

/**
 * @brief 读取指定通道并做均值滤波
 * @param dev MODULE 设备指针
 * @param channel 要读取的通道
 * @param range 量程设置
 * @param sample_count 采样次数（建议 5-10 次）
 * @return 滤波后的值
 */
float MODULE_ReadFiltered(MODULE_Device_t *dev, MODULE_Channel_t channel,
                          MODULE_Range_t range, uint8_t sample_count)
{
    float sum = 0.0f;
    float samples[20];
    uint8_t valid_count = 0;

    // 边界检查
    if (sample_count > 20)
    {
        sample_count = 20;
    }

    for (uint8_t i = 0; i < sample_count; i++)
    {
        float value;

        if (MODULE_ReadChannel(dev, channel, &value, range) == HAL_OK)
        {
            // 范围检查
            if (value >= -4.1f && value <= 4.1f)
            {
                samples[valid_count] = value;
                valid_count++;
                sum += value;
            }
        }

        HAL_Delay(15);
    }

    if (valid_count > 0)
    {
        return sum / valid_count;
    }

    return 0.0f;
}

/**
 * @brief 滑动平均滤波
 * @param dev MODULE 设备指针
 * @param channel 要读取的通道
 * @param range 量程设置
 * @param window_size 滑动窗口大小（建议 3-5）
 * @return 滑动平均后的值
 */
float MODULE_ReadMovingAverage(MODULE_Device_t *dev, MODULE_Channel_t channel,
                               MODULE_Range_t range, uint8_t window_size)
{
    static float history[5] = {0};
    static uint8_t index = 0;
    static uint8_t count = 0;
    float sum = 0.0f;
    float value;

    if (MODULE_ReadChannel(dev, channel, &value, range) == HAL_OK)
    {
        // 更新历史缓冲区
        history[index] = value;
        index = (index + 1) % window_size;

        if (count < window_size)
        {
            count++;
        }

        for (uint8_t i = 0; i < count; i++)
        {
            sum += history[i];
        }

        return sum / count;
    }

    // 读取失败，返回历史平均值
    if (count > 0)
    {
        sum = 0.0f;
        for (uint8_t i = 0; i < count; i++)
        {
            sum += history[i];
        }
        return sum / count;
    }

    return 0.0f;
}

/**
 * @brief 中值滤波 - 有效去除尖峰噪声
 * @param dev MODULE 设备指针
 * @param channel 要读取的通道
 * @param range 量程设置
 * @param sample_count 采样次数（建议奇数：5、7、9）
 * @return 中值滤波后的值
 */
float MODULE_ReadMedianFilter(MODULE_Device_t *dev, MODULE_Channel_t channel,
                              MODULE_Range_t range, uint8_t sample_count)
{
    float samples[9];
    uint8_t valid_count = 0;

    // 确保 sample_count 为奇数
    if (sample_count % 2 == 0)
    {
        sample_count++;
    }
    if (sample_count > 9)
    {
        sample_count = 9;
    }

    for (uint8_t i = 0; i < sample_count; i++)
    {
        float value;
        if (MODULE_ReadChannel(dev, channel, &value, range) == HAL_OK)
        {
            if (value >= -4.1f && value <= 4.1f)
            {
                samples[valid_count] = value;
                valid_count++;
            }
        }
        HAL_Delay(15);
    }

    if (valid_count == 0)
    {
        return 0.0f;
    }

    // 冒泡排序（小数据量足够快）
    for (uint8_t i = 0; i < valid_count - 1; i++)
    {
        for (uint8_t j = 0; j < valid_count - i - 1; j++)
        {
            if (samples[j] > samples[j + 1])
            {
                float temp = samples[j];
                samples[j] = samples[j + 1];
                samples[j + 1] = temp;
            }
        }
    }

    // 返回中值
    return samples[valid_count / 2];
}
```

## Key Design Decisions

### 为什么 `dev->address << 1`？
HAL I2C 函数要求 8 位地址（7 位地址左移 1 位）。数据手册给出 7 位地址。我们在驱动里存 7 位、调用时移位，这样宏定义的值和手册一致。

### 为什么不用 `HAL_I2C_Mem_Read/Mem_Write`？
部分器件（如 ADS1115）的寄存器地址 + 数据格式与 HAL 的 Mem 函数预期不完全匹配。直接用 `Master_Transmit` + `Master_Receive` 更灵活，行为完全可控。

### 为什么设备结构体 address 在 hi2c 前面？
先确定"哪个设备"（address），再确定"用哪条总线"（hi2c）。逻辑顺序更自然。同时结构体初始化时 `{0x48, &hi2c1}` 比 `{&hi2c1, 0x48}` 更好读。

### 为什么 include guard 不用 `__` 前缀？
`__MODULE_H__` 是 C 标准保留标识符（双下划线归实现使用）。用 `MODULE_H` 干净且无潜在冲突。

### Early return 错误处理
```c
status = HAL_I2C_Master_Transmit(...);
if (status != HAL_OK)
    return status;          // ← 不嵌套，直接返回
```
每个可能失败的操作后立即检查并返回，减少嵌套层级。

### 滤波函数的三层设计
- `ReadFiltered` — 多次采样取平均，去除白噪声
- `ReadMovingAverage` — 滑动窗口平滑，适合连续监测，用 static 变量维持历史
- `ReadMedianFilter` — 冒泡排序取中值，有效去除偶发尖峰
