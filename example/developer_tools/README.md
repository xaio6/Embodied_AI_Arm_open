# 开发者工具 (Developer Tools)

本目录包含用于调试和开发的专业工具，不作为示例教程使用。

## 工具列表

### 1. protocol_analyzer.py
协议解析测试工具，用于：
- 验证ZDT协议的解析正确性
- 测试新增的通信命令
- 调试协议兼容性问题

### 2. joycon_sensor_display.py (移动自test_joycon_display.py)
Joy-Con传感器深度监控工具，用于：
- 查看原始IMU数据
- 校准摇杆死区
- 调试按键映射

### 3. motor_diagnostics.py
电机诊断工具，用于：
- 批量读取电机参数
- 生成诊断报告
- 故障排查辅助

## 使用说明

这些工具是为有SDK开发经验的工程师准备的，普通开发者请使用 `control_sdk_examples/` 下的示例。

## 与示例的区别

| 类型 | 目的 | 受众 |
|------|------|------|
| **示例 (examples/)** | 教学、学习、快速上手 | 所有开发者 |
| **工具 (developer_tools/)** | 调试、诊断、协议验证 | 高级开发者/集成商 |

