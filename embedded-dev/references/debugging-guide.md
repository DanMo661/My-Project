# 调试指南

## 调试工具

### Keil 调试器
1. **断点调试**：设置断点，单步执行
2. **变量观察**：查看变量值和内存内容
3. **寄存器查看**：查看外设寄存器状态
4. **逻辑分析仪**：使用 Serial Wire Viewer (SWV)

### 串口调试
```c
// 使用 printf 重定向到串口
int fputc(int ch, FILE *f)
{
    HAL_UART_Transmit(&huart1, (uint8_t *)&ch, 1, HAL_MAX_DELAY);
    return ch;
}

// 调试输出
printf("Debug: value = %d\r\n", value);
```

### GPIO 调试
```c
// 使用 LED 指示状态
HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);    // LED 亮
HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);  // LED 灭

// 使用示波器观察波形
HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_0);  // 翻转引脚
```

## 常见问题排查

### 编译错误

**错误：undefined reference**
- 原因：函数声明但未定义，或未包含源文件
- 解决：检查函数实现，确认源文件已添加到工程

**错误：redefinition**
- 原因：头文件重复包含
- 解决：检查头文件保护宏是否正确

**错误：implicit declaration**
- 原因：函数未声明就使用
- 解决：在头文件中添加函数声明

### 运行时错误

**HardFault 异常**
- 原因：内存访问错误、栈溢出、未对齐访问
- 排查：
  1. 检查栈使用情况
  2. 检查指针是否为空
  3. 检查数组是否越界
  4. 检查内存分配是否成功

**死循环**
- 原因：中断未正确处理，任务调度问题
- 排查：
  1. 检查中断优先级
  2. 检查任务栈大小
  3. 检查是否有死锁

### 外设问题

**I2C 通信失败**
- 检查上拉电阻是否正确
- 检查设备地址是否正确
- 检查时序是否满足要求

**SPI 通信异常**
- 检查时钟极性和相位
- 检查片选信号控制
- 检查数据位顺序

**UART 通信错误**
- 检查波特率设置
- 检查数据位、停止位、校验位配置
- 检查硬件连接

## 调试技巧

### 1. 最小系统测试
```c
// 先测试最基本的外设
void Test_Minimal_System(void)
{
    // 测试 GPIO
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);
    HAL_Delay(500);
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);
    HAL_Delay(500);
    
    // 测试 UART
    printf("System OK\r\n");
}
```

### 2. 模块化测试
```c
// 逐个测试模块
void Test_All_Modules(void)
{
    printf("Testing GPIO...\r\n");
    Test_GPIO();
    
    printf("Testing UART...\r\n");
    Test_UART();
    
    printf("Testing I2C...\r\n");
    Test_I2C();
}
```

### 3. 数据记录
```c
// 记录关键数据
void Log_Data(int16_t *data, int len)
{
    for (int i = 0; i < len; i++) {
        printf("Data[%d] = %d\r\n", i, data[i]);
    }
}
```

### 4. 性能分析
```c
// 测量函数执行时间
uint32_t start_time, end_time;
start_time = HAL_GetTick();
// 执行代码
end_time = HAL_GetTick();
printf("Execution time: %d ms\r\n", end_time - start_time);
```

## FreeRTOS 调试

### 任务状态查看
```c
// 使用 FreeRTOS 提供的 API
void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName)
{
    printf("Stack overflow in task: %s\r\n", pcTaskName);
}

void vApplicationMallocFailedHook(void)
{
    printf("Malloc failed!\r\n");
}
```

### 任务监控
```c
// 定期打印任务状态
void Monitor_Task(void)
{
    while (1) {
        printf("Free heap: %d\r\n", xPortGetFreeHeapSize());
        printf("Task count: %d\r\n", uxTaskGetNumberOfTasks());
        vTaskDelay(1000);
    }
}
```

## 硬件调试

### 信号测量
1. 使用示波器测量时序
2. 使用逻辑分析仪分析协议
3. 使用万用表测量电压

### 电源检测
1. 检查供电电压是否稳定
2. 检查电源纹波
3. 检查各模块供电是否正常

### 温度检测
1. 检查芯片温度
2. 检查功率器件温度
3. 检查散热是否良好