# Layered Architecture for STM32 Firmware

## Three-Layer Model

```
┌──────────────────────────────────────────┐
│ Application Layer                        │
│ User/main.c, FreeRTOS tasks, app logic   │
│ Never calls HAL directly                 │
├──────────────────────────────────────────┤
│ Hardware Abstraction Layer (HAL²)        │
│ Hardware/sensor.c, Hardware/motor.c, ... │
│ One module per peripheral (.h + .c)      │
│ .h = public API, .c = implementation     │
├──────────────────────────────────────────┤
│ Driver Layer                             │
│ Core/Src/ (CubeMX generated)             │
│ Drivers/STM32xxxx_HAL_Driver/  ← Auto-detected from chip family            │
│ DO NOT MODIFY                            │
└──────────────────────────────────────────┘
```

## Rules Per Layer

### Application Layer

**Allowed:**
- Call Hardware/ APIs (e.g., `ADS1115_ReadChannel(&dev, 0)`)
- Manage FreeRTOS tasks and queues
- Implement business logic (PID loops, state machines)
- Use debug_printf for logging

**Forbidden:**
- Direct HAL calls (`HAL_I2C_Master_Transmit` in main.c)
- Direct register access
- Including sensor chip header files directly (use the Hardware module's .h)

**Why:** If CubeMX regenerates and changes HAL handles, only the Hardware layer needs updating, not all of main.c.

### Hardware Abstraction Layer

Each module = one .h + one .c file.

**.h file contents (in order):**
1. Include guard (`#ifndef __MODULE_H__`)
2. Standard includes (`#include "main.h"`)
3. Public macros (device address, register addresses)
4. Public type definitions (device struct, config struct, data struct)
5. Public function declarations

**.c file contents (in order):**
1. `#include "ModuleName.h"`
2. Static helper functions (hidden from callers)
3. Public function implementations

**Why separate .h/.c:** Callers only see the API. Implementation details (register maps, bit manipulation) stay hidden. If the chip changes (e.g., from MPU6050 to ICM-42688), only the .c file changes.

### Driver Layer

CubeMX generates this. Only add code between USER CODE markers:

```c
/* USER CODE BEGIN 0 */
// Your code here — survives regeneration
/* USER CODE END 0 */
```

After every CubeMX regeneration:
1. Check that your USER CODE blocks are intact
2. Re-add Hardware/ source files to the Keil project groups (CubeMX strips them)

## Passing Data Between Layers

### Correct: Struct pointer

```c
// Hardware layer defines
typedef struct {
    float pitch, roll, yaw;
} Attitude_t;

void MPU6050_GetAttitude(MPU6050_Device_t *dev, Attitude_t *out);

// Application layer uses
Attitude_t att;
MPU6050_GetAttitude(&imu, &att);
pid_update(&att.pitch);  // clean, clear
```

### Wrong: Global variables

```c
// Don't do this
float g_gyro_x, g_gyro_y, g_gyro_z;  // scattered, no owner, no thread safety
```

## Adding a New Module Checklist

1. Create `Hardware/ModuleName.h` with include guard, structs, API declarations
2. Create `Hardware/ModuleName.c` with all static helpers and public implementations
3. In Keil: add .c to the Hardware project group
4. In Keil: add `Hardware/` to include paths if not already
5. In main.c or task file: `#include "ModuleName.h"`, declare device, call Init
