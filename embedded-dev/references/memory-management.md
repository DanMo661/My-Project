# 内存管理指南

## 内存区域划分

### STM32 内存布局
- **Flash**：程序代码和常量数据
- **SRAM**：变量、堆栈、动态内存
- **CCM**：核心耦合内存（部分型号）

### 内存区域用途
| 区域 | 用途 | 特点 |
|------|------|------|
| Flash | 代码、常量 | 非易失，读取较慢 |
| SRAM | 变量、堆栈 | 易失，读取快 |
| CM | 快速变量 | 部分型号，不能DMA |

## 静态内存分配

### 全局变量
```c
// 推荐：使用静态分配
int32_t g_sensor_data[100];
uint8_t g_comm_buffer[256];
```

### 局部变量
```c
void App_Task(void)
{
    // 推荐：使用静态或栈分配
    static int32_t static_buffer[100];
    int32_t stack_buffer[50];
}
```

### 结构体
```c
// 推荐：使用静态结构体
typedef struct {
    int32_t x;
    int32_t y;
    int32_t z;
} Sensor_Data_t;

static Sensor_Data_t g_sensor_data;
```

## 动态内存分配

### FreeRTOS 内存管理
```c
// 配置 FreeRTOS 堆大小
#define configTOTAL_HEAP_SIZE ((size_t)(16 * 1024))

// 使用 pvPortMalloc
void *buffer = pvPortMalloc(BUFFER_SIZE);
if (buffer == NULL) {
    // 内存分配失败
    return;
}

// 使用 vPortFree
vPortFree(buffer);
```

### 内存分配策略
1. **静态分配**：编译时确定大小，优先使用
2. **栈分配**：函数内局部变量，自动管理
3. **堆分配**：动态分配，需手动释放

## 内存泄漏防范

### 1. 配对原则
```c
// 每个 malloc 必须有对应的 free
void *ptr = pvPortMalloc(size);
// 使用 ptr
vPortFree(ptr);
```

### 2. 使用智能指针（C语言）
```c
// 使用指针包装器
typedef struct {
    void *ptr;
    size_t size;
} Smart_Pointer_t;

Smart_Pointer_t Smart_Malloc(size_t size)
{
    Smart_Pointer_t sp;
    sp.ptr = pvPortMalloc(size);
    sp.size = size;
    return sp;
}

void Smart_Free(Smart_Pointer_t *sp)
{
    if (sp->ptr != NULL) {
        vPortFree(sp->ptr);
        sp->ptr = NULL;
        sp->size = 0;
    }
}
```

### 3. 内存监控
```c
// 监控内存使用
void Monitor_Heap(void)
{
    size_t free_heap = xPortGetFreeHeapSize();
    size_t min_heap = xPortGetMinimumEverFreeHeapSize();
    
    printf("Free heap: %d bytes\r\n", free_heap);
    printf("Min heap: %d bytes\r\n", min_heap);
}
```

## 栈溢出防范

### 1. 静态分析
```c
// 使用静态分析工具
// Keil: Options for Target -> C/C++ -> Analyze Code
```

### 2. 运行时检查
```c
// FreeRTOS 栈溢出钩子
void vApplicationStackOverflowHook(TaskHandle_t xTask, char *pcTaskName)
{
    printf("Stack overflow in task: %s\r\n", pcTaskName);
    // 停止系统
    while(1);
}

// 启用栈溢出检测
#define configCHECK_FOR_STACK_OVERFLOW 2
```

### 3. 栈使用监控
```c
// 检查栈使用情况
void Check_Stack_Usage(void)
{
    UBaseType_t high_water = uxTaskGetStackHighWaterMark(NULL);
    printf("Stack high water mark: %d words\r\n", high_water);
}
```

## 内存对齐

### 对齐原则
1. 按变量大小对齐
2. 结构体成员按大小排序
3. 使用 packed 属性控制对齐

### 示例
```c
// 不好的写法
typedef struct {
    uint8_t a;
    uint32_t b;
    uint8_t c;
} Bad_Struct_t;  // 可能有填充

// 优化后
typedef struct {
    uint32_t b;
    uint8_t a;
    uint8_t c;
} Good_Struct_t;  // 减少填充

// 强制对齐
typedef struct __attribute__((packed)) {
    uint8_t a;
    uint32_t b;
    uint8_t c;
} Packed_Struct_t;
```

## DMA 缓冲区管理

### 对齐要求
```c
// DMA 缓冲区需要对齐
__ALIGN_BEGIN uint8_t dma_buffer[256] __ALIGN_END;

// 或使用编译器属性
uint8_t dma_buffer[256] __attribute__((aligned(4)));
```

### 缓冲区大小
```c
// DMA 缓冲区大小要是传输单元的整数倍
#define DMA_BUFFER_SIZE (256 * 4)  // 4字节对齐
```

## 内存调试技巧

### 1. 内存填充
```c
// 使用特殊值填充未初始化内存
memset(buffer, 0xDEADBEEF, size);
```

### 2. 内存检查
```c
// 检查内存是否被意外修改
void Check_Memory(uint32_t *ptr, size_t size, uint32_t expected)
{
    for (size_t i = 0; i < size/4; i++) {
        if (ptr[i] != expected) {
            printf("Memory corruption at %p\r\n", &ptr[i]);
        }
    }
}
```

### 3. 内存统计
```c
// 统计内存使用
typedef struct {
    size_t total;
    size_t used;
    size_t free;
} Memory_Stats_t;

void Get_Memory_Stats(Memory_Stats_t *stats)
{
    stats->total = configTOTAL_HEAP_SIZE;
    stats->free = xPortGetFreeHeapSize();
    stats->used = stats->total - stats->free;
}
```