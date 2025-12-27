# IOSDK - IO 控制

**对应源码：** `Embodied_SDK/io.py`

## 概述

`IOSDK` 提供 ESP32 IO 控制能力，支持数字输入/输出（DI/DO）的读写操作。

## 前置条件

- ESP32 IO 控制器已连接
- 已烧录对应固件
- 串口连接正常

---

## 模块入口

### 通过顶层 SDK

```python
from Embodied_SDK import HorizonArmSDK

sdk = HorizonArmSDK(motors=motors)
io = sdk.io  # 获取 IOSDK 实例
```

### 独立使用

```python
from Embodied_SDK.io import IOSDK

io = IOSDK(port="COM15", baudrate=115200)
```

---

## 核心接口

### 1. 连接管理

#### `connect() -> bool`

连接 IO 控制器。

**返回值：**
- `True`: 连接成功
- `False`: 连接失败

**示例：**
```python
if io.connect():
    print("✅ IO 控制器已连接")
else:
    print("❌ 连接失败")
```

#### `disconnect()`

断开连接。

```python
io.disconnect()
```

---

### 2. 数字输入（DI）

#### `read_di(pin) -> bool`

读取单个数字输入引脚状态。

**参数：**
- `pin`: 引脚编号（通常 0-7）

**返回值：**
- `True`: 高电平
- `False`: 低电平

**示例：**
```python
state = io.read_di(0)
print(f"DI0 状态: {'HIGH' if state else 'LOW'}")
```

#### `read_di_states() -> dict`

读取所有数字输入引脚状态。

**返回值：**
- `dict`: `{pin: state}` 字典

**示例：**
```python
states = io.read_di_states()
print("所有 DI 状态:")
for pin, state in states.items():
    print(f"  DI{pin}: {'HIGH' if state else 'LOW'}")
```

---

### 3. 数字输出（DO）

#### `set_do(pin, state) -> bool`

设置单个数字输出引脚状态。

**参数：**
- `pin`: 引脚编号
- `state`: 状态（`True`/`1` = 高电平，`False`/`0` = 低电平）

**返回值：**
- `True`: 设置成功
- `False`: 设置失败

**示例：**
```python
# 设置 DO0 为高电平
io.set_do(0, True)

# 设置 DO1 为低电平
io.set_do(1, False)
```

#### `set_do_all(states) -> bool`

批量设置所有数字输出引脚。

**参数：**
- `states`: 状态字典 `{pin: state}` 或状态列表

**示例：**
```python
# 使用字典
io.set_do_all({0: True, 1: False, 2: True})

# 使用列表（按引脚顺序）
io.set_do_all([True, False, True, False, True, False, True, False])
```

---

### 4. 状态查询

#### `read_do_states() -> dict`

读取所有数字输出引脚的当前状态。

**返回值：**
- `dict`: `{pin: state}` 字典

**示例：**
```python
states = io.read_do_states()
print("所有 DO 状态:")
for pin, state in states.items():
    print(f"  DO{pin}: {'HIGH' if state else 'LOW'}")
```

---

### 5. 辅助功能

#### `reset_all_do()`

重置所有数字输出为低电平。

```python
io.reset_all_do()
print("所有 DO 已重置")
```

#### `pulse_do(pin, duration=0.1) -> bool`

在指定引脚上产生脉冲信号。

**参数：**
- `pin`: 引脚编号
- `duration`: 脉冲持续时间（秒）

**使用场景：**
- 触发继电器
- 发送触发信号

**示例：**
```python
# 在 DO0 上产生 100ms 的脉冲
io.pulse_do(0, duration=0.1)
```

---

### 6. 设备信息

#### `get_version() -> str`

获取 IO 控制器固件版本。

```python
version = io.get_version()
print(f"固件版本: {version}")
```

#### `get_status() -> dict`

获取设备状态信息。

**返回值：**
- `dict`: 包含连接状态、引脚状态等信息

**示例：**
```python
status = io.get_status()
print(f"连接状态: {status['connected']}")
print(f"DI 数量: {status['di_count']}")
print(f"DO 数量: {status['do_count']}")
```

---

## 完整示例

### 基础 IO 操作

```python
from Embodied_SDK.io import IOSDK
import time

# 1. 创建 IOSDK 实例
io = IOSDK(port="COM15", baudrate=115200)

# 2. 连接设备
if not io.connect():
    print("连接失败")
    exit(1)

print("✅ IO 控制器已连接")

# 3. 读取数字输入
print("\n读取数字输入:")
di_states = io.read_di_states()
for pin, state in di_states.items():
    print(f"  DI{pin}: {'HIGH' if state else 'LOW'}")

# 4. 控制数字输出
print("\n控制数字输出:")
io.set_do(0, True)   # DO0 高电平
print("  DO0: HIGH")
time.sleep(1)

io.set_do(0, False)  # DO0 低电平
print("  DO0: LOW")

# 5. 批量设置
print("\n批量设置 DO:")
io.set_do_all({0: True, 1: True, 2: False, 3: False})
print("  DO0-1: HIGH, DO2-3: LOW")
time.sleep(1)

# 6. 重置所有 DO
print("\n重置所有 DO")
io.reset_all_do()

# 7. 断开连接
io.disconnect()
print("\n✅ 已断开连接")
```

---

### 循环监控输入

```python
from Embodied_SDK.io import IOSDK
import time

io = IOSDK(port="COM15")
if not io.connect():
    exit(1)

print("开始监控数字输入，按 Ctrl+C 退出")

try:
    while True:
        # 读取所有输入
        states = io.read_di_states()
        
        # 检测 DI0 变化
        if states.get(0):
            print("⚠️  DI0 触发！")
            # 执行相应操作
            io.set_do(0, True)  # 点亮指示灯
            time.sleep(0.5)
            io.set_do(0, False)
        
        time.sleep(0.1)  # 10Hz 轮询
        
except KeyboardInterrupt:
    print("\n停止监控")
    
io.disconnect()
```

---

### 与机械臂联动

```python
from Embodied_SDK import HorizonArmSDK, create_motor_controller
import time

# 1. 初始化机械臂和 IO
motors = {mid: create_motor_controller(motor_id=mid, port="COM14") for mid in range(1, 7)}
for m in motors.values():
    m.connect()

sdk = HorizonArmSDK(motors=motors)
io = sdk.io
io.connect()

print("机械臂 + IO 联动控制")
print("DI0: 触发回到初始位置")
print("DI1: 触发抓取动作")

try:
    while True:
        # 读取输入
        di_states = io.read_di_states()
        
        # DI0 触发 - 回到初始位置
        if di_states.get(0):
            print("触发: 回到初始位置")
            sdk.motion.move_joints([0, 0, 0, 0, 0, 0])
            io.set_do(0, True)  # 指示灯
            time.sleep(0.5)
            io.set_do(0, False)
        
        # DI1 触发 - 抓取
        if di_states.get(1):
            print("触发: 抓取动作")
            sdk.motion.execute_preset_action("pick")
            io.set_do(1, True)  # 指示灯
            time.sleep(0.5)
            io.set_do(1, False)
        
        time.sleep(0.1)
        
except KeyboardInterrupt:
    print("\n停止")

# 清理
io.disconnect()
for m in motors.values():
    m.disconnect()
```

---

## 引脚说明

### 数字输入（DI）

通常 DI0-DI7，8 个输入引脚。

**典型用途：**
- 传感器信号检测
- 按钮输入
- 限位开关
- 外部触发信号

### 数字输出（DO）

通常 DO0-DO7，8 个输出引脚。

**典型用途：**
- 控制继电器
- 指示灯
- 外部设备触发
- 信号输出

---

## 配置文件

### IO 映射配置

可在 `config/io_control/io_mapping.json` 中定义引脚映射：

```json
{
  "inputs": {
    "emergency_stop": 0,
    "start_button": 1,
    "sensor_1": 2
  },
  "outputs": {
    "indicator_green": 0,
    "indicator_red": 1,
    "relay_1": 2
  }
}
```

---

## 注意事项

1. **电气安全**：
   - 确认电压电平匹配
   - 使用继电器隔离高压设备

2. **响应时间**：
   - 串口通信有延迟
   - 不适用于实时性要求极高的场景

3. **引脚保护**：
   - 避免短路
   - 使用合适的电流限制

---

## 相关文档

- [MotionSDK](motion.md) - 与机械臂联动
- [配置说明](configuration.md) - IO 映射配置
- [API 详细参考](api_detailed.md) - 完整 API 说明

## 示例脚本

- **`example/test_io.py`**  
  **用途：** IO 控制综合测试工具。  
  **功能：** 提供交互式菜单，支持读取所有 DI 状态、控制 DO 引脚以及实时监控模式。

- `config/io_control/` - IO 配置示例

