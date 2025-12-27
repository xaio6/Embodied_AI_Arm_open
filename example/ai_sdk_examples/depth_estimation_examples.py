"""
深度估计功能示例
展示如何使用深度估计SDK功能
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
import numpy as np

# -----------------------------------------------------------------------------

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def check_files(left_path, right_path, json_path):
    """检查必要文件是否存在"""
    missing = []
    if not os.path.exists(left_path): missing.append(left_path)
    if not os.path.exists(right_path): missing.append(right_path)
    if not os.path.exists(json_path): missing.append(json_path)
    
    if missing:
        print("❌ 缺少必要文件:")
        for f in missing:
            print(f"  - {f}")
        print("\n请确保 'test_file/' 目录下有 left.jpg, right.jpg")
        print("请确保 'config/' 目录下有 calibration_parameter.json")
        return False
    return True

def demo_from_files(sdk):
    """从文件计算视差图示例"""
    left_path = "test_file/left.jpg"
    right_path = "test_file/right.jpg"
    json_path = "config/calibration_parameter.json"
    
    if not check_files(left_path, right_path, json_path): return

    print("\n📂 方式一：直接从文件计算")
    print("-" * 30)
    print(f"左图: {left_path}")
    print(f"右图: {right_path}")
    
    result = sdk.compute_disparity_from_files(
        left_image_path=left_path,
        right_image_path=right_path,
        json_path=json_path,
        blockSize=7,
        num=8,
        minDisparity=5
    )
    
    if not result['success']:
        print(f"❌ 视差图计算失败: {result['error']}")
        return
    
    process_disparity_result(sdk, result)

def demo_with_memory_images(sdk):
    """内存图像计算示例"""
    left_path = "test_file/left.jpg"
    right_path = "test_file/right.jpg"
    json_path = "config/calibration_parameter.json"
    
    if not check_files(left_path, right_path, json_path): return

    print("\n🧠 方式二：内存图像处理流程")
    print("-" * 30)
    
    # 1. 加载参数
    print("[1/3] 加载相机参数...")
    try:
        sdk.load_camera_parameters(json_path)
        print("  ✅ 成功")
    except Exception as e:
        print(f"  ❌ 失败: {e}")
        return

    # 2. 读取图像
    print("[2/3] 读取图像到内存...")
    left_img = cv2.imread(left_path)
    right_img = cv2.imread(right_path)
    if left_img is None or right_img is None:
        print("  ❌ 读取图片失败")
        return
    print("  ✅ 成功")

    # 3. 计算
    print("[3/3] 计算视差图...")
    disparity = sdk.compute_disparity(
        left_image=left_img,
        right_image=right_img,
        blockSize=7,
        num=8,
        minDisparity=5
    )
    
    result = {
        'success': True,
        'disparity': disparity,
        'left_image': left_img,
        'right_image': right_img
    }
    process_disparity_result(sdk, result)

def process_disparity_result(sdk, result):
    """处理并显示结果"""
    disparity = result['disparity']
    left_img = result['left_image']
    right_img = result['right_image']
    
    print("\n📊 结果分析:")
    
    # 绘制校验线
    print("  - 绘制立体校正校验线...")
    rectified_image = sdk.draw_verification_lines(left_img, right_img)
    
    # 计算中心点距离
    h, w = left_img.shape[:2]
    center_point = (w // 2, h // 2)
    dist = sdk.calculate_distance_by_point(disparity, center_point)
    print(f"  - 中心点 {center_point} 距离: {dist:.3f} 米")
    
    # 计算中心区域距离
    box_size = 60
    bbox = (center_point[0] - box_size//2, center_point[1] - box_size//2, box_size, box_size)
    bbox_dist, bbox_color = sdk.calculate_distance_by_bbox(disparity, bbox)
    print(f"  - 中心区域 {bbox} 平均距离: {bbox_dist:.3f} 米")
    
    print("\n🖼️ 正在打开结果窗口，请查看... (关闭窗口以继续)")
    
    plt.figure(figsize=(15, 10))
    
    plt.subplot(2, 2, 1)
    plt.title("Left Image")
    plt.imshow(cv2.cvtColor(left_img, cv2.COLOR_BGR2RGB))
    
    plt.subplot(2, 2, 2)
    plt.title("Disparity Map")
    plt.imshow(disparity, cmap='jet')
    
    plt.subplot(2, 2, 3)
    plt.title("Rectification Check")
    plt.imshow(cv2.cvtColor(rectified_image, cv2.COLOR_BGR2RGB))
    
    plt.subplot(2, 2, 4)
    plt.title(f"Distance: {bbox_dist:.2f}m")
    plt.imshow(cv2.cvtColor(bbox_color, cv2.COLOR_BGR2RGB))
    
    plt.tight_layout()
    plt.show()

def main():
    sdk = DepthEstimationSDK()
    
    while True:
        clear_screen()
        print("=" * 60)
        print(" 📏 深度估计 SDK 功能演示")
        print("=" * 60)
        print("  1. 从文件路径计算 (一键式)")
        print("  2. 从内存图像计算 (分步式)")
        print("  0. 退出")
        print("=" * 60)
        
        choice = input("\n请输入选择 (0-2): ").strip()
        
        if choice == '0':
            print("👋 再见")
            break
        elif choice == '1':
            demo_from_files(sdk)
        elif choice == '2':
            demo_with_memory_images(sdk)
        else:
            print("❌ 无效选择")
            
        input("\n按 Enter 键继续...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序已终止")
