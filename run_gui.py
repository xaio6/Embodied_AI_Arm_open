# -*- coding: utf-8 -*-
"""
MuJoCo机械臂控制系统 - 上位机界面
整合Control电机控制界面到主项目
"""

import sys
import os
from dotenv import load_dotenv
from Main_UI.utils.bootstrap import (
    apply_global_ui_scale
)

# 兼容源码与冻结运行：确定应用目录 app_dir 与基准目录 base_dir
current_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = getattr(sys, '_MEIPASS', current_dir)


# 将基准目录加入 sys.path（确保可导入 core、Main_UI 等顶层包/命名空间包）
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# 添加Main_UI目录到路径
main_ui_dir = os.path.join(current_dir, "Main_UI")
sys.path.insert(0, main_ui_dir)

# 添加Control_Core目录到路径  
control_core_dir = os.path.join(current_dir, "Control_SDK")
sys.path.insert(0, control_core_dir)

# 读取 .env（支持把 Gitee 参数写在 Horizon_Arm2/.env 内）
env_path = os.path.join(current_dir, ".env")
load_dotenv(env_path)

# 配置目录：优先使用 ProgramData 外部配置（首次运行自动初始化）
def _get_programdata_config_dir():
    program_data = os.environ.get('PROGRAMDATA', r'C:\\ProgramData')
    return os.path.join(program_data, 'HorizonArm', 'config')

def _ensure_external_config():
    try:
        src_config_dir = os.path.join(current_dir, 'config')
        dst_config_dir = _get_programdata_config_dir()
        os.makedirs(dst_config_dir, exist_ok=True)

        # 首次运行：将整个 config 目录按需拷贝到 ProgramData（仅拷贝缺失文件，保留用户修改）
        try:
            import shutil
            if os.path.isdir(src_config_dir):
                for root, dirs, files in os.walk(src_config_dir):
                    rel = os.path.relpath(root, src_config_dir)
                    target_root = os.path.join(dst_config_dir, rel) if rel != '.' else dst_config_dir
                    os.makedirs(target_root, exist_ok=True)
                    for fname in files:
                        src_file = os.path.join(root, fname)
                        dst_file = os.path.join(target_root, fname)
                        if not os.path.exists(dst_file):
                            try:
                                shutil.copy2(src_file, dst_file)
                            except Exception:
                                pass
        except Exception:
            # 忽略拷贝失败，继续后续流程
            pass

        # 将外部配置目录通过环境变量暴露，便于各模块查找
        os.environ['HORIZONARM_CONFIG_DIR'] = dst_config_dir
        # 兼容可能直接使用文件路径的模块
        os.environ['AISDK_CONFIG_PATH'] = os.path.join(dst_config_dir, 'aisdk_config.yaml')
    except Exception:
        # 不因配置目录初始化失败而阻断启动
        pass

_ensure_external_config()

# 应用全局 UI 缩放
apply_global_ui_scale()

# 不再向应用目录复制资源；资源以 ProgramData 为准

try:
    print("🚀 启动机械臂控制系统...")
    
    # 检查路径是否存在
    if not os.path.exists(main_ui_dir):
        print(f"❌ Main_UI目录不存在: {main_ui_dir}")
        sys.exit(1)
        
    if not os.path.exists(os.path.join(main_ui_dir, "main.py")):
        print(f"❌ main.py文件不存在: {os.path.join(main_ui_dir, 'main.py')}")
        sys.exit(1)
    
    # 导入并运行主程序
    from Main_UI.main import main
    main()
    
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("如果问题仍然存在，请检查Main_UI目录结构是否完整")
    
except Exception as e:
    print(f"❌ 运行错误: {e}")
    import traceback
    traceback.print_exc() 
    
print("👋 程序已退出") 