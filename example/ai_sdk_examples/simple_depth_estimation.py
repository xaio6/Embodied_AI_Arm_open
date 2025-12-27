"""
简单深度估计示例
展示如何用一行代码调用深度估计功能
"""

import sys
import os

# 将项目根目录添加到 python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Embodied_SDK.ai import DepthEstimationSDK
import cv2
import matplotlib.pyplot as plt

def main():
    print("=" * 50)
    print(" 📏 极简深度估计演示")
    print("=" * 50)
    print("本示例展示最精简的 SDK 调用方式：")
    print("  1. compute_disparity_from_files() 一行出图")
    print("  2. calculate_distance_by_point() 一行测距")
    print("-" * 50)
    
    input("按 Enter 开始演示...")

    # 初始化
    try:
        depth_sdk = DepthEstimationSDK()
    except Exception as e:
        print(f"❌ SDK 初始化失败: {e}")
        return

    left_path = "test_file/left.jpg"
    right_path = "test_file/right.jpg"
    json_path = "config/calibration_parameter.json"

    if not all(os.path.exists(p) for p in [left_path, right_path, json_path]):
        print("❌ 缺少测试文件，请检查 test_file/ 和 config/ 目录")
        return

    print("\n[1/3] 计算视差图...")
    result = depth_sdk.compute_disparity_from_files(
        left_image_path=left_path,
        right_image_path=right_path,
        json_path=json_path,
        blockSize=9,
        num=9,
        minDisparity=20
    )

    if not result['success']:
        print(f"❌ 计算失败: {result['error']}")
        return
    print("✅ 计算成功")

    disparity = result['disparity']
    
    # 测距演示
    print("\n[2/3] 测量中心点距离...")
    h, w = result['left_image'].shape[:2]
    center = (w//2, h//2)
    dist = depth_sdk.calculate_distance_by_point(disparity, center)
    print(f"  📍 坐标 {center} -> 距离: {dist:.3f} 米")

    print("\n[3/3] 显示结果...")
    plt.figure("Simple Depth Demo")
    plt.imshow(disparity, cmap='jet')
    plt.title(f"Center Distance: {dist:.3f}m")
    plt.colorbar()
    plt.show()
    print("演示结束")

if __name__ == "__main__":
    main()
