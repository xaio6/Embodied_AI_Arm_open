# 驱动扩展

本章节面向需要接入不同厂商/不同协议驱动板的开发者，说明如何扩展电机驱动实现，并让上层继续使用统一的 `motors` 字典。

## 1. 目标与原则

- **目标**：让上层始终只依赖统一的“电机控制器接口”，无需关心实际连接的驱动板型号。
- **原则**：
  - 上层逻辑只拿到 `motors: Dict[int, MotorController]`
  - 控制器需要实现一组最小方法（连接、断开、多机命令、同步等）
  - 新驱动通过“注册机制”接入，做到可插拔

## 2. 统一使用方式

建议保持以下写法（无论使用哪种驱动）：

- `motors` 字典结构固定：`{motor_id: controller_instance}`
- 交给 `HorizonArmSDK` 或各子 SDK 绑定即可：
  - `sdk = HorizonArmSDK(motors=motors)`
  - 或 `sdk.motion.bind_motors(motors)` / `sdk.vision.bind_motors(motors)`

## 3. 驱动扩展的“注册”方式

系统提供了统一的驱动注册入口：

- `Horizon_Core.gateway.register_motor_driver(name, controller_cls, builder_cls=None, parser_cls=None)`
- `Horizon_Core.gateway.set_default_motor_driver(name)`

其中：
- `controller_cls`：你的电机控制器类（负责连接、发命令、读状态等）
- `builder_cls`（可选）：命令构建器（将“位置/速度/力矩”等抽象参数变成协议字节）
- `parser_cls`（可选）：响应解析器（将协议回复解析成结构化数据）

> 如果你的驱动板协议与现有命令体系差异很大，可以只实现 `controller_cls`，并在控制器类里自行处理协议帧；`builder/parser` 仅用于把“命令构建/解析”模块化拆分。

## 4. 控制器需要实现哪些能力

电机控制器需要满足上层调用的最小能力集合：

### 4.1 连接管理

- `connect(motor_id: Optional[int] = None) -> None`
- `disconnect() -> None`

说明：
- 支持“构造时指定 motor_id”或“connect 时指定 motor_id”
- 多电机场景建议支持共享通信接口（同一条总线、多实例共享）

### 4.2 单电机控制能力（最小）

上层常用到的最小能力（用于关节控制/末端控制的下发）：

- `enable() -> None`
- `disable() -> None`
- `move_to_position(position: float, **kwargs) -> None`
- `get_position() -> float`
- `is_in_position() -> bool`

> `**kwargs` 的存在是为了让不同驱动板可以扩展自己的速度/加速度/绝对/相对等参数，同时不破坏统一接口。

### 4.3 多电机同步能力（推荐）

为了支持“多电机同起同停”的一致性（更好的轨迹一致性与手感），建议提供：

- `multi_motor_command(per_motor_commands: list, expected_ack_motor_id: int = 1, timeout: float = 1.0, wait_ack: bool = True, mode: str = None)`
- `sync_motion() -> None`

说明：
- 若你的驱动板支持“聚合帧一次下发多电机命令”，可实现 `multi_motor_command`
- 若你的驱动板只支持“各电机先缓存同步标志，最后统一触发”，则实现 `sync_motion`

## 5. 推荐的接入步骤

1. **实现你的控制器类**：满足第 4 节的最小接口
2. **（可选）实现 builder/parser**：把协议帧构建与解析拆出去，便于维护与复用
3. **注册驱动**：
   - `gateway.register_motor_driver("your_driver", YourController, YourBuilder, YourParser)`
4. **（可选）设置默认驱动**：
   - `gateway.set_default_motor_driver("your_driver")`
5. **在业务侧创建 motors**：
   - 使用 `create_motor_controller(..., driver_name="your_driver")`（如果你选择走统一工厂）
   - 或直接实例化你的 `YourController(...)`

## 6. 常见坑与建议

- **motor_id 统一约定**：建议仍使用 1-6 映射到 J1-J6（或你的实际关节数量），保证上层 `move_joints([J1..J6])` 的语义不变。
- **单位统一**：上层通常以“度/毫米/秒”为单位，你的驱动可以自由换算，但建议在控制器层把单位统一好，减少上层误用。
- **线程安全**：如果你允许多线程读取状态/下发命令，请在底层通信层做串行化（避免命令与响应交叉）。
- **超时与降级**：某些设备在特定响应模式下不会回 ACK，建议允许 `wait_ack=False` 并做好降级发送策略。

