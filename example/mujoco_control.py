import mujoco
import mujoco.viewer
import os
import time
import numpy as np

# 你的模型文件路径
xml_filename = 'config/urdf/mjmodel.xml'

# 检查文件是否存在
if not os.path.exists(xml_filename):
    print(f"错误: 找不到模型文件 '{xml_filename}'。")
    exit()

# 加载模型和数据
try:
    model = mujoco.MjModel.from_xml_path(xml_filename)
    data = mujoco.MjData(model)
except Exception as e:
    print(f"加载 XML 文件时出错: {e}")
    exit()

# 使用 launch_passive 启动被动查看器
with mujoco.viewer.launch_passive(model, data) as viewer:
    
    # 初始化滑块位置，使其与关节初始角度匹配
    data.ctrl[:] = np.rad2deg(data.qpos[:])
    
    while viewer.is_running():
        step_start = time.time()

        # 读取滑块的角度值 (data.ctrl)，转换为弧度，然后直接赋给关节位置 (data.qpos)
        qpos_radians = np.deg2rad(data.ctrl)
        data.qpos[:] = qpos_radians
        
        # mj_step 只用于更新正向运动学，因为kp=0，所以不会产生干扰力
        mujoco.mj_step(model, data)

        # 同步渲染
        viewer.sync()

        # (可选) 控制仿真速度
        time_until_next_step = model.opt.timestep - (time.time() - step_start)
        if time_until_next_step > 0:
            time.sleep(time_until_next_step)