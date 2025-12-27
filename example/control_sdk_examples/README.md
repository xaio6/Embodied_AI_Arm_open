# Control SDK 示例

本目录包含HorizonArm Control SDK的所有功能示例，按照从简单到复杂的顺序组织。

## 📚 推荐学习顺序

### 第一步：快速入门
开始之前，请先运行项目根目录的 `quickstart_guide.py`，完成5分钟快速入门。

### 第二步：核心功能学习

1. **motor_usage_example.py** - 单电机完全指南
   - 基础控制（使能/失能/停止）
   - 运动模式（速度/位置/力矩）
   - 参数读取和配置
   - 👉 推荐用时：30分钟

2. **motion_usage_example.py** (待创建)
   - 多关节运动控制
   - 关节空间 vs 笛卡尔空间
   - 预设动作
   - 👉 推荐用时：30分钟

3. **visual_grasp_example.py** - 视觉抓取功能
   - 系统自检和配置
   - 像素点抓取
   - 框选抓取
   - 视觉跟随
   - 👉 推荐用时：45分钟

### 第三步：高级功能

4. **multi_motor_sync_example.py** - 多电机同步控制 (简化版)
   - 同步位置控制
   - 同步速度控制
   - 同步回零
   - 👉 推荐用时：20分钟
   - 💡 完整功能见：`test_multi_motor_sync.py`

5. **joycon_control_example.py** - 手柄遥操作
   - Level 1: 连接测试
   - Level 2: 数据监控
   - Level 3: 机械臂控制
   - Level 4: 参数配置
   - 👉 推荐用时：40分钟

6. **io_control_example.py** - IO控制
   - 基础IO读写
   - 应用场景演示
   - 👉 推荐用时：20分钟

7. **digital_twin_example.py** - MuJoCo仿真
   - 无硬件开发
   - 算法验证
   - 轨迹预览
   - 👉 推荐用时：15分钟

## 🔧 完整功能参考

如需更多专业功能，请参考项目根目录的：
- `test_interactive.py` - 完整的单电机测试工具（40+功能）
- `test_multi_motor_sync.py` - 完整的多机同步工具（26+功能）
- `sdk_quickstart.py` - 完整的机械臂控制示例

## 🛠️ 开发者工具

高级调试工具位于 `developer_tools/` 目录。

## 📖 文档

完整API文档请参考：
- `docs/sdk_reference/control_sdk.md`
- `docs/troubleshooting.md`

