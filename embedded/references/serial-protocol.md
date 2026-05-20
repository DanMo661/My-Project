# Serial Protocol Design for MCU ↔ Host Communication

## Standard Frame Format

```
:value1,value2,...,valueN\r\n
```

| Element | Purpose | Example |
|---------|---------|---------|
| `:` | Frame start marker (sync character) | `:` |
| `val1,...` | Comma-separated data fields | `12.50,-3.20,11.00` |
| `\r\n` | Frame end (CR+LF) | `\r\n` |

## MCU Side (Sender)

```c
// Simple printf-based sender — fits in main loop or a FreeRTOS task
void SendSensorFrame(SensorData_t *data) {
    printf(":%.2f,%.2f,%.2f,%.2f\r\n",
           data->ch0_voltage, data->ch1_voltage,
           data->temperature, data->vbat);
}

// Call from main loop with timing control
while (1) {
    SensorData_t data;
    ADS1115_ReadAllChannels(&adc_dev, &data);
    SendSensorFrame(&data);
    HAL_Delay(50);  // 20Hz — adjust based on sensor speed and UART bandwidth
}
```

## UART Bandwidth Check

At 115200 baud, 8N1: ~11.5 KB/s theoretical, ~10 KB/s practical.

One frame of 10 float values with `:` and `,` separators: ~70 bytes.
70 bytes × 20Hz = 1400 bytes/s — well within limits.

Warning: 100Hz with 15 floats ≈ 7 KB/s, approaching the limit. Use higher baud (230400, 460800) or reduce data.

## Float Format Guidelines

```c
// Match precision to sensor resolution
printf("%.2f", voltage);    // 12-bit ADC → ~3 significant digits, use %.2f
printf("%.4f", angle);      // High-precision IMU → use %.4f
printf("%d", raw_adc);      // Raw integer — no decimal point needed
```

Don't send unnecessary decimal places past the sensor's actual resolution. It wastes UART bandwidth and implies false precision.

## Host Side (Python Parser)

```python
def parse_frame(line: str):
    """Parse a colon-prefixed CSV frame. Returns list of floats or None."""
    line = line.strip()
    if not line.startswith(':'):
        return None  # not a valid frame
    try:
        parts = line[1:].split(',')
        values = [float(p) for p in parts]
        return values
    except (ValueError, IndexError):
        return None  # malformed frame
```

## Number of Channels and Scaling

Frame design checklist:

1. **How many channels?** One value per sensor channel
2. **What units?** MCU sends raw sensor units (volts, degrees). Host converts for display
3. **Scaling factor?** Use fixed-point if float is too heavy: `printf(":%d,%d,%d\r\n", (int)(angle*100), ...)` → host divides by 100
4. **Channel order?** Document it. Consistent order on both sides. Add a header frame on startup that lists channel names

## Robust Parsing (Host)

```python
# Full serial reader with buffering
def serial_reader_thread(port, baud, data_queue):
    ser = serial.Serial(port, baud, timeout=0.5)
    buf = ''
    while True:
        chunk = ser.read(ser.in_waiting or 1).decode('utf-8', errors='ignore')
        buf += chunk
        while '\n' in buf:
            line, buf = buf.split('\n', 1)
            values = parse_frame(line)
            if values is not None:
                data_queue.put(values)
```

Key points:
- `errors='ignore'` prevents crash on garbled bytes
- Line buffering handles partial reads (serial.read doesn't guarantee full lines)
- `data_queue` decouples serial thread from UI thread

## Simulation / Testing Without Hardware

```python
import serial, time, math, random

ser = serial.Serial('COM3', 115200)
while True:
    t = time.time()
    ch0 = 1.65 + 0.5 * math.sin(t * 2) + random.uniform(-0.02, 0.02)
    ch1 = 3.30 + 0.3 * math.cos(t * 1.5)
    ser.write(f':{ch0:.2f},{ch1:.2f}\r\n'.encode())
    time.sleep(0.05)
```

This lets you develop and test the host UI before the hardware is ready.
