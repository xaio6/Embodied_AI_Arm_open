import sys
import os
import importlib
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SDK_Verifier")

def check_import(module_name, describe=""):
    """尝试导入模块并报告结果"""
    try:
        importlib.import_module(module_name)
        logger.info(f"✅ [通过] 导入 {module_name} ({describe})")
        return True
    except ImportError as e:
        logger.error(f"❌ [失败] 导入 {module_name}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ [错误] 导入 {module_name} 时发生异常: {e}")
        return False

def check_attribute(module_name, attr_name):
    """检查模块是否具有特定属性"""
    try:
        mod = importlib.import_module(module_name)
        if hasattr(mod, attr_name):
            logger.info(f"✅ [通过] {module_name} 包含属性 '{attr_name}'")
            return True
        else:
            logger.error(f"❌ [失败] {module_name} 缺失属性 '{attr_name}'")
            return False
    except Exception as e:
        logger.error(f"❌ [错误] 检查属性时发生异常: {e}")
        return False

def verify_sdk_structure():
    logger.info("====== 开始 SDK 完整性检查 ======")
    
    # 1. 检查底层核心绑定
    logger.info("--- 检查 Horizon_Core 绑定 ---")
    if not check_import("Horizon_Core", "底层命名空间"):
        return
    if not check_import("Horizon_Core.gateway", "授权网关"):
        return
        
    # 2. 检查 Embodied_SDK 模块
    logger.info("--- 检查 Embodied_SDK 模块 ---")
    modules_to_check = [
        ("Embodied_SDK", "SDK 根包"),
        ("Embodied_SDK.motion", "运动控制模块"),
        ("Embodied_SDK.ai", "AI 模块"),
        ("Embodied_SDK.joycon", "手柄模块"),
        ("Embodied_SDK.visual_grasp", "视觉抓取模块"),
        ("Embodied_SDK.digital_twin", "数字孪生模块"),
        ("Embodied_SDK.io", "IO 模块"),
    ]
    
    all_modules_ok = True
    for mod, desc in modules_to_check:
        if not check_import(mod, desc):
            all_modules_ok = False
            
    # 3. 检查关键工厂函数导出
    logger.info("--- 检查关键 API 导出 ---")
    api_checks = [
        ("Embodied_SDK", "create_motor_controller"),
        ("Embodied_SDK", "setup_logging"),
        ("Embodied_SDK", "AISDK"),
        ("Embodied_SDK", "VisualGraspSDK"),
        ("Embodied_SDK", "JoyconSDK"),
    ]
    
    all_apis_ok = True
    for mod, attr in api_checks:
        if not check_attribute(mod, attr):
            all_apis_ok = False

    # 4. 检查示例代码语法的正确性 (尝试导入但不运行)
    logger.info("--- 检查示例代码语法 (静态扫描) ---")
    example_dir = os.path.join(os.getcwd(), "example")
    if os.path.exists(example_dir):
        sys.path.append(example_dir)
        # 列出几个关键示例进行导入测试
        examples = [
            "sdk_quickstart",
            "test_interactive",
            # "sdk_joycon_demo", # 可能包含立即执行的代码，暂不导入
        ]
        for ex in examples:
            # 注意：如果示例代码在模块层级就有执行逻辑（非 if __name__ == "__main__"），这里导入会触发执行
            # 这里的检查主要是确认 import 路径是否正确
            try:
                # 仅做查找测试
                found = importlib.util.find_spec(ex)
                if found:
                     logger.info(f"✅ [通过] 示例脚本找到: {ex}.py")
                else:
                     logger.warning(f"⚠️ [警告] 未找到示例脚本: {ex}.py")
            except Exception as e:
                logger.error(f"❌ [失败] 示例脚本检查异常 {ex}: {e}")

    logger.info("====== 检查结束 ======")
    if all_modules_ok and all_apis_ok:
        logger.info("🎉 SDK 结构完整，核心链接正常。")
    else:
        logger.error("🚫 检测到 SDK 存在问题，请检查上方报错信息。")

if __name__ == "__main__":
    verify_sdk_structure()

