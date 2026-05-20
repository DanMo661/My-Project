# Naming Conventions

## Quick Reference

| Category | Convention | Good | Bad |
|----------|-----------|------|-----|
| Function | `Module_Action` | `ADS1115_Init`, `Motor_SetPWM`, `UART_SendFrame` | `init_ads`, `SendData` |
| Local variable | `snake_case` | `adc_raw`, `pitch_angle`, `byte_count` | `adcRaw`, `i`, `tmp1` |
| Global variable | `g_snake_case` | `g_sys_tick`, `g_data_ready` | `SysTick`, `data_flag` |
| Struct type | `Module_Xxx_t` | `ADS1115_Device_t`, `PID_Config_t`, `IMU_Data_t` | `ads_device`, `SConfig` |
| Enum type | `Module_Xxx_t` | `ADS1115_Channel_t`, `SensorState_t` | `state_t`, `Dir` |
| Enum value | `MODULE_VAL_NAME` | `ADS1115_MUX_AIN0_GND`, `SENSOR_STATE_IDLE` | `idle`, `DIR1` |
| Macro/constant | `UPPER_SNAKE` | `MPU6050_ADDR`, `TASK_STACK_MIN` | `mpuAddr`, `stackmin` |
| Pin define | `PERIPH_FUNC_PORT` | `I2C1_SCL_PORT`, `LED_GPIO_PORT` | `SCL_PIN`, `p_led` |
| File name | `ModuleName.h/.c` | `ADS1115.h`, `MotorControl.c` | `ads1115.h`, `motor_control.c` |

## Function Naming

Pattern: `[Module]_[Action][Target]`

```c
// Init
ADS1115_Init(ADS1115_Device_t *dev);
MPU6050_Init(MPU6050_Device_t *dev, MPU6050_Config_t *cfg);

// Single read
ADS1115_ReadChannel(ADS1115_Device_t *dev, uint8_t ch);
MPU6050_ReadAccel(MPU6050_Device_t *dev, IMU_Data_t *out);

// Block read
HMC5883L_ReadMagnetometer(HMC5883L_Device_t *dev, MagData_t *out);

// Write / set
Motor_SetSpeed(Motor_Device_t *dev, int16_t speed);
OLED_SetCursor(OLED_Device_t *dev, uint8_t page, uint8_t col);

// Check state
ADS1115_IsReady(ADS1115_Device_t *dev);
```

Common action verbs: `Init`, `Read`, `Write`, `Set`, `Get`, `Start`, `Stop`, `Reset`, `IsReady`, `IsError`.

## Variable Naming

```c
// Counts, totals — prefix with what's counted
uint16_t byte_count;    // not `count`, `cnt`, `n`
uint8_t  sample_index;  // not `index`, `i` (i is OK as a tight loop iterator)

// Raw vs converted
uint16_t adc_raw;       // what the register returns
float    adc_voltage;   // after conversion

// Flags — noun + adjective
uint8_t data_ready;     // not `flag`, `stat`
uint8_t transfer_done;

// Sensor data — noun + axis
float pitch_angle;      // not `angle1`, `a_pitch`
float roll_angle;
float yaw_angle;        // or yaw_rate for gyro

// Timestamps
uint32_t last_read_tick;  // HAL_GetTick() value
```

## Things to Avoid

- Hungarian notation: no `iCount`, `fVoltage`, `pData`
- Single letters except loop iterators (`i`, `j`) and coordinate axes (`x`, `y`, `z`)
- Abbreviations that aren't universal: `tmp` → `temp`, `cfg` → `config`, `buf` → `buffer` (only when universally clear)
- `_t` suffix outside of typedef structs/enums (it's reserved by POSIX, but STM32 HAL uses it anyway — we follow the HAL convention)
- `__` (double underscore) in include guards — C 标准保留给实现使用。用 `MODULE_H`，不用 `__MODULE_H__`
