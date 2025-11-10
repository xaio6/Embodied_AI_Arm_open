#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双目鱼眼相机深度估计算法
支持鱼眼和针孔模型的立体视觉深度计算
针对105°广角鱼眼相机优化
"""

import cv2
import numpy as np
import json
import os
from typing import Tuple, Optional, Dict, Any

class StereoDepthEstimator:
    """双目深度估计器"""
    
    def __init__(self, config_path: str = "config/calibration_parameter.json"):
        """
        初始化深度估计器
        
        Args:
            config_path: 标定参数配置文件路径
        """
        self.config_path = config_path
        self.camera_model = 'pinhole'
        
        # 相机参数
        self.K1 = None  # 左相机内参
        self.D1 = None  # 左相机畸变
        self.K2 = None  # 右相机内参  
        self.D2 = None  # 右相机畸变
        self.R = None   # 旋转矩阵
        self.T = None   # 平移向量
        
        # 立体校正参数
        self.R1 = None  # 左相机校正旋转矩阵
        self.R2 = None  # 右相机校正旋转矩阵
        self.P1 = None  # 左相机校正投影矩阵
        self.P2 = None  # 右相机校正投影矩阵
        self.Q = None   # 视差到深度映射矩阵
        
        # 校正映射
        self.map1_left = None
        self.map2_left = None
        self.map1_right = None
        self.map2_right = None
        
        # 视差计算器
        self.stereo_matcher = None
        
        # 图像尺寸
        self.image_size = None
        
        # 加载标定参数
        self.load_calibration_params()
        
    def load_calibration_params(self) -> bool:
        """加载双目标定参数"""
        try:
            if not os.path.exists(self.config_path):
                print(f"❌ 配置文件不存在: {self.config_path}")
                return False
                
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            two_config = config.get('two', {})
            if not two_config:
                print("❌ 未找到双目相机标定参数")
                return False
            
            # 加载相机内参
            self.K1 = np.array(two_config.get('left_camera_matrix', []), dtype=np.float64)
            self.K2 = np.array(two_config.get('right_camera_matrix', []), dtype=np.float64)
            
            # 加载畸变系数（支持两种格式）
            left_distortion = two_config.get('left_distortion', [])
            right_distortion = two_config.get('right_distortion', [])
            
            self.D1 = self._parse_distortion_coeffs(left_distortion)
            self.D2 = self._parse_distortion_coeffs(right_distortion)
            
            # 加载外参
            self.R = np.array(two_config.get('R', []), dtype=np.float64)
            self.T = np.array(two_config.get('T', []), dtype=np.float64).reshape(3, 1)
            
            # 获取相机模型
            self.camera_model = two_config.get('model', 'pinhole')
            
            # 计算基线距离
            baseline = abs(self.T[0, 0]) / 1000.0  # 转换为米（配置中是mm）
            return True
            
        except Exception as e:
            print(f"❌ 加载双目标定参数失败: {e}")
            return False
    
    def _parse_distortion_coeffs(self, distortion_data) -> np.ndarray:
        """解析畸变系数（支持两种格式）"""
        if not distortion_data:
            return np.zeros(4 if self.camera_model == 'fisheye' else 5, dtype=np.float64)
        
        if len(distortion_data) > 0:
            if isinstance(distortion_data[0], list):
                if len(distortion_data[0]) > 1:
                    # 旧格式：[[-0.04169075, -0.10853007, ...]]
                    return np.array(distortion_data[0], dtype=np.float64)
                else:
                    # 新格式：[[0.281...], [0.074...], ...]
                    return np.array([row[0] for row in distortion_data if len(row) > 0], dtype=np.float64)
            else:
                return np.array(distortion_data, dtype=np.float64)
        
        return np.zeros(4 if self.camera_model == 'fisheye' else 5, dtype=np.float64)
    
    def setup_stereo_rectification(self, image_size: Tuple[int, int]) -> bool:
        """设置立体校正参数"""
        try:
            if any(param is None for param in [self.K1, self.K2, self.D1, self.D2, self.R, self.T]):
                print("❌ 标定参数不完整，无法进行立体校正")
                return False
            
            self.image_size = image_size
            w, h = image_size
            
            # 将T转换为正确的单位（米）
            T_meters = self.T.copy()
            if abs(T_meters[0, 0]) > 10:  # 如果T的值很大，说明单位是mm
                T_meters = T_meters / 1000.0
            
            if self.camera_model == 'fisheye':
                # 鱼眼立体校正 - 修复参数传递
                try:
                    # 方法1：使用简化的鱼眼校正
                    balance = 0.0
                    fov_scale = 1.0
                    
                    # 计算新的相机矩阵
                    new_K1 = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                        self.K1, self.D1.reshape(4, 1), (w, h), np.eye(3), balance=balance
                    )
                    new_K2 = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                        self.K2, self.D2.reshape(4, 1), (w, h), np.eye(3), balance=balance
                    )
                    
                    # 使用标准的立体校正（不使用鱼眼专用函数）
                    self.R1, self.R2, self.P1, self.P2, self.Q, _, _ = cv2.stereoRectify(
                        cameraMatrix1=new_K1, distCoeffs1=np.zeros(5),
                        cameraMatrix2=new_K2, distCoeffs2=np.zeros(5),
                        imageSize=(w, h),
                        R=self.R, T=T_meters,
                        flags=cv2.CALIB_ZERO_DISPARITY,
                        alpha=0.0
                    )
                    
                    # 计算鱼眼校正映射
                    self.map1_left, self.map2_left = cv2.fisheye.initUndistortRectifyMap(
                        self.K1, self.D1.reshape(4, 1), self.R1, self.P1, (w, h), cv2.CV_16SC2
                    )
                    self.map1_right, self.map2_right = cv2.fisheye.initUndistortRectifyMap(
                        self.K2, self.D2.reshape(4, 1), self.R2, self.P2, (w, h), cv2.CV_16SC2
                    )
                    
                    print("✅ 鱼眼立体校正设置完成（混合方法）")
                    
                except Exception as fisheye_error:
                    print(f"⚠️ 鱼眼专用校正失败，尝试标准方法: {fisheye_error}")
                    
                    # 方法2：回退到标准立体校正
                    self.R1, self.R2, self.P1, self.P2, self.Q, _, _ = cv2.stereoRectify(
                        cameraMatrix1=self.K1, distCoeffs1=self.D1,
                        cameraMatrix2=self.K2, distCoeffs2=self.D2,
                        imageSize=(w, h),
                        R=self.R, T=T_meters,
                        flags=cv2.CALIB_ZERO_DISPARITY,
                        alpha=0.0
                    )
                    
                    # 使用标准校正映射
                    self.map1_left, self.map2_left = cv2.initUndistortRectifyMap(
                        self.K1, self.D1, self.R1, self.P1, (w, h), cv2.CV_16SC2
                    )
                    self.map1_right, self.map2_right = cv2.initUndistortRectifyMap(
                        self.K2, self.D2, self.R2, self.P2, (w, h), cv2.CV_16SC2
                    )
                    
                    print("✅ 标准立体校正设置完成（鱼眼参数）")
                
            else:
                # 针孔立体校正
                self.R1, self.R2, self.P1, self.P2, self.Q, _, _ = cv2.stereoRectify(
                    cameraMatrix1=self.K1, distCoeffs1=self.D1,
                    cameraMatrix2=self.K2, distCoeffs2=self.D2,
                    imageSize=(w, h),
                    R=self.R, T=T_meters,
                    flags=cv2.CALIB_ZERO_DISPARITY,
                    alpha=0.0
                )
                
                # 计算校正映射
                self.map1_left, self.map2_left = cv2.initUndistortRectifyMap(
                    self.K1, self.D1, self.R1, self.P1, (w, h), cv2.CV_16SC2
                )
                self.map1_right, self.map2_right = cv2.initUndistortRectifyMap(
                    self.K2, self.D2, self.R2, self.P2, (w, h), cv2.CV_16SC2
                )
                
                print("✅ 针孔立体校正设置完成")
            
            # 设置视差计算器
            self.setup_stereo_matcher()
            
            # 计算基线距离
            baseline = abs(T_meters[0, 0])
            print(f"基线距离: {baseline:.3f}m")
            print(f"校正后左相机焦距: fx={self.P1[0,0]:.1f}, fy={self.P1[1,1]:.1f}")
            print(f"校正后右相机焦距: fx={self.P2[0,0]:.1f}, fy={self.P2[1,1]:.1f}")
            
            return True
            
        except Exception as e:
            print(f"❌ 立体校正设置失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def setup_stereo_matcher(self, min_disparity=0, num_disparities=128, block_size=5, uniqueness_ratio=10):
        """设置立体匹配器（支持外部参数）"""
        # 确保参数有效性
        if num_disparities % 16 != 0:
            num_disparities = (num_disparities // 16) * 16
            print(f"调整视差范围为16的倍数: {num_disparities}")
        
        if block_size % 2 == 0:
            block_size += 1
            print(f"调整块大小为奇数: {block_size}")
        
        # 计算P1和P2参数
        P1 = 8 * 3 * block_size ** 2
        P2 = 32 * 3 * block_size ** 2
        
        self.stereo_matcher = cv2.StereoSGBM_create(
            minDisparity=min_disparity,
            numDisparities=num_disparities,
            blockSize=block_size,
            P1=P1,
            P2=P2,
            disp12MaxDiff=1,  # 严格一致性检查
            uniquenessRatio=uniqueness_ratio,  # 可调整的唯一性要求
            speckleWindowSize=200,  # 增大斑点窗口
            speckleRange=32,  # 增大斑点范围
            preFilterCap=63,  # 恢复预滤波强度
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
        )
        
        print(f"✅ 立体匹配器设置完成")
        print(f"参数: 最小视差={min_disparity}, 视差范围={num_disparities}, 块大小={block_size}x{block_size}")
        print(f"      唯一性={uniqueness_ratio}, P1={P1}, P2={P2}")

    def update_sgbm_params(self, min_disparity=0, num_disparities=128, block_size=5, uniqueness_ratio=10):
        """更新SGBM参数"""
        self.setup_stereo_matcher(min_disparity, num_disparities, block_size, uniqueness_ratio)
    
    def rectify_stereo_pair(self, left_image: np.ndarray, right_image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """校正立体图像对"""
        try:
            if self.map1_left is None:
                # 首次使用，设置立体校正
                h, w = left_image.shape[:2]
                if not self.setup_stereo_rectification((w, h)):
                    raise ValueError("立体校正设置失败")
            
            # 应用校正映射
            rectified_left = cv2.remap(left_image, self.map1_left, self.map2_left, cv2.INTER_LINEAR)
            rectified_right = cv2.remap(right_image, self.map1_right, self.map2_right, cv2.INTER_LINEAR)
            
            return rectified_left, rectified_right
            
        except Exception as e:
            print(f"❌ 立体校正失败: {e}")
            return left_image, right_image
    
    def compute_disparity(self, left_image: np.ndarray, right_image: np.ndarray) -> np.ndarray:
        """计算视差图（增强预处理和后处理）"""
        try:
            # 校正图像
            rect_left, rect_right = self.rectify_stereo_pair(left_image, right_image)
            
            # 转换为灰度图
            if len(rect_left.shape) == 3:
                gray_left = cv2.cvtColor(rect_left, cv2.COLOR_BGR2GRAY)
            else:
                gray_left = rect_left
                
            if len(rect_right.shape) == 3:
                gray_right = cv2.cvtColor(rect_right, cv2.COLOR_BGR2GRAY)
            else:
                gray_right = rect_right
            
            # 增强预处理
            # 1. 直方图均衡化，提高对比度
            gray_left = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(gray_left)
            gray_right = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(gray_right)
            
            # 2. 轻微高斯滤波减噪
            gray_left = cv2.GaussianBlur(gray_left, (3, 3), 0)
            gray_right = cv2.GaussianBlur(gray_right, (3, 3), 0)

# 计算视差
            disparity = self.stereo_matcher.compute(gray_left, gray_right)
            
            # 转换为浮点数并归一化
            disparity = disparity.astype(np.float32) / 16.0
            
            # 增强后处理
            # 1. 去除明显错误的视差值
            disparity[disparity < 0] = 0
            disparity[disparity > 128] = 0
            
            # 2. 形态学操作去除小噪声
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            disparity_cleaned = cv2.morphologyEx(disparity, cv2.MORPH_CLOSE, kernel)
            
            # 3. 双边滤波保持边缘同时平滑
            disparity_filtered = cv2.bilateralFilter(
                disparity_cleaned.astype(np.uint8), 9, 75, 75
            ).astype(np.float32)
            
            return disparity_filtered
            
        except Exception as e:
            print(f"❌ 计算视差失败: {e}")
            return np.zeros((480, 640), dtype=np.float32)
    
    def get_depth_at_point(self, u: int, v: int, disparity_map: np.ndarray) -> Optional[float]:
        """获取指定像素点的深度值"""
        try:
            if disparity_map is None or disparity_map.size == 0:
                return None
            
            h, w = disparity_map.shape
            if not (0 <= u < w and 0 <= v < h):
                print(f"⚠️ 坐标超出范围: ({u}, {v}), 图像尺寸: {w}x{h}")
                return None
            
            # 获取视差值
            disparity = disparity_map[v, u]
            
            # 检查视差有效性
            if disparity <= 0:
                print(f"⚠️ 无效视差: {disparity}")
                return None
            
            # 计算深度（使用基线和焦距）
            baseline = abs(self.T[0, 0]) / 1000.0  # 转换为米
            focal_length = (self.K1[0, 0] + self.K2[0, 0]) / 2  # 平均焦距
            
            depth = (focal_length * baseline) / disparity
            
            print(f"深度计算: 视差={disparity:.2f}, 基线={baseline:.3f}m, 焦距={focal_length:.1f}, 深度={depth:.3f}m")
            
            return depth
            
        except Exception as e:
            print(f"❌ 深度计算失败: {e}")
            return None
    
    def estimate_depth_region(self, u: int, v: int, disparity_map: np.ndarray, 
                            region_size: int = 9) -> Optional[float]:
        """估计区域平均深度（提高稳定性和精度）"""
        try:
            h, w = disparity_map.shape
            
            # 计算区域边界
            half_size = region_size // 2
            u_min = max(0, u - half_size)
            u_max = min(w, u + half_size + 1)
            v_min = max(0, v - half_size)
            v_max = min(h, v + half_size + 1)
            
            # 提取区域
            region = disparity_map[v_min:v_max, u_min:u_max]
            
            # 过滤无效视差
            valid_disparities = region[region > 0]
            
            if len(valid_disparities) < 3:  # 至少需要3个有效点
                print(f"⚠️ 区域内有效视差不足: {len(valid_disparities)}")
                return None
            
            # 使用统计方法提高稳定性
            mean_disparity = np.mean(valid_disparities)
            std_disparity = np.std(valid_disparities)
            
            # 去除异常值（超过2个标准差的点）
            filtered_disparities = valid_disparities[
                np.abs(valid_disparities - mean_disparity) <= 2 * std_disparity
            ]
            
            if len(filtered_disparities) == 0:
                median_disparity = mean_disparity
            else:
                median_disparity = np.median(filtered_disparities)
            
            # 计算深度
            baseline = abs(self.T[0, 0]) / 1000.0  # 转换为米
            focal_length = (self.K1[0, 0] + self.K2[0, 0]) / 2  # 平均焦距
            depth = (focal_length * baseline) / median_disparity
            
            print(f"区域深度估计: 视差={median_disparity:.2f}±{std_disparity:.2f}, 深度={depth:.3f}m, 有效像素={len(valid_disparities)}/{region.size}")
            
            return depth
            
        except Exception as e:
            print(f"❌ 区域深度估计失败: {e}")
            return None
    
    def create_depth_map(self, left_image: np.ndarray, right_image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """创建深度图（增强质量）"""
        try:
            # 计算视差图
            disparity_map = self.compute_disparity(left_image, right_image)
            
            # 创建深度图
            depth_map = np.zeros_like(disparity_map, dtype=np.float32)
            
            # 获取有效视差的掩码
            valid_mask = disparity_map > 0
            
            # 计算深度
            baseline = abs(self.T[0, 0]) / 1000.0  # 转换为米
            focal_length = (self.K1[0, 0] + self.K2[0, 0]) / 2  # 平均焦距
            
            # 批量计算深度
            depth_map[valid_mask] = (focal_length * baseline) / disparity_map[valid_mask]
            
            # 深度范围限制和平滑
            depth_map = np.clip(depth_map, 0.05, 1.5)
            
            # 对深度图进行平滑处理
            if np.sum(valid_mask) > 0:
                # 使用双边滤波保持边缘
                depth_map_smooth = cv2.bilateralFilter(
                    depth_map.astype(np.float32), 5, 50, 50
                )
                # 只在有效区域应用平滑
                depth_map[valid_mask] = depth_map_smooth[valid_mask]
            
            return depth_map, disparity_map
            
        except Exception as e:
            print(f"❌ 创建深度图失败: {e}")
            return np.zeros((480, 640), dtype=np.float32), np.zeros((480, 640), dtype=np.float32)
    
    def get_3d_point(self, u: int, v: int, left_image: np.ndarray, right_image: np.ndarray) -> Optional[Tuple[float, float, float]]:
        """获取指定像素点的3D坐标（左相机坐标系）"""
        try:
            # 计算视差图
            disparity_map = self.compute_disparity(left_image, right_image)
            
            # 获取深度
            depth = self.estimate_depth_region(u, v, disparity_map, region_size=9)
            
            if depth is None:
                return None
            
            # 计算3D坐标（使用左相机原始内参，与手眼标定一致）
            fx = self.K1[0, 0]
            fy = self.K1[1, 1]
            cx = self.K1[0, 2]
            cy = self.K1[1, 2]
            
            # 相机坐标系下的3D点
            X = (u - cx) * depth / fx
            Y = (v - cy) * depth / fy
            Z = depth
            
            print(f"3D点计算: 像素({u}, {v}) → 左相机坐标({X:.3f}, {Y:.3f}, {Z:.3f})m")
            
            return (X, Y, Z)
            
        except Exception as e:
            print(f"❌ 3D点计算失败: {e}")
            return None
    
    def visualize_depth(self, depth_map: np.ndarray, disparity_map: np.ndarray) -> np.ndarray:
        """可视化深度图（增强显示效果）"""
        try:
            # 归一化深度图用于显示
            valid_mask = depth_map > 0
            if np.sum(valid_mask) == 0:
                return np.zeros((*depth_map.shape, 3), dtype=np.uint8)
            
            # 使用更好的深度范围
            valid_depths = depth_map[valid_mask]
            # 去除极值，使用95%分位数作为范围
            min_depth = np.percentile(valid_depths, 5)
            max_depth = np.percentile(valid_depths, 95)
            
            normalized_depth = np.zeros_like(depth_map)
            if max_depth > min_depth:
                # 限制在合理范围内
                clipped_depth = np.clip(depth_map, min_depth, max_depth)
                normalized_depth[valid_mask] = 255 * (clipped_depth[valid_mask] - min_depth) / (max_depth - min_depth)
            
            # 应用更好的颜色映射
            depth_colored = cv2.applyColorMap(normalized_depth.astype(np.uint8), cv2.COLORMAP_TURBO)
            
            # 无效区域设为黑色
            depth_colored[~valid_mask] = [0, 0, 0]
            
            # 添加深度信息文本
            valid_percent = np.sum(valid_mask) / depth_map.size * 100
            cv2.putText(depth_colored, f"Depth: {min_depth:.2f}m - {max_depth:.2f}m", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(depth_colored, f"Valid: {valid_percent:.1f}%, Baseline: {abs(self.T[0,0])/1000:.3f}m", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            return depth_colored
            
        except Exception as e:
            print(f"❌ 深度可视化失败: {e}")
            return np.zeros((*depth_map.shape, 3), dtype=np.uint8)

def test_depth_estimation():
    """测试深度估计功能"""
    print("🎯 双目鱼眼深度估计测试")
    print("=" * 50)
    
    # 创建深度估计器
    estimator = StereoDepthEstimator()
    
    # 打开双目相机
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ 无法打开相机")
        return
    
    # 设置分辨率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print("📷 双目相机已启动")
    print("💡 操作说明:")
    print("  - 按 'q' 退出")
    print("  - 按 'd' 显示/隐藏深度图")
    print("  - 按 'r' 显示/隐藏校正图像")
    print("  - 鼠标左键点击获取深度值")
    print("  - 鼠标右键点击获取3D坐标")
    
    show_depth = False
    show_rectified = False
    
    def mouse_callback(event, x, y, flags, param):
        """鼠标回调函数"""
        left_img, right_img = param
        if left_img is None or right_img is None:
            return
            
        if event == cv2.EVENT_LBUTTONDOWN:
            # 左键：获取深度值
            disparity_map = estimator.compute_disparity(left_img, right_img)
            depth = estimator.estimate_depth_region(x, y, disparity_map)
            if depth:
                print(f"🎯 点击坐标({x}, {y}) → 深度: {depth:.3f}m")
            else:
                print(f"❌ 无法获取点击坐标({x}, {y})的深度")
                
        elif event == cv2.EVENT_RBUTTONDOWN:
            # 右键：获取3D坐标
            point_3d = estimator.get_3d_point(x, y, left_img, right_img)
            if point_3d:
                X, Y, Z = point_3d
                print(f"🎯 点击坐标({x}, {y}) → 3D坐标: X={X:.3f}m, Y={Y:.3f}m, Z={Z:.3f}m")
            else:
                print(f"❌ 无法获取点击坐标({x}, {y})的3D坐标")
    
    # 设置鼠标回调
    cv2.namedWindow('Stereo Depth Estimation', cv2.WINDOW_AUTOSIZE)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # 分离左右图像
        left_img = frame[:, 0:640]
        right_img = frame[:, 640:1280]
        
        # 设置鼠标回调参数
        cv2.setMouseCallback('Stereo Depth Estimation', mouse_callback, (left_img, right_img))
        
        if show_depth:
            # 显示深度图模式
            depth_map, disparity_map = estimator.create_depth_map(left_img, right_img)
            depth_vis = estimator.visualize_depth(depth_map, disparity_map)
            
            if show_rectified:
                # 显示校正后的图像
                rect_left, rect_right = estimator.rectify_stereo_pair(left_img, right_img)
                top_row = np.hstack((rect_left, rect_right))
                bottom_row = np.hstack((depth_vis, depth_vis))  # 深度图显示两次
                display = np.vstack((top_row, bottom_row))
                
                # 添加标签
                cv2.putText(display, "Left Rectified", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(display, "Right Rectified", (650, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(display, "Depth Map", (10, 510), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(display, "Disparity Map", (650, 510), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                # 只显示深度图
                display = depth_vis
                cv2.putText(display, "Depth Map (Left Click: Depth, Right Click: 3D)", 
                           (10, display.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        else:
            # 显示原始左右图像
            display = frame
            cv2.putText(display, "Left Camera", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display, "Right Camera", (650, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display, "Press 'd' for depth, 'r' for rectified", (10, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        cv2.imshow('Stereo Depth Estimation', display)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('d'):
            show_depth = not show_depth
            print(f"切换显示模式: {'深度图' if show_depth else '原始图像'}")
        elif key == ord('r'):
            show_rectified = not show_rectified
            print(f"校正图像显示: {'开启' if show_rectified else '关闭'}")
    
    cap.release()
    cv2.destroyAllWindows()
    print("✅ 测试完成")

if __name__ == "__main__":
    test_depth_estimation()
