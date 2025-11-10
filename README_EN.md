# Horizon Embodied Intelligence Robotic Arm Control System

<div align="center">

![Logo](logo.png)

**An integrated 6-axis robotic arm control platform with AI intelligent decision-making, visual recognition, and voice interaction**

**Making robotic arms understand the world, controlling the future with natural language**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Bilibili](https://img.shields.io/badge/Bilibili-Tutorial-ff69b4.svg)](https://www.bilibili.com/video/BV13LkDBeEpy)
[![Stars](https://img.shields.io/github/stars/your-repo/Horizon_Arm?style=social)](https://github.com/your-repo/Horizon_Arm)

[English](README_EN.md) | [简体中文](README.md)

</div>

---

## 📺 Video Tutorial

For complete system introduction, please watch:
- 🎬 [Horizon Embodied Intelligence Robotic Arm System](https://www.bilibili.com/video/BV13LkDBeEpy)

If this project helps you, please give it a ⭐Star to support!

## 🎯 Project Overview

The Horizon Embodied Intelligence System is a fully-featured 6-axis robotic arm control platform that integrates modern AI technology with precision mechanical control. The system enables intelligent control and operation of robotic arms through natural language commands, visual recognition, voice interaction, and other methods.

If this project helps you, please give me a ⭐Star to support!

### ✨ Core Features

- 🤖 **Embodied Intelligence**: Natural language understanding and decision-making based on LLM and VLM
- 👁️ **Vision System**: Binocular stereo vision, object detection, depth estimation
- 🎮 **Digital Twin**: MuJoCo high-precision physical simulation
- 🔧 **Precision Control**: High-precision motor control based on CAN bus
- 🎤 **Voice Interaction**: Automatic Speech Recognition (ASR) and Text-to-Speech (TTS)
- 📱 **Modern Interface**: Responsive PyQt5 user interface

## 🏗️ Project Architecture

```
Horizon_Arm_New/
├── 🧠 AI_SDK/                    # Unified AI service framework
│   ├── core/                     # Core processors
│   │   ├── llm/                  # Large Language Model processing
│   │   ├── asr/                  # Automatic Speech Recognition
│   │   ├── tts/                  # Text-to-Speech processing
│   │   ├── multimodal/           # Multimodal processing
│   │   ├── smart_chat/           # Intelligent dialogue
│   │   └── session/              # Session management
│   ├── providers/                # Multi-vendor adaptation layer
│   │   ├── alibaba/              # Alibaba Cloud Qwen
│   │   └── deepseek/             # DeepSeek
│   └── services/                 # Service encapsulation layer
│
├── ⚙️ Control_SDK/               # Motor control core SDK
│   └── Control_Core/             # Control core module
│       ├── modules/              # Function modules
│       │   ├── control_actions.py    # Control actions
│       │   ├── read_parameters.py    # Parameter reading
│       │   ├── modify_parameters.py  # Parameter modification
│       │   ├── homing_commands.py    # Homing control
│       │   └── trigger_actions.py    # Trigger actions
│       ├── motor_controller_modular.py  # Modular controller
│       ├── can_interface.py      # CAN communication interface
│       └── commands.py           # Command builder
│
├── 🎯 core/                      # Core algorithm modules
│   ├── arm_core/                 # Robotic arm core algorithms
│   │   ├── kinematics.py         # Kinematics calculation
│   │   ├── vision_detection.py   # Visual detection
│   │   ├── Depth_Estimation.py   # Depth estimation
│   │   ├── Hand_Eye_Calibration.py  # Hand-eye calibration
│   │   ├── trajectory_executor.py    # Trajectory execution
│   │   └── rrt_planner.py        # Path planning
│   └── embodied_core/            # Embodied intelligence core
│       ├── hierarchical_decision_system.py  # Hierarchical decision system
│       └── mujoco_kinematics_control_core.py  # MuJoCo control
│
├── 🖥️ Main_UI/                   # Graphical User Interface
│   ├── ui/                       # Interface components
│   ├── widgets/                  # Function widgets
│   │   ├── digital_twin_widget.py       # Digital twin
│   │   ├── teach_pendant_widget.py      # Teach pendant
│   │   ├── vision_grasp_widget.py       # Vision grasping
│   │   ├── embodied_intelligence_widget.py  # Embodied intelligence
│   │   └── connection_widget.py         # Connection management
│   └── utils/                    # Utility modules
│
└── 📁 config/                    # Configuration files
    ├── aisdk_config.yaml         # AI SDK configuration
    ├── motor_config.json         # Motor configuration
    ├── embodied_config/          # Embodied intelligence config
    └── urdf/                     # Robot model files
```

## 🚀 Main Function Modules

### 1. 🧠 AI_SDK - Unified AI Service Framework

AI_SDK provides unified calling interfaces for multi-vendor AI services, supporting:

#### 🗣️ Large Language Models (LLM)
```python
from AI_SDK import AISDK

sdk = AISDK()

# Basic conversation
response = sdk.chat("alibaba", "qwen-turbo", "Hello")

# Stream output
for chunk in sdk.chat("alibaba", "qwen-turbo", "Tell me a story", stream=True):
    print(chunk, end="")

# Contextual dialogue
sdk.chat("alibaba", "qwen-turbo", "My name is John", use_context=True)
name = sdk.chat("alibaba", "qwen-turbo", "What's my name?", use_context=True)
```

#### 🎤 Automatic Speech Recognition (ASR)
```python
# File recognition
result = sdk.asr("alibaba", "file", audio_file="audio.wav")

# Microphone recognition
result = sdk.asr("alibaba", "microphone", duration=5)

# Real-time stream recognition
for result in sdk.asr("alibaba", "stream", audio_stream=stream):
    print(result)

# Keyword wake-up
for result in sdk.asr("alibaba", "keyword", keywords=["hello", "assistant"]):
    if result.get("success"):
        print("Wake word detected:", result.get("keyword_detected"))
```

#### 🔊 Text-to-Speech (TTS)
```python
# Text to audio file
sdk.tts("alibaba", "file", "Hello World", output_file="output.mp3")

# Direct playback
sdk.tts("alibaba", "speaker", "Welcome to AI system")

# Stream synthesis
def text_generator():
    yield "Today's weather"
    yield "is very nice"

for chunk in sdk.tts("alibaba", "stream", text_generator()):
    print("Synthesis completed")
```

#### 👁️ Multimodal Understanding
```python
# Image understanding
result = sdk.multimodal("alibaba", "image", "Describe this image", image_path="image.jpg")

# Video analysis
result = sdk.multimodal("alibaba", "video", "Analyze video content", video_path="video.mp4")

# Multi-image analysis
result = sdk.multimodal("alibaba", "multiple_images", "Compare these images", 
                       image_paths=["img1.jpg", "img2.jpg"])
```

#### 🤖 Smart Chat (LLM + TTS)
```python
# Q&A with voice playback
result = sdk.smart_chat(
    prompt="Please introduce yourself",
    llm_provider="alibaba", 
    llm_model="qwen-turbo",
    tts_provider="alibaba",
    tts_mode="speaker"
)
```

**Supported AI Providers:**
- 🔵 **Alibaba Cloud**: Qwen series models
- 🟢 **DeepSeek**: DeepSeek series models
- 🔴 **OpenAI**: GPT series models (extensible)

### 2. ⚙️ Control_SDK - Precision Motor Control

Control_SDK provides complete control functions for ZDT closed-loop drive boards:

#### 🔧 Basic Control
```python
from Control_SDK.Control_Core import ZDTMotorController

# Create motor controller
motor = ZDTMotorController(motor_id=1, port='COM18')

with motor:
    # Enable motor
    motor.control_actions.enable()
    
    # Position control
    motor.control_actions.move_to_position(90.0, speed=200)
    
    # Speed control
    motor.control_actions.set_speed(100)
    
    # Torque control
    motor.control_actions.set_torque(500)  # 500mA
```

#### 🔄 Multi-Motor Synchronous Control
```python
# Create multiple motor controllers
broadcast = ZDTMotorController(motor_id=0, port='COM18')  # Broadcast controller
motor1 = ZDTMotorController(motor_id=1, port='COM18')
motor2 = ZDTMotorController(motor_id=2, port='COM18')

# Share CAN interface
broadcast.connect()
motor1.can_interface = broadcast.can_interface
motor2.can_interface = broadcast.can_interface

# Enable all motors
motor1.control_actions.enable()
motor2.control_actions.enable()

# Configure synchronous motion (with sync flag)
motor1.control_actions.move_to_position(-3600, speed=1000, multi_sync=True)
motor2.control_actions.move_to_position_trapezoid(7200, max_speed=1000, 
                                                 acceleration=2000, multi_sync=True)

# Trigger synchronous motion
broadcast.control_actions.sync_motion()
```

#### 📊 Status Monitoring
```python
# Get motor status
status = motor.read_parameters.get_motor_status()
position = motor.read_parameters.get_position()
speed = motor.read_parameters.get_speed()
temperature = motor.read_parameters.get_temperature()
current = motor.read_parameters.get_current()

print(f"Position: {position:.2f}°, Speed: {speed:.2f}RPM, Temperature: {temperature:.1f}°C")
```

#### 🏠 Homing Function
```python
# Start homing
motor.control_actions.start_homing()

# Wait for homing completion
if motor.homing_commands.wait_for_homing_complete(timeout=30):
    print("Homing successful")
else:
    print("Homing timeout")

# Set current position as zero
motor.homing_commands.set_zero_position(save_to_chip=True)
```

**Control Features:**
- 🎯 **Precise Control**: Position accuracy ±0.1°, speed accuracy ±1RPM
- 🔄 **Multiple Modes**: Position mode, speed mode, torque mode
- 🚀 **High-Speed Communication**: CAN bus 500K baud rate
- 🛡️ **Safety Protection**: Stall protection, over-temperature protection, limit protection

### 3. 🎯 Core Algorithm Modules

#### 🤖 Kinematics and Trajectory Planning
```python
from core.arm_core.kinematics import RobotKinematics

# Initialize kinematics
kinematics = RobotKinematics()

# Forward kinematics: joint angles → end effector pose
joint_angles = [0, 30, -45, 0, 15, 0]  # degrees
end_pose = kinematics.forward_kinematics(joint_angles)

# Inverse kinematics: end effector pose → joint angles
target_pose = [300, 200, 400, 0, 0, 0]  # [x,y,z,rx,ry,rz]
joint_solution = kinematics.inverse_kinematics(target_pose)

# Trajectory planning
from core.arm_core.trajectory_executor import TrajectoryExecutor
executor = TrajectoryExecutor()

# Joint space trajectory
trajectory = executor.plan_joint_trajectory(start_joints, end_joints, duration=3.0)

# Cartesian space trajectory
trajectory = executor.plan_cartesian_trajectory(start_pose, end_pose, duration=5.0)
```

#### 👁️ Visual Detection and Depth Estimation
```python
from core.arm_core.vision_detection import VisionDetector
from core.arm_core.Depth_Estimation import StereoDepthEstimator

# Initialize vision detector
detector = VisionDetector(camera_matrix, dist_coeffs, model='fisheye')

# Color detection
hsv_lower = (35, 50, 50)   # HSV lower bound
hsv_upper = (85, 255, 255) # HSV upper bound
result = detector.detect_color(image, hsv_lower, hsv_upper, min_area=500)

# Binocular depth estimation
depth_estimator = StereoDepthEstimator()
depth_map = depth_estimator.compute_depth(left_image, right_image)

# Get depth at specified point
x, y = 320, 240  # Pixel coordinates
depth = depth_estimator.get_depth_at_point(depth_map, x, y)
```

#### 🎯 Hand-Eye Calibration
```python
from core.arm_core.Hand_Eye_Calibration import HandEyeCalibrator

# Initialize calibrator
calibrator = HandEyeCalibrator()

# Add calibration data points
for i in range(num_poses):
    # Move robot to calibration pose
    robot_pose = get_robot_pose(i)
    
    # Capture calibration board image
    image = capture_image()
    
    # Detect calibration board
    success, camera_pose = calibrator.detect_calibration_board(image)
    
    if success:
        calibrator.add_calibration_data(robot_pose, camera_pose)

# Perform calibration calculation
success, transform_matrix = calibrator.calibrate()
if success:
    print("Hand-eye calibration successful")
    print(f"Transform matrix:\n{transform_matrix}")
```

### 4. 🧠 Embodied Intelligence System

The embodied intelligence system implements a three-layer decision architecture supporting natural language control:

#### 🎯 Three-Layer Architecture
```
┌─────────────────────────────────────────────────────────────┐
│              High-Level Planner (Decision Maker)             │
│  - Interact with LLM for function selection                 │
│  - Convert natural language to function call JSON           │
│  - Intelligently select appropriate functions and params    │
└─────────────────────┬───────────────────────────────────────┘
                      │ Function Call JSON
                      ▼
┌─────────────────────────────────────────────────────────────┐
│           Middle-Level Parser (Task Parser)                  │
│  - Parse function call JSON from high-level                 │
│  - Directly call specified functions with params            │
│  - Handle function execution results and errors             │
└─────────────────────┬───────────────────────────────────────┘
                      │ Function Execution
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Low-Level Executor (Actuator)                   │
│  - Specific robotic arm control functions                   │
│  - MuJoCo simulation control functions                      │
│  - Vision processing and grasping functions                 │
└─────────────────────────────────────────────────────────────┘
```

#### 🗣️ Natural Language Control
```python
from core.embodied_core.hierarchical_decision_system import HierarchicalDecisionSystem

# Initialize decision system
decision_system = HierarchicalDecisionSystem(
    provider="alibaba",
    model="qwen-turbo", 
    control_mode="both"  # Control both real robot and simulation
)

# Natural language instruction control
instructions = [
    "Return robotic arm to initial position",
    "Rotate joint 1 by 30 degrees",
    "Move to coordinates (300, 200, 400)",
    "Grasp the red object",
    "Execute a waving motion"
]

for instruction in instructions:
    result = decision_system.execute_instruction(instruction)
    print(f"Instruction: {instruction}")
    print(f"Execution result: {result['execution_result']['success']}")
```

#### 🎮 MuJoCo Simulation Integration
```python
# MuJoCo simulation control
from core.embodied_core import embodied_mujoco_func

# Start MuJoCo simulation
embodied_mujoco_func.start_mujoco_simulation()

# Control simulated robotic arm
embodied_mujoco_func.move_to_joint_angles([0, 30, -45, 0, 15, 0])
embodied_mujoco_func.move_to_position([300, 200, 400, 0, 0, 0])

# Preset actions
embodied_mujoco_func.wave_hand()
embodied_mujoco_func.home_position()
```

### 5. 🖥️ Graphical User Interface

Modern interface based on PyQt5, providing intuitive operation experience:

#### 🦾 Robotic Arm Control Interface
- **Digital Twin**: Real-time 3D simulation display
- **Joint Control**: Independent control of each joint
- **Coordinate Control**: Cartesian coordinate system control
- **Status Monitoring**: Real-time motor status display

#### 🎮 Teach Pendant Interface
- **Joint Mode**: Direct control of joint angles
- **Base Mode**: Based on base coordinate system
- **Tool Mode**: Based on end-effector tool coordinate system
- **Program Recording**: Record and playback motion sequences

#### 👁️ Vision Grasping Interface
- **Camera Display**: Real-time camera image display
- **Depth Map**: Binocular depth information visualization
- **Object Detection**: AI object recognition and annotation
- **Coordinate Conversion**: Pixel to robot coordinates

#### 🧠 Embodied Intelligence Interface
- **Voice Interaction**: Voice command input and feedback
- **Text Dialogue**: Natural language text interaction
- **Task Queue**: Batch task management and execution
- **Execution Log**: Detailed execution process records

## 📋 System Requirements

### Hardware Requirements
- **Robotic Arm**: 6-axis robotic arm + ZDT closed-loop drive board
- **Communication Device**: CANable, CANtact or other SLCAN compatible devices
- **Camera**: USB camera or industrial camera (optional)
- **Computer**: Windows 10/11, 8GB+ RAM, OpenGL support

### Software Dependencies
- **Python**: 3.8+
- **GUI Framework**: PyQt5
- **Simulation**: MuJoCo >= 2.3.0
- **Computer Vision**: OpenCV >= 4.10.0
- **Numerical Computing**: NumPy, SciPy, Matplotlib
- **AI Services**: Network connection (when using LLM features)

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Clone the project
git clone https://github.com/your-repo/Horizon_Arm_New.git
cd Horizon_Arm_New

# Install dependencies
pip install -r requirements.txt

# Windows system pyaudio installation
pip install pipwin
pipwin install pyaudio
```

### 2. Configuration
```bash
# Copy configuration template
cp config/aisdk_config.yaml.template config/aisdk_config.yaml

# Edit configuration file, set API keys
# Recommended: use environment variables for keys
export ALI_API_KEY="your_alibaba_api_key"
export DEEPSEEK_API_KEY="your_deepseek_api_key"
```

### 3. Hardware Connection
1. Connect ZDT drive board to CAN bus
2. Connect CANable device to computer USB port
3. Set drive board parameters:
   - P_Serial: CAN1_MAP
   - CAN rate: 500K
   - Motor ID: 1-6 (unique for each motor)

### 4. Start System
```bash
# Start GUI
python run_gui.py

# Or run main program directly
python Main_UI/main.py
```

### 5. Basic Usage

#### Connect Motors
1. Open "Connection Management" interface
2. Select correct serial port (e.g., COM18)
3. Click "Connect" button
4. Wait for motor connection success

#### Control Robotic Arm
1. Switch to "Robotic Arm" tab
2. Use joint control sliders to adjust each joint angle
3. Or use coordinate input boxes to set target position
4. Observe real-time feedback in MuJoCo simulation

#### Natural Language Control
1. Switch to "Embodied Intelligence" tab
2. Configure LLM provider and model
3. Enter natural language instructions in command input box
4. Click "Execute Instruction" or use voice input

## 🔧 Configuration Instructions

### AI_SDK Configuration (config/aisdk_config.yaml)
```yaml
providers:
  alibaba:
    api_key: ${ALI_API_KEY}  # Use environment variable
    default_params:
      max_tokens: 2000
      temperature: 0.7
      top_p: 0.8
    enabled: true
    
  deepseek:
    api_key: ${DEEPSEEK_API_KEY}
    default_params:
      max_tokens: 2000
      temperature: 0.7
      top_p: 1.0
    enabled: true

logging:
  level: INFO
  file: AI_SDK.log
  max_size: 10485760  # 10MB
  backup_count: 5

session:
  default_max_history: 20
  max_sessions: 100
```

### Motor Configuration (config/motor_config.json)
```json
{
  "motors": {
    "1": {
      "name": "Base Joint",
      "reducer_ratio": 50.0,
      "direction": 1,
      "min_angle": -180,
      "max_angle": 180
    },
    "2": {
      "name": "Shoulder Joint", 
      "reducer_ratio": 50.0,
      "direction": -1,
      "min_angle": -90,
      "max_angle": 90
    }
    // ... other motor configurations
  },
  "communication": {
    "port": "COM18",
    "baudrate": 500000,
    "timeout": 1.0
  }
}
```

## 🛠️ Development Guide

### Extending AI Functionality
```python
# Add new AI provider
# 1. Create new provider module in AI_SDK/providers/
# 2. Implement LLMProvider base class
# 3. Add provider config in configuration file

class NewAIProvider(LLMProvider):
    def __init__(self, config):
        super().__init__(config)
        
    def chat(self, model, messages, **kwargs):
        # Implement chat interface
        pass
        
    def stream_chat(self, model, messages, **kwargs):
        # Implement stream chat interface
        pass
```

### Adding New Control Functions
```python
# Extend motor control functionality
# Add new module in Control_SDK/Control_Core/modules/

class CustomControlModule:
    def __init__(self, controller):
        self.controller = controller
        
    def custom_motion(self, params):
        # Implement custom motion control
        command = self.controller.command_builder.build_custom_command(params)
        return self.controller._send_command(command)
```

### Adding Vision Algorithms
```python
# Extend visual detection functionality
# Add new vision algorithm in core/arm_core/

class CustomVisionAlgorithm:
    def __init__(self):
        pass
        
    def detect_custom_object(self, image):
        # Implement custom object detection
        return detection_result
```

## 🔍 Troubleshooting

### Common Issues

#### 1. Connection Failure
**Problem**: Unable to connect to motor controller
**Solutions**:
- Check if serial port number is correct (Device Manager)
- Ensure no other program is using the serial port
- Check CAN bus connection and power supply
- Verify drive board parameter settings

#### 2. AI Features Not Working
**Problem**: LLM call failure or timeout
**Solutions**:
- Check network connection
- Verify API key is correct
- Confirm API quota is sufficient
- Check firewall settings

#### 3. Vision Feature Issues
**Problem**: Camera cannot open or image is abnormal
**Solutions**:
- Check camera connection and drivers
- Verify camera permission settings
- Check OpenCV version compatibility
- Confirm camera calibration parameters

#### 4. MuJoCo Simulation Problems
**Problem**: Simulation cannot start or display is abnormal
**Solutions**:
- Check MuJoCo license
- Verify OpenGL support
- Check URDF model files
- Ensure graphics drivers are updated

### Debug Mode
```python
# Enable verbose logging
from Control_SDK.Control_Core import setup_logging
import logging

setup_logging(logging.DEBUG)

# Enable AI_SDK debug
os.environ['AISDK_DEBUG'] = '1'
```

## 📚 API Documentation

For detailed API documentation, please refer to:
- [AI_SDK API Documentation](AI_SDK/README.md)
- [Control_SDK API Documentation](Control_SDK/README.md)
- [Embodied Intelligence System Documentation](core/embodied_core/README.md)

## 📜 Open Source License and Commercial Use Statement

### Open Source License
This project is licensed under the **MIT License**, you are free to:
- ✅ Use this project for learning and research
- ✅ Modify and distribute the source code
- ✅ Use for personal or commercial projects
- ✅ Private deployment

### ⚠️ Commercial Use Statement (Important)

**If you use this project for commercial purposes, please comply with the following requirements:**

1. **Attribution**: Clearly state in your product, documentation, or promotional materials:
   ```
   This project is based on Horizon Embodied Intelligence Robotic Arm Control System
   Original project: https://github.com/xaio6/Embodied_AI_Arm_open
   Original author's Bilibili: https://www.bilibili.com/video/BV13LkDBeEpy
   ```

2. **Retain Copyright Information**: Do not remove copyright notices and license files from source code

3. **No False Attribution**: Do not claim all or part of this project's code as your original work

4. **Feedback Encouraged**: If you develop interesting applications based on this project, welcome to contact the original author

**Commercial use that violates the above statement reserves the right to pursue legal liability.**

### Disclaimer
- This software is provided "as is" without any express or implied warranties
- The author is not responsible for any direct or indirect losses caused by using this software
- Please ensure operation of the robotic arm in a safe environment and pay attention to personal and equipment safety

## 🤝 Contribution Guide

All forms of contribution are welcome! Whether it's reporting bugs, proposing new features, or submitting code improvements.

### How to Contribute

1. **Fork** this repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a **Pull Request**

### Contribution Content
- 🐛 Bug fixes and issue reports
- ✨ New feature development
- 📝 Documentation improvements and translations
- 🎨 UI/UX optimization
- ⚡ Performance optimization
- 🧪 Test case additions

### Code Standards
- Follow PEP 8 Python code style
- Add necessary comments and docstrings
- Run tests before committing to ensure code works
- Clearly describe changes in Pull Request

<div align="center">

### **Horizon Embodied Intelligence Robotic Arm Control System**

*Making robotic arms smarter, making control simpler*

**If this project helps you, please give it a ⭐Star to support!**

Made with ❤️ by Horizon AI Lab

</div>

