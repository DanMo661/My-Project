# Common Peripherals — Quick Reference

Register maps, init sequences, and known quirks for peripherals used across projects.

---

## ADS1115 — 16-bit 4-channel I2C ADC

| Parameter | Value |
|-----------|-------|
| I2C addresses | 0x48 (ADDR→GND), 0x49 (ADDR→VDD), 0x4A (ADDR→SDA), 0x4B (ADDR→SCL) |
| Max I2C speed | 400kHz (fast mode) |

### Registers

| Register | Address | Description |
|----------|---------|-------------|
| Conversion | 0x00 | 16-bit conversion result (read-only) |
| Config | 0x01 | 16-bit configuration |
| Lo_thresh | 0x02 | Low threshold |
| Hi_thresh | 0x03 | High threshold |

### Config Register (0x01) Bits

| Bits | Field | Values |
|------|-------|--------|
| 15 | OS (operational status) | 0: no effect, 1: start conversion (write) / 1: conversion ready (read) |
| 14-12 | MUX[2:0] | 0-3: AINp=AIN0-3, AINn=GND; 4-7: differential pairs |
| 11-9 | PGA[2:0] | 0: ±6.144V, 1: ±4.096V, 2: ±2.048V, 3: ±1.024V, 4: ±0.512V, 5-7: ±0.256V |
| 8 | MODE | 0: continuous, 1: single-shot (power down after conversion) |
| 7-5 | DR[2:0] | 0: 8 SPS, 1: 16, 2: 32, 3: 64, 4: 128, 5: 250, 6: 475, 7: 860 |
| 4 | COMP_MODE | 0: traditional comparator, 1: window comparator |
| 3 | COMP_POL | 0: active low, 1: active high |
| 2 | COMP_LAT | 0: non-latching, 1: latching |
| 1-0 | COMP_QUE[1:0] | 0: 1 conversion, 1: 2, 2: 4, 3: disable comparator |

### Read Sequence

```c
// Write config: AIN0-GND, ±4.096V, continuous, 128SPS
uint8_t config[2] = { 0x42, 0x83 };
HAL_I2C_Master_Transmit(hi2c, addr << 1, config, 2, 100);

// Read conversion: write 0x00 register pointer, then read 2 bytes
uint8_t reg = 0x00;
HAL_I2C_Master_Transmit(hi2c, addr << 1, &reg, 1, 100);
HAL_I2C_Master_Receive(hi2c, addr << 1, raw, 2, 100);
int16_t result = (int16_t)((raw[0] << 8) | raw[1]);  // MSB first
```

### Known Quirk
After writing config, wait for conversion to complete before reading. At 128 SPS, that's ~8ms. Poll the OS bit (bit 15 of config register) or use a delay.

---

## MPU6050 — 6-axis IMU (Accel + Gyro)

| Parameter | Value |
|-----------|-------|
| I2C address | 0x68 (AD0→GND), 0x69 (AD0→VCC) |

### Key Registers

| Register | Address | Notes |
|----------|---------|-------|
| PWR_MGMT_1 | 0x6B | Bit 6: sleep (1=yes). Write 0x00 to wake. |
| SMPRT_DIV | 0x19 | Sample rate = gyro_rate / (1 + value) |
| CONFIG | 0x1A | DLPF config |
| GYRO_CONFIG | 0x1B | Gyro full-scale range |
| ACCEL_CONFIG | 0x1C | Accel full-scale range |
| ACCEL_XOUT_H | 0x3B | Accel data (6 bytes: XH,XL,YH,YL,ZH,ZL) |
| GYRO_XOUT_H | 0x43 | Gyro data (6 bytes) |
| WHO_AM_I | 0x75 | Should return 0x68 |

### Init Sequence

```c
static const struct { uint8_t reg; uint8_t val; } mpu6050_init_seq[] = {
    {0x6B, 0x00},  // Wake up device
    {0x19, 0x07},  // Sample rate divider = 7 → 1kHz / 8 = 125Hz
    {0x1A, 0x06},  // DLPF = 6 → 5Hz bandwidth (good for angles)
    {0x1B, 0x00},  // Gyro ±250 °/s
    {0x1C, 0x00},  // Accel ±2g
};
```

### Scale Factors

| Gyro FS_SEL | Range | Scale (LSB/°/s) |
|-------------|-------|------------------|
| 0 | ±250 | 131.0 |
| 1 | ±500 | 65.5 |
| 2 | ±1000 | 32.8 |
| 3 | ±2000 | 16.4 |

| Accel AFS_SEL | Range | Scale (LSB/g) |
|---------------|-------|---------------|
| 0 | ±2g | 16384 |
| 1 | ±4g | 8192 |
| 2 | ±8g | 4096 |
| 3 | ±16g | 2048 |

### Known Quirks
- Must wake from sleep before any other register writes work. PWR_MGMT_1 write ALWAYS first.
- Self-test response varies per unit. Don't rely on it for calibration.
- Gyro has a startup bias (especially Z). Zero-calibrate by averaging 100 samples at rest.

---

## HMC5883L — 3-axis Magnetometer

| Parameter | Value |
|-----------|-------|
| I2C address | 0x1E (fixed) |
| ID registers | 0x0A=0x48, 0x0B=0x34, 0x0C=0x33 ("H43") |
| Data range | 12-bit two's complement (-2048 ~ +2047) |

### Key Registers

| Register | Address | Notes |
|----------|---------|-------|
| Config A | 0x00 | Bits 6:5=averaging, 4:2=data rate, 1:0=measurement mode |
| Config B | 0x01 | Bits 7:5=gain (GN2:0), bits 4:0 must be 0 |
| Mode | 0x02 | 0x00=continuous, 0x01=single, 0x02=idle |
| Data X MSB | 0x03 | 6 bytes: **X, Z, Y** (Z before Y!) |
| Status | 0x09 | Bit 0=RDY (data ready), Bit 1=LOCK |
| ID A/B/C | 0x0A-0x0C | Chip ID "H43", verify during init |

### Gain Table (CRB)

| GN2:0 | Gain (Ga) | LSB/Ga | CRB Value |
|-------|-----------|--------|-----------|
| 000 | ±0.88 | 1370 | 0x00 |
| 001 | ±1.3 | 1090 | 0x20 (default) |
| 010 | ±1.9 | 820 | 0x40 |
| 011 | ±2.5 | 660 | 0x60 |
| 100 | ±4.0 | 440 | 0x80 |
| 101 | ±4.7 | 390 | 0xA0 |
| 110 | ±5.6 | 330 | 0xC0 |
| 111 | ±8.1 | 230 | 0xE0 |

### Init (Continuous Measurement, 使用 ADS1115 库 I2C 风格)

```c
// 验证 ID: 读 0x0A/0x0B/0x0C，期望 0x48/0x34/0x33
// Config A: 8 次平均, 75Hz, 正常测量
uint8_t cra[] = {0x00, 0x78};
HAL_I2C_Master_Transmit(dev->hi2c, dev->address << 1, cra, 2, HAL_MAX_DELAY);
// Config B: ±1.3Ga
uint8_t crb[] = {0x01, 0x20};
HAL_I2C_Master_Transmit(dev->hi2c, dev->address << 1, crb, 2, HAL_MAX_DELAY);
// Mode: 连续测量
uint8_t mr[] = {0x02, 0x00};
HAL_I2C_Master_Transmit(dev->hi2c, dev->address << 1, mr, 2, HAL_MAX_DELAY);
```

### Conversion

```
gauss = raw_value / LSB_per_Gauss
例如: raw=120, GN=001(1090) → gauss = 120/1090 = 0.110 Ga
heading = atan2(y_gauss, x_gauss) * 180/π; if < 0, += 360
```

### Known Quirks
- Data register order is **X, Z, Y** — NOT X, Y, Z. HMC5883L 独有的寄存器布局。
- Hard-iron distortion from nearby metal and PCB traces. Must calibrate with min/max sweep.
- Not continuous by default — Mode register 0x02 must be set to 0x00.
- Magnetometer data needs tilt compensation (needs accel data from MPU6050).
- CRB gain bits 在 bits 7:5，不在低位。0x20=±1.3Ga(默认)。

---

## nRF24L01 / SI24R1 — 2.4GHz Wireless

| Parameter | Value |
|-----------|-------|
| Interface | SPI (Mode 0: CPOL=0, CPHA=0), max 10MHz |
| CSN pin | Any GPIO (software-controlled) |
| CE pin | Any GPIO |

### Key Registers (SPI command byte: 0x00 + register address for read, 0x20 + address for write)

| Register | Address | Notes |
|----------|---------|-------|
| CONFIG | 0x00 | IRQ mask, CRC, power up, TX/RX mode |
| EN_AA | 0x01 | Auto-ack per pipe |
| RF_SETUP | 0x06 | Data rate, RF power |
| STATUS | 0x07 | IRQ flags, TX full, RX pipe number |
| RX_ADDR_P0 | 0x0A | Pipe 0 address (5 bytes) |
| TX_ADDR | 0x10 | TX address (5 bytes) |
| RX_PW_P0 | 0x11 | Pipe 0 payload width |
| FIFO_STATUS | 0x17 | FIFO empty/full flags |
| R_RX_PAYLOAD | 0x61 | Read RX payload command |
| W_TX_PAYLOAD | 0xA0 | Write TX payload command |
| FLUSH_TX | 0xE1 | Flush TX FIFO |
| FLUSH_RX | 0xE2 | Flush RX FIFO |

### Init Sequence (TX Mode)

```c
// Must be in power-down (PWR_UP=0) to configure
// 1. Set address width = 5 bytes
// 2. Enable auto-ack on pipe 0
// 3. Set channel frequency (2.400 + channel MHz, range 0-125)
// 4. Set data rate + power: 0x06 = 1Mbps, 0dBm; 0x26 = 250kbps, 0dBm
// 5. Set RX/TX addresses (must match on both ends)
// 6. Set payload width for pipe 0
// 7. Power up (PWR_UP=1), wait 1.5ms for crystal
```

### Known Quirks
- SI24R1 is the Chinese clone of nRF24L01. Same register map, cheaper, slightly worse sensitivity.
- Must wait 1.5ms after PWR_UP before transmitting. Crystal startup time.
- CE pin must be HIGH during TX/RX. LOW = standby.
- 2.4GHz WiFi interference is real. Use channel scan or frequency hopping in noisy environments.

---

## SSD1306 — 128x64 OLED (I2C)

| Parameter | Value |
|-----------|-------|
| I2C address | 0x3C (typical), 0x3D (some modules with SA0 tied high) |

### Init Sequence

```c
static const uint8_t oled_init_seq[] = {
    0xAE,        // Display OFF
    0xD5, 0x80,  // Clock divide
    0xA8, 0x3F,  // Mux ratio (64 rows)
    0xD3, 0x00,  // Display offset
    0x40,        // Start line
    0x8D, 0x14,  // Charge pump
    0x20, 0x00,  // Memory mode: horizontal
    0xA1,        // Segment remap
    0xC8,        // COM scan direction
    0xDA, 0x12,  // COM pins
    0x81, 0xCF,  // Contrast
    0xD9, 0xF1,  // Pre-charge
    0xDB, 0x40,  // VCOM detect
    0xA4,        // Display resume
    0xA6,        // Normal display (not inverse)
    0xAF,        // Display ON
};
```

Commands go with prefix 0x00 (control byte), data with prefix 0x40.

### Known Quirks
- I2C OLED modules have a slave address that varies by manufacturer. 0x3C is most common. Run I2C scan if init doesn't work.
- After init, display is cleared. Need to write font/graphics data explicitly.
