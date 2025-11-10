"""
眼在手上 
用采集到的图片信息和机械臂位姿信息计算相机坐标系相对于机械臂末端坐标系的旋转矩阵和平移向量
支持标准针孔模型和鱼眼模型

所有单位为米

"""

import os.path
import os
os.environ['KMP_DUPLICATE_LIB_OK']='True'
import cv2
import numpy as np
import csv
import json
np.set_printoptions(precision=8,suppress=True)

class EyeInHand():
    def __init__(self,):
        self.csv_path = None
        self.camera_model = 'fisheye'  # 默认鱼眼
        self.camera_matrix = None
        self.dist_coeffs = None

    def load_camera_params(self, config_path="config/calibration_parameter.json"):
        """加载相机参数和模型类型"""
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    one_config = config.get('one', {})
                    if one_config:
                        self.camera_matrix = np.array(one_config.get('camera_matrix', [[1, 0, 0], [0, 1, 0], [0, 0, 1]]))
                        
                        # 处理畸变系数的两种格式
                        camera_distortion = one_config.get('camera_distortion', [[0, 0, 0, 0, 0]])
                        if camera_distortion:
                            if len(camera_distortion) > 0:
                                if isinstance(camera_distortion[0], list):
                                    if len(camera_distortion[0]) > 1:
                                        # 旧格式：[[-0.04169075, -0.10853007, ...]]  (一行多列)
                                        self.dist_coeffs = np.array(camera_distortion[0], dtype=np.float64)
                                    else:
                                        # 新格式：[[0.281...], [0.074...], ...]  (多行一列)
                                        self.dist_coeffs = np.array([row[0] for row in camera_distortion if len(row) > 0], dtype=np.float64)
                                else:
                                    # 直接是数值列表
                                    self.dist_coeffs = np.array(camera_distortion, dtype=np.float64)
                            else:
                                self.dist_coeffs = np.array([0, 0, 0, 0, 0], dtype=np.float64)
                        else:
                            self.dist_coeffs = np.array([0, 0, 0, 0, 0], dtype=np.float64)
                        
                        self.camera_model = one_config.get('model', 'fisheye')
                        print(f"✅ 加载相机参数成功，模型: {self.camera_model}")
                        print(f"内参矩阵:\n{self.camera_matrix}")
                        print(f"畸变系数: {self.dist_coeffs}")
                        return True
        except Exception as e:
            print(f"⚠️ 加载相机参数失败: {e}")
        
        # 使用默认参数
        self.camera_matrix = np.array([[500, 0, 320], [0, 500, 240], [0, 0, 1]], dtype=np.float64)
        self.dist_coeffs = np.array([0, 0, 0, 0], dtype=np.float64)  # 鱼眼默认4参数
        self.camera_model = 'fisheye'
        print(f"⚠️ 使用默认相机参数，模型: {self.camera_model}")
        return False

    def euler_angles_to_rotation_matrix(self, yaw, pitch, roll):
        """
        将ZYX顺序的欧拉角（度数制）转换为旋转矩阵
        
        Args:
            yaw: 偏航角（绕Z轴旋转，度数制）
            pitch: 俯仰角（绕Y轴旋转，度数制）
            roll: 翻滚角（绕X轴旋转，度数制）
        
        Returns:
            3x3旋转矩阵
        """
        # 将度数转换为弧度
        yaw_rad = np.deg2rad(yaw)
        pitch_rad = np.deg2rad(pitch)  
        roll_rad = np.deg2rad(roll)
        
        # 计算各轴旋转矩阵
        Rx = np.array([[1, 0, 0],
                    [0, np.cos(roll_rad), -np.sin(roll_rad)],
                    [0, np.sin(roll_rad), np.cos(roll_rad)]])
        Ry = np.array([[np.cos(pitch_rad), 0, np.sin(pitch_rad)],
                    [0, 1, 0],
                    [-np.sin(pitch_rad), 0, np.cos(pitch_rad)]])
        Rz = np.array([[np.cos(yaw_rad), -np.sin(yaw_rad), 0],
                    [np.sin(yaw_rad), np.cos(yaw_rad), 0],
                    [0, 0, 1]])
        
        # ZYX欧拉角：先绕Z轴旋转，再绕Y轴，最后绕X轴
        R = Rz @ Ry @ Rx
        
        return R

    def pose_to_homogeneous_matrix(self, pose):
        """
        将位姿向量转换为齐次变换矩阵
        
        Args:
            pose: [x, y, z, yaw, pitch, roll] 
                  位置单位：mm (>1时) 或 m (<=1时)
                  角度单位：度 (degrees) - ZYX顺序
        
        Returns:
            4x4齐次变换矩阵
        """
        x, y, z, yaw, pitch, roll = pose
        if x > 1: # 把毫米转为米
            x = x / 1000
            y = y / 1000
            z = z / 1000
        
        # 传递ZYX顺序的欧拉角：yaw, pitch, roll
        R = self.euler_angles_to_rotation_matrix(yaw, pitch, roll)
        t = np.array([x, y, z]).reshape(3, 1)
        H = np.eye(4)
        H[:3, :3] = R
        H[:3, 3] = t[:, 0]
        return H

    def save_matrices_to_csv(self, matrices, file_name):
        rows, cols = matrices[0].shape
        num_matrices = len(matrices)
        combined_matrix = np.zeros((rows, cols * num_matrices))

        for i, matrix in enumerate(matrices):
            combined_matrix[:, i * cols: (i + 1) * cols] = matrix

        with open(file_name, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            for row in combined_matrix:
                csv_writer.writerow(row)

    def poses_to_matrix_save_csv(self, filepath, csv_path):
        self.csv_path = csv_path
        # 打开文本文件
        with open(filepath, 'r') as file:
            data = file.readlines()
        # 处理每一行，将字符串转换为整数列表
        pose_vectors = []
        for line in data:
            # 分割每一行的字符串，用逗号作为分隔符，并将每个值转换为整数
            int_values = [float(value) for value in line.strip().split(',')]
            pose_vectors.append(int_values)

        matrices = []
        for i in range(0,len(pose_vectors)):
            matrices.append(self.pose_to_homogeneous_matrix(pose_vectors[i]))
        # 将齐次变换矩阵列表存储到 CSV 文件中
        self.save_matrices_to_csv(matrices, self.csv_path)

    def compute_T(self, images_path, corner_point_width, corner_point_height, corner_point_size):
        # 加载相机参数
        self.load_camera_params()
        
        # 设置寻找亚像素角点的参数，采用的停止准则是最大循环次数30和最大误差容限0.001
        criteria = (cv2.TERM_CRITERIA_MAX_ITER | cv2.TERM_CRITERIA_EPS, 30, 0.001)
        # 获取标定板角点的位置
        objp = np.zeros((corner_point_width * corner_point_height, 3), np.float32)
        objp[:, :2] = np.mgrid[0:corner_point_width, 0:corner_point_height].T.reshape(-1, 2)     
        # 将世界坐标系建在标定板上，所有点的Z坐标全部为0，所以只需要赋值x和y
        objp = corner_point_size * objp

        obj_points = []     # 存储3D点
        img_points = []     # 存储2D点
        
        # 动态遍历：按实际拍摄的图片数量进行标定（支持 1.jpg, 2.jpg, ... 的编号命名）
        # 收集目录下所有形如 N.jpg 的文件，并按 N 递增排序
        numbered_images = []
        try:
            for fname in os.listdir(images_path):
                if fname.lower().endswith('.jpg'):
                    name, _ = os.path.splitext(fname)
                    if name.isdigit():
                        numbered_images.append((int(name), os.path.join(images_path, fname)))
        except Exception:
            numbered_images = []

        # 若没有编号命名，则回退为按文件名排序的所有jpg
        if not numbered_images:
            fallback = [os.path.join(images_path, f) for f in os.listdir(images_path) if f.lower().endswith('.jpg')]
            numbered_images = list(enumerate(sorted(fallback), start=1))

        # 逐张处理，并记录成功匹配角点的图片编号，用于对齐机器人位姿
        used_ids = []
        for img_id, image in sorted(numbered_images, key=lambda x: x[0]):
            if os.path.exists(image):
                img = cv2.imread(image)
                if img is None:
                    continue
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                size = gray.shape[::-1]
                ret, corners = cv2.findChessboardCorners(gray, (corner_point_width, corner_point_height), None)
                if ret:
                    obj_points.append(objp)
                    corners2 = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), criteria)  # 在原角点的基础上寻找亚像素角点
                    if corners2 is not None:
                        img_points.append(corners2)
                    else:
                        img_points.append(corners)
                    used_ids.append(img_id)
            cv2.destroyAllWindows()
        N = len(img_points)
        
        if N == 0:
            raise ValueError("没有找到有效的标定板图像")
        
        print(f"找到 {N} 个有效的标定板图像")
        print(f"使用相机模型: {self.camera_model}")

        # 机器人末端在基坐标系下的位姿
        tool_pose = np.loadtxt(self.csv_path, delimiter=',')  #与poses_save_csv保存的名字对应上
        R_tool = []
        t_tool = []
        rvecs = []
        tvecs = []
        
        # 使用成功检测到角点的对应图片编号，对齐机器人位姿（图片编号从1开始）
        if used_ids:
            for img_id in used_ids:
                idx = img_id - 1  # 转为0基
                R_tool.append(tool_pose[0:3, 4*idx:4*idx+3])
                t_tool.append(tool_pose[0:3, 4*idx+3])
        else:
            # 兜底：按前N个
            for i in range(int(N)):
                R_tool.append(tool_pose[0:3,4*i:4*i+3])
                t_tool.append(tool_pose[0:3,4*i+3])

        # 根据相机模型计算外参
        if self.camera_model == 'fisheye':
            try:
                # 对于鱼眼模型，我们使用 fisheye.calibrate 并固定内参来求解外参
                # 这是最精确的做法，因为它使用了完整的鱼眼畸变模型来优化位姿
                
                # 准备数据，obj_points需要为每个图像重复一次
                obj_points_fisheye = [objp for _ in range(len(img_points))]

                # 设置标志位：使用已知的内参，并且不重新计算它们
                flags = cv2.fisheye.CALIB_USE_INTRINSIC_GUESS | cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC | cv2.fisheye.CALIB_FIX_INTRINSIC

                # 调用函数，它会返回固定的内参和计算出的外参rvecs, tvecs
                # 注意：这里的 K 和 D 是 self.camera_matrix 和 self.dist_coeffs
                rms, K, D, rvecs, tvecs = cv2.fisheye.calibrate(
                    obj_points_fisheye,
                    img_points,
                    gray.shape[::-1],  # 图像尺寸
                    self.camera_matrix,
                    self.dist_coeffs,
                    flags=flags
                )
                print(f"鱼眼模型外参重投影RMS误差: {rms:.4f}")
            except Exception as e:
                print(f"鱼眼模型外参计算失败: {e}")
                return
        else: # 标准针孔模型
            rvecs = []
            tvecs = []
            # 正确做法：遍历每张图片，使用已知内参，单独求解外参
            for i in range(len(img_points)):
                # 使用 solvePnP 直接计算外参
                # 它会利用畸变系数 D 在内部处理畸变，不需要手动去畸变
                success, rvec, tvec = cv2.solvePnP(
                    obj_points[i], 
                    img_points[i], 
                    self.camera_matrix, 
                    self.dist_coeffs
                )
                if success:
                    rvecs.append(rvec)
                    tvecs.append(tvec)
                else:
                    print(f"⚠️ 标准模型第{i+1}张图片solvePnP失败")

        # 首先，将 rvecs 列表转换为 R_cam_target 旋转矩阵列表
        R_cam_target = []
        for rvec in rvecs:
            R, _ = cv2.Rodrigues(rvec)
            R_cam_target.append(R)

        # 其次，机器人位姿部分也需要是旋转矩阵和位移向量分开的列表
        # 你的代码 R_tool, t_tool 已经做好了，这里确认一下
        R_base_flange = R_tool[:len(rvecs)]
        t_base_flange = t_tool[:len(tvecs)]

        # 调用 cv2.calibrateHandEye 进行手眼标定 (方法: TSAI)
        method_tsai = cv2.CALIB_HAND_EYE_TSAI
        # 注意输入参数的名字和内容
        R_flange_cam, t_flange_cam = cv2.calibrateHandEye(
            R_gripper2base=R_base_flange,   # 机器人末端(法兰)到基座的旋转
            t_gripper2base=t_base_flange,   # 机器人末端(法兰)到基座的平移
            R_target2cam=R_cam_target,      # 标定板到相机的旋转
            t_target2cam=tvecs,             # 标定板到相机的平移
            method=method_tsai
        )

        # 最后，返回正确的结果
        return R_flange_cam, t_flange_cam

if __name__ == '__main__':

    EIH = EyeInHand()
    images_path = "data/eye_hand_calibration_image" #手眼标定采集的标定版图片所在路径
    file_path = "data/targets.txt" #采集标定板图片时对应的机械臂末端的位姿 从 第一行到最后一行 需要和采集的标定板的图片顺序进行对应
    corner_point_width = 6      #标定板内角点数量  宽度
    corner_point_height = 5     #标定板内角点数量  高度
    corner_point_size = 0.030        #标定板方格真实尺寸  m
    
    # 测试位姿 - ZYX顺序：[x(mm), y(mm), z(mm), yaw(deg), pitch(deg), roll(deg)]
    pose = [180.03314599646225, 0.0, 140.81726470277647, 
            -1.912, 0.415, -180.0]  # 位置单位：mm，角度单位：度（ZYX顺序）

    print("手眼标定采集的标定版图片所在路径", images_path)
    print("采集标定板图片时对应的机械臂末端的位姿", file_path)
    
    EIH.poses_to_matrix_save_csv(file_path, r"data\robotToolPose.csv")
    rotation_matrix ,translation_vector = EIH.compute_T(images_path, corner_point_width, corner_point_height, corner_point_size)
    print('默认返回tsai方法计算结果,可根据设计情况自行选择合适的矩阵和平移向量 ')
    
    print("////////////////////////////////////////////////////////////////////////////////////////////////")
    print('rotation_matrix:')
    print(rotation_matrix)
    print('translation_vector:')
    print(translation_vector)
    
    print("////////////////////////////////////////////////////////////////////////////////////////////////")
    RT_camera2end = np.eye(4)
    RT_camera2end[0:3,0:3] = rotation_matrix
    RT_camera2end[0:3,3] = translation_vector.reshape(3)
    print('RT_camera2end:')
    print(RT_camera2end)
    print("////////////////////////////////////////////////////////////////////////////////////////////////")
    
    u, v = 280, 264
    Z = 0.24  # 假设已知的深度值，单位为米
    fx, fy, cx, cy = 334.74708104,447.86175651, 308.83371984,  230.12967209
    # 图像坐标转换为相机坐标
    X = (u - cx) * Z / fx
    Y = (v - cy) * Z / fy
    # 齐次坐标
    P_camera_homogeneous = np.array([X, Y, Z, 1]).reshape(4, 1)
    print("相机坐标系中的坐标:", P_camera_homogeneous)    
    print("////////////////////////////////////////////////////////////////////////////////////////////////")
    
    RT_end2base = EIH.pose_to_homogeneous_matrix(pose)
    print("机械臂末端坐标系到机械臂基坐标系的变换矩阵:")
    print(RT_end2base)
    print("////////////////////////////////////////////////////////////////////////////////////////////////")
    # 从相机坐标系转换到机械臂末端坐标系
    P_end_homogeneous = RT_camera2end @ P_camera_homogeneous
    print("机械臂末端坐标系中的坐标:", P_end_homogeneous)
    print("////////////////////////////////////////////////////////////////////////////////////////////////")

    # 从机械臂末端坐标系转换到机械臂基底坐标系
    P_base_homogeneous = RT_end2base @ P_end_homogeneous
    x,y,z = P_base_homogeneous[0,0],-P_base_homogeneous[1,0],P_base_homogeneous[2,0]
    print("机械臂基底坐标系中的坐标:", x*1000,y*1000,z*1000)
    print("////////////////////////////////////////////////////////////////////////////////////////////////")

    
    
