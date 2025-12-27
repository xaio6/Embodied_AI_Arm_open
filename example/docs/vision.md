# VisualGraspSDK & FollowGraspSDK - 视觉抓取与跟随

**对应源码：** `Embodied_SDK/visual_grasp.py`

## 概述

视觉模块提供两个 SDK：
- **VisualGraspSDK**: 基础视觉抓取（像素点抓取、框选抓取）
- **FollowGraspSDK**: 视觉跟随（目标检测跟随、手动框选跟踪）

## 前置条件

### 硬件要求
- USB 摄像头或工业相机
- 相机已正确连接并可被系统识别

### 软件要求
- ⚠️ **必需**：已完成相机标定（`config/calibration_parameter.json`）
- 对于目标检测跟随：需要 YOLO 模型（`config/yolov8n.onnx`）

---

## VisualGraspSDK - 基础视觉抓取

### 模块入口

```python
from Embodied_SDK import HorizonArmSDK

sdk = HorizonArmSDK(motors=motors, camera_id=0)
vision = sdk.vision  # 获取 VisualGraspSDK 实例
```

### 核心接口

#### 1. 设置抓取参数

##### `set_grasp_params(grasp_height=50, approach_height=100, tcp_offset=None, retreat_height=150, grasp_orientation=None)`

**参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `grasp_height` | 50 | 抓取高度（mm），相对于桌面 |
| `approach_height` | 100 | 接近高度（mm），抓取前的安全高度 |
| `tcp_offset` | `[0,0,120]` | 工具中心点偏移 [x,y,z]（mm） |
| `retreat_height` | 150 | 抓取后抬升高度（mm） |
| `grasp_orientation` | `[0,0,180]` | 抓取姿态 [yaw,pitch,roll]（度） |

**⚠️ 注意：**
- `grasp_height` 不要设置过低，避免碰撞桌面
- `tcp_offset` 需根据夹爪实际长度调整
- 首次使用建议从较高的 `grasp_height`（如 100mm）开始测试

**示例：**
```python
vision.set_grasp_params(
    grasp_height=80,
    approach_height=150,
    tcp_offset=[0, 0, 120],
    retreat_height=200
)
```

---

#### 2. 像素点抓取

##### `grasp_at_pixel(u, v) -> bool`

根据像素坐标抓取目标。

**参数：**
- `u, v`: 像素坐标

**使用场景：**
- Web/GUI 用户点击抓取
- ROS 节点接收点击坐标
- 已知目标的像素位置

**示例：**
```python
import cv2

cap = cv2.VideoCapture(0)
ret, frame = cap.read()

if ret:
    h, w = frame.shape[:2]
    center_u, center_v = w // 2, h // 2
    success = vision.grasp_at_pixel(center_u, center_v)
```

---

#### 3. 框选抓取

##### `grasp_at_bbox(x1, y1, x2, y2) -> bool`

抓取矩形框中心点。

**参数：**
- `x1, y1`: 左上角坐标
- `x2, y2`: 右下角坐标

**使用场景：**
- 结合目标检测（YOLO/Faster R-CNN）
- 用户框选目标区域

**示例：**
```python
from ultralytics import YOLO

model = YOLO("yolov8n.pt")
cap = cv2.VideoCapture(0)

ret, frame = cap.read()
results = model(frame)

for box in results[0].boxes:
    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
    if float(box.conf[0]) > 0.5:
        vision.grasp_at_bbox(int(x1), int(y1), int(x2), int(y2))
        break
```

---

## FollowGraspSDK - 视觉跟随

### 模块入口

```python
sdk = HorizonArmSDK(motors=motors, camera_id=0)
follow = sdk.follow  # 获取 FollowGraspSDK 实例
```

### 核心接口

#### 1. 配置跟随参数

##### `configure_follow(target_class=None, confidence_threshold=0.5, control_frequency=10, ...)`

**参数：**
- `target_class`: 目标类别（如 "person", "cup"）
- `confidence_threshold`: 检测置信度阈值
- `control_frequency`: 控制频率（Hz）

**示例：**
```python
follow.configure_follow(
    target_class="cup",
    confidence_threshold=0.6,
    control_frequency=10
)
```

---

#### 2. 单步跟随（推荐）

##### `follow_step(frame) -> bool`

执行一次跟随步骤。

**参数：**
- `frame`: 当前帧图像（numpy 数组）

**使用场景：**
- 自定义采图循环
- ROS 节点订阅图像话题
- Web 后端接收视频流

**示例：**
```python
import cv2

cap = cv2.VideoCapture(0)
follow.configure_follow(target_class="person")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    success = follow.follow_step(frame)
    
    if success:
        print("正在跟随目标")
    
    cv2.imshow("Follow", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
```

---

#### 3. 后台循环跟随

##### `start_follow_grasp(...)` / `stop_follow_grasp()` / `is_following()`

启动后台跟随线程。

**示例：**
```python
# 启动
follow.start_follow_grasp(target_class="cup", camera_id=0)

# 检查状态
while follow.is_following():
    time.sleep(0.1)

# 停止
follow.stop_follow_grasp()
```

---

#### 4. 手动框选跟踪

##### `init_manual_target(frame0, x1, y1, x2, y2) -> bool`

手动框选目标并初始化跟踪器。

**使用场景：**
- 用户手动框选目标
- 跟踪特定物体（无需目标检测模型）

**示例：**
```python
import cv2

cap = cv2.VideoCapture(0)
ret, frame = cap.read()

# 让用户框选目标
bbox = cv2.selectROI("Select Target", frame, False)
x, y, w, h = bbox

# 初始化跟踪器
follow.init_manual_target(frame, x, y, x+w, y+h)

# 开始跟随
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    success = follow.follow_step(frame)
    if not success:
        break
    
    cv2.imshow("Following", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
```

---

## 配置文件

### calibration_parameter.json（必需）

相机标定参数：

```json
{
  "camera_matrix": [[fx, 0, cx], [0, fy, cy], [0, 0, 1]],
  "dist_coeffs": [k1, k2, p1, p2, k3],
  "rotation_matrix": [...],
  "translation_vector": [...]
}
```

### motor_config.json

电机配置（减速比、方向等）。

---

## 安全建议

1. **标定检查**：
   - 首次使用前必须完成手眼标定
   - 更换相机或安装位置后需重新标定

2. **参数设置**：
   - 从较高的 `grasp_height` 开始测试
   - 逐步降低高度找到最佳抓取点

3. **测试流程**：
   - 先在已知位置测试，验证抓取精度
   - 确认无误后再用于实际场景

---

## 相关文档

- [安全须知](safety.md) - 视觉抓取安全注意事项
- [配置说明](configuration.md) - 标定文件配置
- [MotionSDK](motion.md) - 运动控制接口
- [API 详细参考](api_detailed.md) - 完整 API 说明

## 示例脚本

- **`example/test_visual_grasp.py`**  
  **用途：** 视觉抓取综合测试工具。  
  **功能：** 提供交互式菜单，测试像素点抓取、框选抓取和视觉跟随功能。

- **`example/ai_sdk_examples/simple_depth_estimation.py`**  
  **用途：** 极简深度估计演示。  
  **功能：** 展示如何用一行代码调用深度估计功能，支持从文件计算视差图和单点测距。

- **`example/ai_sdk_examples/depth_estimation_examples.py`**  
  **用途：** 交互式深度估计综合示例。  
  **功能：** 提供菜单选择，可运行“文件模式”（读取本地图片）或“内存模式”（直接处理图像数组），展示完整的深度图生成与可视化流程。
