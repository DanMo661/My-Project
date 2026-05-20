# FreeRTOS on STM32F103

## Memory Budget

STM32F103C8T6: 20KB SRAM total. FreeRTOS heap: ~12KB (configTOTAL_HEAP_SIZE).
STM32F103RCT6: 48KB SRAM total. FreeRTOS heap: ~30KB.

Rule of thumb: each task costs stack + TCB (task control block, ~100 bytes).
3 tasks × 128 words = 3 × 512 bytes = 1536 bytes. Plus heap overhead. Leave headroom.

## Task Creation Template

```c
/* ----- Task defines (in the task's .c or a shared config.h) ----- */
#define SENSOR_TASK_STACK    256    // words, not bytes
#define SENSOR_TASK_PRIO     1

/* ----- Task handle ----- */
static TaskHandle_t sensor_task_handle;

/* ----- Task function ----- */
static void SensorTask(void *param) {
    Sensor_Device_t *dev = (Sensor_Device_t *)param;
    TickType_t last_wake = xTaskGetTickCount();

    for (;;) {
        // Work
        SensorData_t data;
        dev->Read(dev, &data);
        // Send to queue, process, etc.

        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(50));  // precise 20Hz
    }
}

/* ----- Creation (in App_freeRTOS_start or equivalent) ----- */
BaseType_t ret;
ret = xTaskCreate(SensorTask, "sensor", SENSOR_TASK_STACK,
                  &imu_dev, SENSOR_TASK_PRIO, &sensor_task_handle);
if (ret != pdPASS) {
    // Task creation failed — likely out of heap
    Error_Handler();
}
```

## Stack Sizing

| Task type | Recommended stack (words) | Rationale |
|-----------|--------------------------|-----------|
| Simple LED blink / flag setter | 64 | Minimal locals |
| Sensor reader (I2C) | 128-256 | HAL I2C uses stack buffers |
| Serial printf / logger | 256-512 | printf internals need lots of stack |
| PID control loop | 256 | Float math + state variables |
| Flight controller fusion | 512-1024 | Madgwick/DMP + multiple sensors |

Start high (256), verify with `uxTaskGetStackHighWaterMark()`, then reduce.

## Stack High Water Mark Check

```c
// In a debug task or main loop
UBaseType_t high_water = uxTaskGetStackHighWaterMark(sensor_task_handle);
debug_printf("Sensor task stack free: %u words\r\n", high_water);
// If this is < 20 words, increase the stack immediately
```

## Priority Assignment

```c
#define PRIO_IDLE     (tskIDLE_PRIORITY)       // 0 — never use for user tasks
#define PRIO_LOW      1                         // housekeeping, logging
#define PRIO_MID      2                         // sensor reading, UI updates
#define PRIO_HIGH     3                         // control loops (PID, stabilization)
#define PRIO_CRITICAL 4                         // emergency stop, motor kill
```

Only go higher if you have measured that a lower priority causes missed deadlines.

## Task Notification (ISR → Task)

Faster than semaphores for simple "new data ready" signaling:

```c
// In ISR (e.g., EXTI callback for data ready pin)
void HAL_GPIO_EXTI_Callback(uint16_t pin) {
    if (pin == MPU6050_INT_PIN) {
        BaseType_t higher_prio_woken = pdFALSE;
        vTaskNotifyGiveFromISR(sensor_task_handle, &higher_prio_woken);
        portYIELD_FROM_ISR(higher_prio_woken);
    }
}

// In task — wait for notification
void SensorTask(void *param) {
    for (;;) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);  // blocks until ISR fires
        MPU6050_ReadAccel(&imu, &data);
    }
}
```

## Common FreeRTOS Pitfalls

| Problem | Cause | Fix |
|---------|-------|-----|
| HardFault on `vTaskStartScheduler` | Stack overflow on first task | Increase configTOTAL_HEAP_SIZE or task stack |
| Task never runs | Priority too low, higher task never yields | Add vTaskDelay in all higher-priority loops |
| printf crashes in task | Stack too small for printf | 512 words minimum for printf tasks |
| Data corruption | Two tasks writing same variable | Use queue, semaphore, or taskENTER_CRITICAL |
| `xTaskCreate` returns errCOULD_NOT_ALLOCATE_REQUIRED_MEMORY | Heap exhausted | Reduce heap usage, check for leaks, increase heap |
