# -*- coding: utf-8 -*-
"""
视觉检测模块
- 颜色阈值检测（HSV）
- 简单形状检测（圆/矩形/轮廓质心）
- 支持标准针孔模型和鱼眼模型
使用最小外接矩形检测，返回旋转角度信息：
{
	'success': bool,
	'count': int,
	'objects': [
		{
			'center': (cx, cy),
			'size': (width, height), 
			'angle': rotation_angle,
			'short_edge_angle': short_edge_rotation_angle,
			'box_points': [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
		}, ...
	]
}
注：short_edge_angle为物体短边的旋转角度，已转换为顺时针为正的系统标准，用于机械臂抓取角度计算
"""
import cv2
import numpy as np
from typing import Tuple, Dict, Any, Optional

class VisionDetector:
	def __init__(self, camera_matrix: np.ndarray, dist_coeffs: np.ndarray, model: str = 'fisheye'):
		self.camera_matrix = camera_matrix
		self.dist_coeffs = dist_coeffs
		self.model = model.lower() if isinstance(model, str) else 'fisheye'

	def undistort_image(self, image: np.ndarray) -> np.ndarray:
		"""根据相机模型去畸变图像"""
		if self.model == 'fisheye':
			# 鱼眼模型去畸变
			h, w = image.shape[:2]
			R = np.eye(3)
			new_camera_matrix = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
				self.camera_matrix, self.dist_coeffs, (w, h), R, balance=0.0
			)
			mapx, mapy = cv2.fisheye.initUndistortRectifyMap(
				self.camera_matrix, self.dist_coeffs, R, new_camera_matrix, (w, h), cv2.CV_16SC2
			)
			return cv2.remap(image, mapx, mapy, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
		else:
			# 针孔模型去畸变
			h, w = image.shape[:2]
			new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
				self.camera_matrix, self.dist_coeffs, (w, h), 0, (w, h)
			)
			return cv2.undistort(image, self.camera_matrix, self.dist_coeffs, None, new_camera_matrix)

	def detect_color(self, bgr_image: np.ndarray, hsv_lower: Tuple[int,int,int], hsv_upper: Tuple[int,int,int], min_area: int = 0, undistort: bool = True) -> Dict[str, Any]:
		"""基于HSV的颜色检测，返回所有轮廓的最小外接矩形及旋转角度
		Args:
			min_area: 过滤小目标的最小面积（像素），默认为0不过滤
			undistort: 是否先去畸变，默认True
		"""
		# 可选去畸变
		if undistort:
			bgr_image = self.undistort_image(bgr_image)
			
		hsv = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
		mask = cv2.inRange(hsv, np.array(hsv_lower, dtype=np.uint8), np.array(hsv_upper, dtype=np.uint8))
		mask = cv2.medianBlur(mask, 5)
		contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
		if not contours:
			return {'success': False, 'count': 0, 'objects': []}
		objects = []
		for contour in contours:
			# 使用最小外接矩形
			rect = cv2.minAreaRect(contour)
			center, size, angle = rect
			
			# 过滤小目标
			if min_area > 0 and (size[0] * size[1]) < min_area:
				continue
			
			# 获取矩形的四个角点
			box_points = cv2.boxPoints(rect)
			box_points = np.array(box_points, dtype=int)
			
			# 计算短边角度
			width, height = size
			if width < height:
				# width 是短边，angle 就是短边与水平轴的夹角
				short_edge_angle = angle
			else:
				# width 是长边，height 是短边，短边角度 = angle + 90
				short_edge_angle = angle + 90
				
			# 将角度规范化到 [-90, 90] 范围
			while short_edge_angle > 90:
				short_edge_angle -= 180
			while short_edge_angle < -90:
				short_edge_angle += 180
			
			# 转换角度方向：从数学标准（逆时针为正）转为系统标准（顺时针为正）
			final_yaw = -short_edge_angle
			
			# 构建对象信息
			obj_info = {
				'center': (int(center[0]), int(center[1])),
				'size': (int(size[0]), int(size[1])),
				'angle': angle,
				'short_edge_angle': final_yaw,
				'box_points': [tuple(point) for point in box_points]
			}
			objects.append(obj_info)
			
		if not objects:
			return {'success': False, 'count': 0, 'objects': []}
		# 可根据面积从大到小排序（可选）
		# objects.sort(key=lambda obj: obj['size'][0] * obj['size'][1], reverse=True)
		return {'success': True, 'count': len(objects), 'objects': objects}

	def detect_circles(self, bgr_image: np.ndarray, dp: float=1.2, minDist: float=20, param1: float=100, param2: float=30, minRadius: int=5, maxRadius: int=200, undistort: bool = True) -> Dict[str, Any]:
		"""检测圆（HoughCircles），返回所有圆的最小外接矩形及旋转角度"""
		# 可选去畸变
		if undistort:
			bgr_image = self.undistort_image(bgr_image)
			
		h, w_img = bgr_image.shape[:2]
		gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
		gray = cv2.GaussianBlur(gray, (9,9), 2)
		circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp, minDist, param1=param1, param2=param2, minRadius=minRadius, maxRadius=maxRadius)
		if circles is None:
			return {'success': False, 'count': 0, 'objects': []}
		circles = np.uint16(np.around(circles))[0]
		objects = []
		for c in circles:
			cx, cy, r = int(c[0]), int(c[1]), int(c[2])
			
			# 对于圆形，创建一个正方形的最小外接矩形
			# 圆形的角度设为0度（因为圆形旋转不影响形状）
			size = (2 * r, 2 * r)  # 正方形边长
			center = (cx, cy)
			angle = 0.0  # 圆形旋转角度为0
			
			# 生成正方形的四个角点
			half_size = r
			box_points = [
				(cx - half_size, cy - half_size),  # 左上
				(cx + half_size, cy - half_size),  # 右上  
				(cx + half_size, cy + half_size),  # 右下
				(cx - half_size, cy + half_size)   # 左下
			]
			
			# 确保角点在图像范围内
			box_points = [(max(0, min(w_img-1, int(x))), max(0, min(h-1, int(y)))) for x, y in box_points]
			
			# 计算短边角度（对于圆形，长宽相等，短边角度就是0）
			width, height = size
			if width < height:
				# width 是短边
				short_edge_angle = angle
			else:
				# height 是短边（对于圆形width=height，这种情况角度为0）
				short_edge_angle = angle + 90 if width > height else 0.0
				
			# 将角度规范化到 [-90, 90] 范围
			while short_edge_angle > 90:
				short_edge_angle -= 180
			while short_edge_angle < -90:
				short_edge_angle += 180
			
			# 转换角度方向：从数学标准（逆时针为正）转为系统标准（顺时针为正）
			final_yaw = -short_edge_angle
			
			# 构建对象信息
			obj_info = {
				'center': center,
				'size': size,
				'angle': angle,
				'short_edge_angle': final_yaw,
				'box_points': box_points
			}
			objects.append(obj_info)
			
		if not objects:
			return {'success': False, 'count': 0, 'objects': []}
		# 可根据半径从大到小排序（可选）
		# objects.sort(key=lambda obj: obj['size'][0], reverse=True)
		return {'success': True, 'count': len(objects), 'objects': objects}

	def detect_qrcode(self, bgr_image: np.ndarray, undistort: bool = True) -> Dict[str, Any]:
		"""检测二维码（支持多码），返回每个二维码最小外接矩形及旋转角度"""
		# 可选去畸变
		if undistort:
			bgr_image = self.undistort_image(bgr_image)
			
		detector = cv2.QRCodeDetector()
		objects = []
		try:
			# 优先尝试多二维码接口
			if hasattr(detector, 'detectAndDecodeMulti'):
				result = detector.detectAndDecodeMulti(bgr_image)
				if isinstance(result, tuple) and len(result) >= 3:
					retval = result[0]
					decoded_info = result[1]
					points = result[2]
					if retval and points is not None and len(decoded_info) > 0:
						for pts in list(points):
							if pts is None:
								continue
							pts = np.array(pts).reshape(-1, 2).astype(np.float32)
							
							# 使用二维码的四个角点计算最小外接矩形
							rect = cv2.minAreaRect(pts)
							center, size, angle = rect
							
							# 获取矩形的四个角点
							box_points = cv2.boxPoints(rect)
							box_points = np.array(box_points, dtype=int)
							
							# 计算短边角度
							width, height = size
							if width < height:
								# width 是短边
								short_edge_angle = angle
							else:
								# width 是长边，height 是短边
								short_edge_angle = angle + 90
								
							# 将角度规范化到 [-90, 90] 范围
							while short_edge_angle > 90:
								short_edge_angle -= 180
							while short_edge_angle < -90:
								short_edge_angle += 180
							
							# 转换角度方向：从数学标准（逆时针为正）转为系统标准（顺时针为正）
							final_yaw = -short_edge_angle
							
							# 构建对象信息
							obj_info = {
								'center': (int(center[0]), int(center[1])),
								'size': (int(size[0]), int(size[1])),
								'angle': angle,
								'short_edge_angle': final_yaw,
								'box_points': [tuple(point) for point in box_points]
							}
							objects.append(obj_info)
						return {'success': len(objects) > 0, 'count': len(objects), 'objects': objects}
			
			# 回退到单二维码接口
			text, pts, _ = detector.detectAndDecode(bgr_image)
			if pts is not None and text is not None and len(text) > 0:
				pts = np.array(pts).reshape(-1, 2).astype(np.float32)
				
				# 使用二维码的四个角点计算最小外接矩形
				rect = cv2.minAreaRect(pts)
				center, size, angle = rect
				
				# 获取矩形的四个角点
				box_points = cv2.boxPoints(rect)
				box_points = np.array(box_points, dtype=int)
				
				# 计算短边角度
				width, height = size
				if width < height:
					# width 是短边
					short_edge_angle = angle
				else:
					# width 是长边，height 是短边
					short_edge_angle = angle + 90
					
				# 将角度规范化到 [-90, 90] 范围
				while short_edge_angle > 90:
					short_edge_angle -= 180
				while short_edge_angle < -90:
					short_edge_angle += 180
				
				# 转换角度方向：从数学标准（逆时针为正）转为系统标准（顺时针为正）
				final_yaw = -short_edge_angle
				
				# 构建对象信息
				obj_info = {
					'center': (int(center[0]), int(center[1])),
					'size': (int(size[0]), int(size[1])),
					'angle': angle,
					'short_edge_angle': final_yaw,
					'box_points': [tuple(point) for point in box_points]
				}
				objects.append(obj_info)
				return {'success': True, 'count': len(objects), 'objects': objects}
		except Exception:
			pass
		return {'success': False, 'count': 0, 'objects': []}
