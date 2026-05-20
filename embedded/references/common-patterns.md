# Common Patterns

常用代码模式和调试技巧。

---

## 串口调试

### printf to UART（每个项目都需要）

```c
// 放在 main.c USER CODE BEGIN 0
int fputc(int ch, FILE *f) {
    HAL_UART_Transmit(&huart2, (uint8_t *)&ch, 1, 0xFFFF);
    return ch;
}
```

Keil → Target Options → Target → 勾选 "Use MicroLIB"。

### debug_printf 宏

```c
#define DEBUG_LOG_ENABLE  1
#if DEBUG_LOG_ENABLE
#define debug_printf(fmt, ...)  printf("[%s:%d] " fmt, __FILE__, __LINE__, ##__VA_ARGS__)
#else
#define debug_printf(fmt, ...)
#endif
```

**注意**：printf 很耗 CPU（~1ms/10字节）。在时间关键循环（PID、飞控）中禁用。

---

## 上下位机串口协议

标准帧格式（跨项目通用）：

```
:val1,val2,...,valN\r\n
```

- 冒号前缀用于帧同步
- 逗号分隔的浮点值（printf 用 `%.2f` 或 `%d`）
- CR+LF 终止符
- 115200 波特率，8N1

**MCU 端：**
```c
printf(":%.2f,%.2f,%.2f\r\n", angle, speed, battery);
HAL_Delay(50);  // 20Hz 帧率
```

**上位机（Python）**：行缓冲解析，按 `:` 分割同步，验证字段数量，推送到可视化。

详细协议设计见 `references/serial-protocol.md`。

---

## FreeRTOS Task 模板

```c
#define TASK_STACK_MIN  128   // words (128 words = 512 bytes on Cortex-M3)
#define TASK_PRIO_LOW   0
#define TASK_PRIO_MID   1     // default for sensor tasks
#define TASK_PRIO_HIGH  2     // for control loops (PID, flight)

void SensorTask(void *param) {
    Sensor_Device_t *dev = (Sensor_Device_t *)param;
    for (;;) {
        dev->Read(dev);
        vTaskDelay(pdMS_TO_TICKS(50));  // 20Hz
    }
}
// 在 main 或 init 函数中：
xTaskCreate(SensorTask, "sensor", 256, &imu_dev, TASK_PRIO_MID, NULL);
```

**规则：**
- Stack 单位是 words，不是 bytes。每个任务最少 128 words。
- 任务体必须是 `for(;;)` + `vTaskDelay()` 让出 CPU
- 优先级范围：0 (idle) 到 `configMAX_PRIORITIES-1`
- ISR 到任务通知：`vTaskNotifyGiveFromISR` + `ulTaskNotifyTake`
- Heap 大小取决于 SRAM（F103C8T6: ~12KB，F407: ~192KB total）

详细 FreeRTOS 配置见 `references/freertos-setup.md`。

---

## 常见错误调试

| 现象 | 可能原因 | 检查 |
|------|---------|------|
| I2C 设备无应答 | 地址错或缺上拉电阻 | 7-bit 地址要 `<< 1`。检查 SCL/SDA 4.7kΩ 上拉 |
| CubeMX 覆盖代码 | 代码在 USER CODE BEGIN/END 外 | 只在标记之间添加代码 |
| printf 无输出 | MicroLIB 未启用，UART 错 | Keil Target → Use MicroLIB。验证 UART handle |
| FreeRTOS 启动后 HardFault | 栈溢出 | 增加任务栈大小，检查 heap 大小 |
| 串口数据乱码 | 波特率不匹配或噪声 | 验证两端 115200 8N1。检查 GND 连接 |
| CubeMX 重新生成后编译错 | Hardware/ 文件未重新添加到 Keil | 在 Keil 项目组中重新添加 .c 文件 |
| 未定义 HAL 函数引用 | CubeMX 中未启用 HAL 模块 | 在 .ioc 中启用外设并重新生成 |
