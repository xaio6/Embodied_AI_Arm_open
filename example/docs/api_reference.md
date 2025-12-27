# API 参考（Embodied_SDK）

本页面按模块列出 `Embodied_SDK` 的主要入口、参数含义与常用用法，并附带对应示例脚本位置，方便快速对照。

## 快速入口

- **快速入门**：`example/sdk_quickstart.py`
- **Joy-Con 控制**：`example/sdk_joycon_demo.py`、`example/test_joycon_arm_control.py`
- **仿真**：`example/mujoco_control.py`

## 1. 顶层入口：`HorizonArmSDK`

导入：`from Embodied_SDK.horizon_sdk import HorizonArmSDK`

构造参数：
- **motors**：`Dict[int, Any]`，电机控制器字典 `{motor_id: controller}`
- **camera_id**：`int`，摄像头编号（默认 0）

创建后可直接使用这些子模块：

| 属性 | 类型 | 常用用途 |
| :--- | :--- | :--- |
| `vision` | `VisualGraspSDK` | 点击/框选抓取 |
| `follow` | `FollowGraspSDK` | 视觉跟随/伺服 |
| `motion` | `MotionSDK` | 关节/末端运动、夹爪、预设动作 |
| `embodied` | `EmbodiedSDK` | 自然语言任务执行 |
| `io` | `IOSDK` | ESP32 IO 读写 |
| `digital_twin` | `DigitalTwinSDK` | MuJoCo 仿真控制 |
| `joycon` | `JoyconSDK` | Joy-Con 控制（可选） |

## 2. 运动控制：`MotionSDK`

入口：`sdk.motion`

常用接口：
- **`bind_motors(motors, use_motor_config=True, reducer_ratios=None, directions=None)`**：绑定电机上下文
- **`set_motion_params(max_speed=100, acceleration=50, deceleration=50)`**：设置运动参数
- **`move_joints(joint_angles, duration=None) -> bool`**：关节空间运动，`joint_angles` 为 6 个角度（度）
- **`move_cartesian(position, orientation=None, duration=None) -> bool`**：末端运动，`position=[x,y,z]`（mm），`orientation=[yaw,pitch,roll]`（度）
- **`execute_preset_action(name, speed="normal") -> bool`**：执行预设动作（参考 `config/embodied_config/preset_actions.json`）
- **`control_claw(action) -> bool`**：夹爪开合，`action=1` 张开，`action=0` 闭合
- **`set_claw_params(open_angle=None, close_angle=None)` / `get_claw_params()`**：设置/读取夹爪参数

对应示例：`example/sdk_quickstart.py`

## 3. 视觉抓取：`VisualGraspSDK`

入口：`sdk.vision`

常用接口：
- **`bind_motors(motors, use_motor_config=True, reducer_ratios=None, directions=None)`**
- **`set_grasp_params(...)`**：设置抓取姿态、TCP 偏移、抓取深度等参数
- **`grasp_at_pixel(u, v) -> bool`**：抓取像素点（常用于点击）
- **`grasp_at_bbox(x1, y1, x2, y2) -> bool`**：抓取框中心点（常用于框选）

对应文档：`example/docs/vision.md`

## 4. 跟随抓取：`FollowGraspSDK`

入口：`sdk.follow`

常用接口：
- **`configure_follow(...)`**：配置跟随参数（目标类别、阈值、频率等）
- **`follow_step(frame) -> bool`**：单步跟随（推荐）
- **`start_follow_grasp(...)` / `stop_follow_grasp()` / `is_following()`**：后台循环跟随
- **`init_manual_target(frame0, x1, y1, x2, y2) -> bool`**：手动框选初始化跟踪器

## 5. Joy-Con：`JoyconSDK`

入口：`from Embodied_SDK.joycon import JoyconSDK`

常用接口：
- **`connect_joycon() -> (left_ok, right_ok)`**
- **`bind_arm(motors, use_motor_config=True, kinematics=None, mujoco_controller=None)`**
- **`start_control()` / `stop_control()` / `pause_control()` / `resume_control()`**
- **`toggle_mode()`**：切换关节/笛卡尔模式
- **`emergency_stop()`**：急停
- **`get_status() -> dict`**：读取控制状态
- **`get_left_joycon_status()` / `get_right_joycon_status()`**：读取手柄原始状态（用于终端监控）

对应示例：
- `example/sdk_joycon_demo.py`
- `example/test_joycon_display.py`

## 6. IO：`IOSDK`

入口：`from Embodied_SDK.io import IOSDK`

常用接口：
- **`connect() -> bool` / `disconnect()`**
- **`read_di(pin)` / `read_di_states()`**
- **`set_do(pin, state)` / `set_do_all(states)`**
- **`read_do_states()` / `reset_all_do()` / `pulse_do(pin, duration=0.1)`**
- **`get_version()` / `get_status()`**

## 7. 自然语言：`EmbodiedSDK`

入口：`from Embodied_SDK.embodied import EmbodiedSDK`

常用接口：
- **`run_nl_instruction(instruction) -> dict`**
- **`run_nl_instruction_stream(instruction, action_handler=None, progress_handler=None, completion_handler=None)`**
- **`get_available_functions() -> Dict[str, str]`**
- **`clear_history()` / `get_history()`**

## 8. 仿真：`DigitalTwinSDK`

入口：`from Embodied_SDK.digital_twin import DigitalTwinSDK`

常用接口：
- **`start_simulation() -> bool` / `stop_simulation()` / `is_running() -> bool`**
- **`set_joint_angles(angles) -> bool`**：直接设置关节角（用于同步/波形）
- **`move_joints(joint_angles, duration=None) -> bool`**
- **`move_cartesian(position, orientation=None, duration=None) -> bool`**
- **`execute_preset_action(name, speed="normal") -> bool`**
- **`clear_trajectory() -> bool`**

对应示例：`example/mujoco_control.py`


