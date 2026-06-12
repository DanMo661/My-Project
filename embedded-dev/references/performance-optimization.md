# 性能优化指南

## 编译优化

### Keil 编译选项
1. **优化级别**：Level 1 (-O1) 或 Level 2 (-O2)
2. **代码大小**：使用 -Osize 优化
3. **调试信息**：开发时保留，发布时移除

### 常用优化选项
- `-O1`：基本优化，平衡代码大小和性能
- `-O2`：更积极的优化，提高性能
- `-O3`：最大优化，可能增加代码大小
- `-Osize`：优化代码大小

## 代码优化

### 1. 避免不必要的计算
```c
// 不好的写法
for (int i = 0; i < 100; i++) {
    result = sin(i * 0.01);  // 重复计算
}

// 优化后
for (int i = 0; i < 100; i++) {
    result = sin_table[i];  // 查表法
}
```

### 2. 使用位运算
```c
// 不好的写法
result = value * 2;

// 优化后
result = value << 1;

// 不好的写法
result = value / 4;

// 优化后
result = value >> 2;
```

### 3. 减少函数调用
```c
// 不好的写法
void Process_Data(void)
{
    for (int i = 0; i < 100; i++) {
        data[i] = Calculate_Value(i);  // 函数调用开销
    }
}

// 优化后
void Process_Data(void)
{
    for (int i = 0; i < 100; i++) {
        data[i] = i * 2 + 1;  // 内联计算
    }
}
```

### 4. 使用查表法
```c
// 预计算正弦表
const int16_t sin_table[360] = {
    0, 17, 35, 52, 70, 87, 105, 122, ...
};

// 使用查表
int16_t Get_Sin(int angle)
{
    return sin_table[angle % 360];
}
```

## 内存优化

### 1. 使用合适的变量类型
```c
// 不好的写法
int big_var = 10;  // 使用 int 存储小数值

// 优化后
int8_t small_var = 10;  // 使用最小类型
```

### 2. 结构体内存对齐
```c
// 不好的写道
typedef struct {
    uint8_t a;
    uint32_t b;  // 可能导致未对齐访问
    uint8_t c;
} Bad_Struct_t;

// 优化后
typedef struct {
    uint8_t a;
    uint8_t c;
    uint32_t b;  // 按大小排序，减少填充
} Good_Struct_t;
```

### 3. 使用位域
```c
// 不好的写法
typedef struct {
    uint8_t flag1;
    uint8_t flag2;
    uint8_t flag3;
} Flags_t;  // 占用 3 字节

// 优化后
typedef struct {
    uint8_t flag1 : 1;
    uint8_t flag2 : 1;
    uint8_t flag3 : 1;
} Flags_t;  // 占用 1 字节
```

## 时间优化

### 1. 减少中断延迟
```c
// 中断服务函数要简短
void EXTI0_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0);
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    g_exti_flag = 1;  // 只设置标志位
}
```

### 2. 使用 DMA
```c
// 使用 DMA 传输数据
HAL_UART_Transmit_DMA(&huart1, data, len);

// 使用 DMA 接收数据
HAL_UART_Receive_DMA(&huart1, buffer, len);
```

### 3. 使用定时器
```c
// 使用定时器产生精确延时
void Delay_us(uint32_t us)
{
    __HAL_TIM_SET_COUNTER(&htim1, 0);
    while (__HAL_TIM_GET_COUNTER(&htim1) < us);
}
```

## 功耗优化

### 1. 使用低功耗模式
```c
// 进入 Sleep 模式
HAL_PWR_EnterSLEEPMode(PWR_MAINREGULATOR_ON, PWR_SLEEPENTRY_WFI);

// 进入 Stop 模式
HAL_PWR_EnterSTOPMode(PWR_LOWPOWERREGULATOR_ON, PWR_STOPENTRY_WFI);
```

### 2. 关闭未使用的外设
```c
// 关闭未使用的外设时钟
__HAL_RCC_GPIOA_CLK_DISABLE();
__HAL_RCC_GPIOB_CLK_DISABLE();
```

### 3. 调整时钟频率
```c
// 降低系统时钟
RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK;
RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_HSI;
RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
```

## FreeRTOS 优化

### 1. 任务优先级优化
```c
// 合理设置任务优先级
#define TASK_PRIORITY_LOW      1
#define TASK_PRIORITY_MEDIUM   2
#define TASK_PRIORITY_HIGH     3
#define TASK_PRIORITY_CRITICAL 4
```

### 2. 栈大小优化
```c
// 使用 uxTaskGetStackHighWaterMark() 检查栈使用
void vTaskMonitor(void *pvParameters)
{
    while (1) {
        UBaseType_t high_water = uxTaskGetStackHighWaterMark(NULL);
        printf("Task stack high water mark: %d\r\n", high_water);
        vTaskDelay(1000);
    }
}
```

### 3. 使用空闲任务钩子
```c
void vApplicationIdleHook(void)
{
    // 在空闲任务中执行低优先级工作
    // 或进入低功耗模式
}
```

## 性能测试

### 1. 测量执行时间
```c
// 使用 DWT 测量精确时间
CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
DWT->CYCCNT = 0;
DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

uint32_t start = DWT->CYCCNT;
// 执行代码
uint32_t end = DWT->CYCCNT;
uint32_t cycles = end - start;
```

### 2. 测量中断延迟
```c
// 在中断中测量延迟
void EXTI0_IRQHandler(void)
{
    uint32_t start = DWT->CYCCNT;
    // 中断处理
    uint32_t end = DWT->CYCCNT;
    printf("Interrupt latency: %d cycles\r\n", end - start);
}
```

### 3. 测量任务切换时间
```c
// 测量任务切换开销
void Task1(void *pvParameters)
{
    while (1) {
        uint32_t start = DWT->CYCCNT;
        vTaskDelay(1);
        uint32_t end = DWT->CYCCNT;
        printf("Task switch: %d cycles\r\n", end - start);
    }
}
```