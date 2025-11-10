import numpy as np
from typing import List, Tuple, Optional, Union
import math


class QuinticPolynomial:
    """五次多项式类"""
    
    def __init__(self, start_pos: float, start_vel: float, start_acc: float,
                 end_pos: float, end_vel: float, end_acc: float, duration: float):
        """
        初始化五次多项式
        
        Args:
            start_pos: 起始位置
            start_vel: 起始速度
            start_acc: 起始加速度
            end_pos: 结束位置
            end_vel: 结束速度
            end_acc: 结束加速度
            duration: 运动时间
        """
        self.duration = duration
        self.coefficients = self._calculate_coefficients(
            start_pos, start_vel, start_acc, end_pos, end_vel, end_acc, duration
        )
    
    def _calculate_coefficients(self, p0: float, v0: float, a0: float,
                              p1: float, v1: float, a1: float, T: float) -> np.ndarray:
        """计算五次多项式系数"""
        # 构建约束方程矩阵
        # q(t) = a0 + a1*t + a2*t^2 + a3*t^3 + a4*t^4 + a5*t^5
        # q'(t) = a1 + 2*a2*t + 3*a3*t^2 + 4*a4*t^3 + 5*a5*t^4
        # q''(t) = 2*a2 + 6*a3*t + 12*a4*t^2 + 20*a5*t^3
        
        A = np.array([
            [1, 0, 0, 0, 0, 0],           # q(0) = p0
            [0, 1, 0, 0, 0, 0],           # q'(0) = v0
            [0, 0, 2, 0, 0, 0],           # q''(0) = a0
            [1, T, T**2, T**3, T**4, T**5],        # q(T) = p1
            [0, 1, 2*T, 3*T**2, 4*T**3, 5*T**4],   # q'(T) = v1
            [0, 0, 2, 6*T, 12*T**2, 20*T**3]       # q''(T) = a1
        ])
        
        b = np.array([p0, v0, a0, p1, v1, a1])
        
        return np.linalg.solve(A, b)
    
    def position(self, t: float) -> float:
        """计算t时刻的位置"""
        if t < 0:
            t = 0
        elif t > self.duration:
            t = self.duration
        
        return (self.coefficients[0] + 
                self.coefficients[1] * t +
                self.coefficients[2] * t**2 +
                self.coefficients[3] * t**3 +
                self.coefficients[4] * t**4 +
                self.coefficients[5] * t**5)
    
    def velocity(self, t: float) -> float:
        """计算t时刻的速度"""
        if t < 0:
            t = 0
        elif t > self.duration:
            t = self.duration
        
        return (self.coefficients[1] +
                2 * self.coefficients[2] * t +
                3 * self.coefficients[3] * t**2 +
                4 * self.coefficients[4] * t**3 +
                5 * self.coefficients[5] * t**4)
    
    def acceleration(self, t: float) -> float:
        """计算t时刻的加速度"""
        if t < 0:
            t = 0
        elif t > self.duration:
            t = self.duration
        
        return (2 * self.coefficients[2] +
                6 * self.coefficients[3] * t +
                12 * self.coefficients[4] * t**2 +
                20 * self.coefficients[5] * t**3)


class JointSpaceInterpolator:
    """关节空间插补器"""
    
    def __init__(self):
        self.polynomials = []
        self.duration = 0.0
    
    def plan_trajectory(self, waypoints: List[np.ndarray], 
                       velocities: Optional[List[np.ndarray]] = None,
                       accelerations: Optional[List[np.ndarray]] = None,
                       durations: Optional[List[float]] = None,
                       max_velocity: Optional[np.ndarray] = None,
                       max_acceleration: Optional[np.ndarray] = None) -> bool:
        """
        规划关节空间轨迹
        
        Args:
            waypoints: 路径点列表，每个点是关节角度数组
            velocities: 每个路径点的速度（可选）
            accelerations: 每个路径点的加速度（可选）
            durations: 每段的时间（可选）
            max_velocity: 最大速度限制 
            max_acceleration: 最大加速度限制
        
        Returns:
            规划是否成功
        """
        if len(waypoints) < 2:
            print("至少需要两个路径点")
            return False
        
        num_segments = len(waypoints) - 1
        num_joints = len(waypoints[0])
        
        # 如果没有指定速度和加速度，设置为零
        if velocities is None:
            velocities = [np.zeros(num_joints) for _ in waypoints]
        if accelerations is None:
            accelerations = [np.zeros(num_joints) for _ in waypoints]
        
        # 如果没有指定时间，自动计算
        if durations is None:
            durations = self._calculate_durations(waypoints, max_velocity, max_acceleration)
        
        # 为每个关节的每段创建五次多项式
        self.polynomials = []
        for segment in range(num_segments):
            segment_polynomials = []
            segment_duration = durations[segment]
            
            for joint in range(num_joints):
                poly = QuinticPolynomial(
                    start_pos=waypoints[segment][joint],
                    start_vel=velocities[segment][joint],
                    start_acc=accelerations[segment][joint],
                    end_pos=waypoints[segment + 1][joint],
                    end_vel=velocities[segment + 1][joint],
                    end_acc=accelerations[segment + 1][joint],
                    duration=segment_duration
                )
                segment_polynomials.append(poly)
            
            self.polynomials.append(segment_polynomials)
        
        self.duration = sum(durations)
        self.segment_durations = durations
        return True
    
    def _calculate_durations(self, waypoints: List[np.ndarray],
                           max_velocity: Optional[np.ndarray],
                           max_acceleration: Optional[np.ndarray]) -> List[float]:
        """自动计算各段运动时间"""
        durations = []
        
        for i in range(len(waypoints) - 1):
            displacement = np.abs(waypoints[i + 1] - waypoints[i])
            
            if max_velocity is not None:
                # 基于最大速度估算时间
                time_based_on_vel = np.max(displacement / max_velocity)
            else:
                time_based_on_vel = 1.0
            
            if max_acceleration is not None:
                # 基于最大加速度估算时间
                time_based_on_acc = np.max(np.sqrt(2 * displacement / max_acceleration))
            else:
                time_based_on_acc = 1.0
            
            # 取较大的时间作为该段的时间，减小最小时间限制
            min_duration = 0.1  # 最少0.1秒，允许更快的运动
            duration = max(time_based_on_vel, time_based_on_acc, min_duration)
            durations.append(duration)
            
        
        return durations
    
    def get_joint_states(self, t: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        获取t时刻的关节状态
        
        Args:
            t: 时间
            
        Returns:
            (位置, 速度, 加速度)
        """
        if not self.polynomials:
            raise ValueError("请先规划轨迹")
        
        # 确定当前时间属于哪个段
        segment_idx, local_time = self._get_segment_and_time(t)
        
        if segment_idx >= len(self.polynomials):
            segment_idx = len(self.polynomials) - 1
            local_time = self.segment_durations[segment_idx]
        
        segment_polys = self.polynomials[segment_idx]
        num_joints = len(segment_polys)
        
        positions = np.zeros(num_joints)
        velocities = np.zeros(num_joints)
        accelerations = np.zeros(num_joints)
        
        for joint in range(num_joints):
            poly = segment_polys[joint]
            positions[joint] = poly.position(local_time)
            velocities[joint] = poly.velocity(local_time)
            accelerations[joint] = poly.acceleration(local_time)
        
        return positions, velocities, accelerations
    
    def _get_segment_and_time(self, t: float) -> Tuple[int, float]:
        """获取时间t对应的段索引和局部时间"""
        if t <= 0:
            return 0, 0.0
        
        cumulative_time = 0.0
        for i, duration in enumerate(self.segment_durations):
            if t <= cumulative_time + duration:
                return i, t - cumulative_time
            cumulative_time += duration
        
        # 超出总时间，返回最后一段的结束时间
        return len(self.segment_durations) - 1, self.segment_durations[-1]


class CartesianSpaceInterpolator:
    """笛卡尔空间插补器"""
    
    def __init__(self):
        self.position_polynomials = []  # 位置插补多项式
        self.orientation_polynomials = []  # 姿态插补多项式
        self.duration = 0.0
    
    def plan_trajectory(self, waypoints: List[Tuple[np.ndarray, np.ndarray]],
                       velocities: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None,
                       accelerations: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None,
                       durations: Optional[List[float]] = None,
                       max_linear_velocity: float = 0.5,
                       max_angular_velocity: float = 1.0,
                       max_linear_acceleration: float = 1.0,
                       max_angular_acceleration: float = 2.0) -> bool:
        """
        规划笛卡尔空间轨迹
        
        Args:
            waypoints: 路径点列表，每个点是(位置[x,y,z], 欧拉角[rx,ry,rz])
            velocities: 每个路径点的速度（线速度，角速度）
            accelerations: 每个路径点的加速度
            durations: 每段的时间
            max_linear_velocity: 最大线速度
            max_angular_velocity: 最大角速度
            max_linear_acceleration: 最大线加速度
            max_angular_acceleration: 最大角加速度
        
        Returns:
            规划是否成功
        """
        if len(waypoints) < 2:
            print("至少需要两个路径点")
            return False
        
        num_segments = len(waypoints) - 1
        
        # 分离位置和姿态
        positions = [wp[0] for wp in waypoints]
        orientations = [wp[1] for wp in waypoints]
        
        # 设置默认速度和加速度
        if velocities is None:
            velocities = [(np.zeros(3), np.zeros(3)) for _ in waypoints]
        if accelerations is None:
            accelerations = [(np.zeros(3), np.zeros(3)) for _ in waypoints]
        
        # 自动计算时间
        if durations is None:
            durations = self._calculate_durations(
                positions, orientations, 
                max_linear_velocity, max_angular_velocity,
                max_linear_acceleration, max_angular_acceleration
            )
        
        # 为位置创建多项式
        self.position_polynomials = []
        for segment in range(num_segments):
            segment_polynomials = []
            segment_duration = durations[segment]
            
            for axis in range(3):  # x, y, z
                poly = QuinticPolynomial(
                    start_pos=positions[segment][axis],
                    start_vel=velocities[segment][0][axis],
                    start_acc=accelerations[segment][0][axis],
                    end_pos=positions[segment + 1][axis],
                    end_vel=velocities[segment + 1][0][axis],
                    end_acc=accelerations[segment + 1][0][axis],
                    duration=segment_duration
                )
                segment_polynomials.append(poly)
            
            self.position_polynomials.append(segment_polynomials)
        
        # 为姿态创建多项式
        self.orientation_polynomials = []
        for segment in range(num_segments):
            segment_polynomials = []
            segment_duration = durations[segment]
            
            for axis in range(3):  # rx, ry, rz
                poly = QuinticPolynomial(
                    start_pos=orientations[segment][axis],
                    start_vel=velocities[segment][1][axis],
                    start_acc=accelerations[segment][1][axis],
                    end_pos=orientations[segment + 1][axis],
                    end_vel=velocities[segment + 1][1][axis],
                    end_acc=accelerations[segment + 1][1][axis],
                    duration=segment_duration
                )
                segment_polynomials.append(poly)
            
            self.orientation_polynomials.append(segment_polynomials)
        
        self.duration = sum(durations)
        self.segment_durations = durations
        return True
    
    def _calculate_durations(self, positions: List[np.ndarray], 
                           orientations: List[np.ndarray],
                           max_linear_vel: float, max_angular_vel: float,
                           max_linear_acc: float, max_angular_acc: float) -> List[float]:
        """自动计算各段运动时间"""
        durations = []
        
        for i in range(len(positions) - 1):
            # 计算位置变化
            linear_displacement = np.linalg.norm(positions[i + 1] - positions[i])
            angular_displacement = np.linalg.norm(orientations[i + 1] - orientations[i])
            
            # 基于速度限制计算时间
            time_linear_vel = linear_displacement / max_linear_vel
            time_angular_vel = angular_displacement / max_angular_vel
            
            # 基于加速度限制计算时间
            time_linear_acc = math.sqrt(2 * linear_displacement / max_linear_acc)
            time_angular_acc = math.sqrt(2 * angular_displacement / max_angular_acc)
            
            # 取最大值作为该段时间
            duration = max(time_linear_vel, time_angular_vel, 
                          time_linear_acc, time_angular_acc, 0.5)
            durations.append(duration)
        
        return durations
    
    def get_cartesian_states(self, t: float) -> Tuple[np.ndarray, np.ndarray, 
                                                    np.ndarray, np.ndarray,
                                                    np.ndarray, np.ndarray]:
        """
        获取t时刻的笛卡尔状态
        
        Args:
            t: 时间
            
        Returns:
            (位置, 姿态, 线速度, 角速度, 线加速度, 角加速度)
        """
        if not self.position_polynomials or not self.orientation_polynomials:
            raise ValueError("请先规划轨迹")
        
        # 确定当前时间属于哪个段
        segment_idx, local_time = self._get_segment_and_time(t)
        
        if segment_idx >= len(self.position_polynomials):
            segment_idx = len(self.position_polynomials) - 1
            local_time = self.segment_durations[segment_idx]
        
        # 获取位置状态
        pos_polys = self.position_polynomials[segment_idx]
        position = np.zeros(3)
        linear_velocity = np.zeros(3)
        linear_acceleration = np.zeros(3)
        
        for axis in range(3):
            poly = pos_polys[axis]
            position[axis] = poly.position(local_time)
            linear_velocity[axis] = poly.velocity(local_time)
            linear_acceleration[axis] = poly.acceleration(local_time)
        
        # 获取姿态状态
        orient_polys = self.orientation_polynomials[segment_idx]
        orientation = np.zeros(3)
        angular_velocity = np.zeros(3)
        angular_acceleration = np.zeros(3)
        
        for axis in range(3):
            poly = orient_polys[axis]
            orientation[axis] = poly.position(local_time)
            angular_velocity[axis] = poly.velocity(local_time)
            angular_acceleration[axis] = poly.acceleration(local_time)
        
        return (position, orientation, 
                linear_velocity, angular_velocity,
                linear_acceleration, angular_acceleration)
    
    def _get_segment_and_time(self, t: float) -> Tuple[int, float]:
        """获取时间t对应的段索引和局部时间"""
        if t <= 0:
            return 0, 0.0
        
        cumulative_time = 0.0
        for i, duration in enumerate(self.segment_durations):
            if t <= cumulative_time + duration:
                return i, t - cumulative_time
            cumulative_time += duration
        
        # 超出总时间，返回最后一段的结束时间
        return len(self.segment_durations) - 1, self.segment_durations[-1]
    
    def sample_trajectory(self, sample_rate: float = 100.0) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        采样轨迹点
        
        Args:
            sample_rate: 采样频率 (Hz)
            
        Returns:
            采样点列表，每个点是(位置, 姿态)
        """
        if not self.position_polynomials:
            return []
        
        dt = 1.0 / sample_rate
        samples = []
        
        t = 0.0
        while t <= self.duration:
            pos, orient, _, _, _, _ = self.get_cartesian_states(t)
            samples.append((pos, orient))
            t += dt
        
        return samples


class TrajectoryBlender:
    """轨迹混合器 - 用于平滑连接多段轨迹"""
    
    @staticmethod
    def blend_joint_trajectories(traj1: JointSpaceInterpolator, 
                               traj2: JointSpaceInterpolator,
                               blend_time: float = 0.1) -> JointSpaceInterpolator:
        """
        混合两个关节空间轨迹
        
        Args:
            traj1: 第一段轨迹
            traj2: 第二段轨迹  
            blend_time: 混合时间
            
        Returns:
            混合后的轨迹
        """
        # 这里可以实现轨迹混合逻辑
        # 简化实现：直接返回第一个轨迹
        return traj1
    
    @staticmethod
    def optimize_trajectory(interpolator: Union[JointSpaceInterpolator, CartesianSpaceInterpolator],
                          optimization_type: str = "time") -> bool:
        """
        优化轨迹
        
        Args:
            interpolator: 插补器
            optimization_type: 优化类型 ("time", "energy", "jerk")
            
        Returns:
            优化是否成功
        """
        # 这里可以实现轨迹优化算法
        # 例如时间最优、能量最优、平滑度优化等
        print(f"执行{optimization_type}优化...")
        return True


class CircularInterpolator:
    """圆弧插补器"""
    
    def __init__(self):
        self.arc_center = None
        self.arc_radius = 0.0
        self.start_angle = 0.0
        self.end_angle = 0.0
        self.arc_plane_normal = None
        self.arc_plane_x_axis = None
        self.arc_plane_y_axis = None
        self.duration = 0.0
        self.start_position = None
        self.end_position = None
        self.velocity_polynomial = None
        
    def plan_arc_by_three_points(self, start_point: np.ndarray, 
                                 middle_point: np.ndarray, 
                                 end_point: np.ndarray,
                                 max_velocity: float = 50.0,  # mm/s
                                 max_acceleration: float = 100.0) -> bool:
        """
        通过三点定义圆弧并规划插补轨迹
        
        Args:
            start_point: 起点 [x, y, z]
            middle_point: 中间点 [x, y, z] 
            end_point: 终点 [x, y, z]
            max_velocity: 最大线速度 (mm/s)
            max_acceleration: 最大线加速度 (mm/s²)
            
        Returns:
            规划是否成功
        """
        try:
            # 计算圆弧参数
            success = self._calculate_arc_from_three_points(start_point, middle_point, end_point)
            if not success:
                return False
            
            # 计算圆弧长度
            arc_length = self._calculate_arc_length()
            
            # 计算运动时间
            self.duration = self._calculate_arc_duration(arc_length, max_velocity, max_acceleration)
            
            # 创建速度分布多项式（梯形速度曲线）
            self._create_velocity_profile(arc_length, max_velocity, max_acceleration)
            
            print(f"✅ 圆弧插补规划成功:")
            print(f"   圆心: [{self.arc_center[0]:.1f}, {self.arc_center[1]:.1f}, {self.arc_center[2]:.1f}]")
            print(f"   半径: {self.arc_radius:.1f}mm")
            print(f"   圆弧长度: {arc_length:.1f}mm")
            print(f"   运动时间: {self.duration:.2f}s")
            
            return True
            
        except Exception as e:
            print(f"❌ 圆弧插补规划失败: {e}")
            return False
    
    def plan_arc_by_center(self, start_point: np.ndarray,
                          end_point: np.ndarray,
                          center_point: np.ndarray,
                          plane_normal: np.ndarray = None,
                          clockwise: bool = False,
                          max_velocity: float = 50.0,
                          max_acceleration: float = 100.0) -> bool:
        """
        通过起点、终点和圆心定义圆弧
        
        Args:
            start_point: 起点 [x, y, z]
            end_point: 终点 [x, y, z]
            center_point: 圆心 [x, y, z]
            plane_normal: 平面法向量 [x, y, z]（可选）
            clockwise: 是否顺时针方向
            max_velocity: 最大线速度 (mm/s)
            max_acceleration: 最大线加速度 (mm/s²)
            
        Returns:
            规划是否成功
        """
        try:
            # 设置圆弧参数
            self.arc_center = np.array(center_point)
            self.start_position = np.array(start_point)
            self.end_position = np.array(end_point)
            
            # 计算半径
            radius1 = np.linalg.norm(start_point - center_point)
            radius2 = np.linalg.norm(end_point - center_point)
            
            if abs(radius1 - radius2) > 0.1:  # 允许0.1mm误差
                print(f"❌ 起点和终点到圆心的距离不相等: {radius1:.2f} vs {radius2:.2f}")
                return False
            
            self.arc_radius = (radius1 + radius2) / 2
            
            # 建立坐标系
            success = self._setup_arc_coordinate_system(plane_normal)
            if not success:
                return False
            
            # 计算角度
            self._calculate_arc_angles(clockwise)
            
            # 计算圆弧长度和时间
            arc_length = self._calculate_arc_length()
            self.duration = self._calculate_arc_duration(arc_length, max_velocity, max_acceleration)
            
            # 创建速度分布
            self._create_velocity_profile(arc_length, max_velocity, max_acceleration)
            
            print(f"✅ 圆弧插补规划成功:")
            print(f"   圆心: [{self.arc_center[0]:.1f}, {self.arc_center[1]:.1f}, {self.arc_center[2]:.1f}]")
            print(f"   半径: {self.arc_radius:.1f}mm")
            print(f"   角度范围: {np.rad2deg(self.start_angle):.1f}° → {np.rad2deg(self.end_angle):.1f}°")
            print(f"   圆弧长度: {arc_length:.1f}mm")
            print(f"   运动时间: {self.duration:.2f}s")
            
            return True
            
        except Exception as e:
            print(f"❌ 圆弧插补规划失败: {e}")
            return False
    
    def _calculate_arc_from_three_points(self, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> bool:
        """通过三点计算圆弧参数"""
        p1, p2, p3 = np.array(p1), np.array(p2), np.array(p3)
        
        # 检查三点是否共线
        v1 = p2 - p1
        v2 = p3 - p1
        cross = np.cross(v1, v2)
        
        if np.linalg.norm(cross) < 1e-6:
            print("❌ 三点共线，无法定义圆弧")
            return False
        
        # 计算圆心（使用三点的垂直平分线交点）
        # 使用解析几何方法计算圆心
        self.arc_center = self._calculate_circumcenter(p1, p2, p3)
        
        # 计算半径
        self.arc_radius = np.linalg.norm(p1 - self.arc_center)
        
        # 存储起点和终点
        self.start_position = p1
        self.end_position = p3
        
        # 建立坐标系（平面法向量为两向量的叉积）
        self.arc_plane_normal = cross / np.linalg.norm(cross)
        
        # 建立局部坐标系
        self._setup_arc_coordinate_system()
        
        # 计算角度
        self._calculate_arc_angles()
        
        return True
    
    def _calculate_circumcenter(self, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> np.ndarray:
        """计算三点的外心（圆心）"""
        # 使用向量方法计算外心
        a = np.linalg.norm(p2 - p3)
        b = np.linalg.norm(p3 - p1)  
        c = np.linalg.norm(p1 - p2)
        
        # 计算重心坐标
        A = np.linalg.norm(p2 - p3)**2 * (np.dot(p1 - p2, p1 - p3))
        B = np.linalg.norm(p3 - p1)**2 * (np.dot(p2 - p3, p2 - p1))
        C = np.linalg.norm(p1 - p2)**2 * (np.dot(p3 - p1, p3 - p2))
        
        if abs(A + B + C) < 1e-10:
            # 使用另一种方法
            return self._calculate_circumcenter_alternative(p1, p2, p3)
        
        circumcenter = (A * p1 + B * p2 + C * p3) / (A + B + C)
        return circumcenter
    
    def _calculate_circumcenter_alternative(self, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> np.ndarray:
        """使用替代方法计算外心"""
        # 使用向量和行列式的方法
        ax, ay, az = p1
        bx, by, bz = p2
        cx, cy, cz = p3
        
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        
        if abs(d) < 1e-10:
            # 如果还是接近零，返回质心
            return (p1 + p2 + p3) / 3
        
        ux = ((ax**2 + ay**2 + az**2) * (by - cy) + 
              (bx**2 + by**2 + bz**2) * (cy - ay) + 
              (cx**2 + cy**2 + cz**2) * (ay - by)) / d
        
        uy = ((ax**2 + ay**2 + az**2) * (cx - bx) + 
              (bx**2 + by**2 + bz**2) * (ax - cx) + 
              (cx**2 + cy**2 + cz**2) * (bx - ax)) / d
        
        # 对于z坐标，使用平面约束
        # 假设圆弧在xy平面的投影，z取平均值
        uz = (az + bz + cz) / 3
        
        return np.array([ux, uy, uz])
    
    def _setup_arc_coordinate_system(self, given_normal: np.ndarray = None):
        """建立圆弧坐标系"""
        if given_normal is not None:
            self.arc_plane_normal = np.array(given_normal) / np.linalg.norm(given_normal)
        elif self.arc_plane_normal is None:
            # 默认使用z轴作为法向量
            self.arc_plane_normal = np.array([0, 0, 1])
        
        # 建立x轴（从圆心指向起点）
        to_start = self.start_position - self.arc_center
        self.arc_plane_x_axis = to_start / np.linalg.norm(to_start)
        
        # 建立y轴（叉积）
        self.arc_plane_y_axis = np.cross(self.arc_plane_normal, self.arc_plane_x_axis)
        self.arc_plane_y_axis = self.arc_plane_y_axis / np.linalg.norm(self.arc_plane_y_axis)
        
        return True
    
    def _calculate_arc_angles(self, clockwise: bool = False):
        """计算圆弧的起始和结束角度"""
        # 将起点和终点投影到圆弧平面坐标系
        to_start = self.start_position - self.arc_center
        to_end = self.end_position - self.arc_center
        
        # 计算角度
        start_x = np.dot(to_start, self.arc_plane_x_axis)
        start_y = np.dot(to_start, self.arc_plane_y_axis)
        self.start_angle = np.arctan2(start_y, start_x)
        
        end_x = np.dot(to_end, self.arc_plane_x_axis)
        end_y = np.dot(to_end, self.arc_plane_y_axis)
        self.end_angle = np.arctan2(end_y, end_x)
        
        # 处理角度跨越
        if not clockwise:
            # 逆时针方向
            if self.end_angle < self.start_angle:
                self.end_angle += 2 * np.pi
        else:
            # 顺时针方向
            if self.end_angle > self.start_angle:
                self.end_angle -= 2 * np.pi
    
    def _calculate_arc_length(self) -> float:
        """计算圆弧长度"""
        angle_diff = abs(self.end_angle - self.start_angle)
        return self.arc_radius * angle_diff
    
    def _calculate_arc_duration(self, arc_length: float, max_velocity: float, max_acceleration: float) -> float:
        """计算圆弧运动时间"""
        # 使用梯形速度曲线估算时间
        t_acc = max_velocity / max_acceleration  # 加速时间
        s_acc = 0.5 * max_acceleration * t_acc**2  # 加速距离
        
        if 2 * s_acc >= arc_length:
            # 三角形速度曲线（无匀速段）
            return 2 * np.sqrt(arc_length / max_acceleration)
        else:
            # 梯形速度曲线
            s_const = arc_length - 2 * s_acc  # 匀速距离
            t_const = s_const / max_velocity  # 匀速时间
            return 2 * t_acc + t_const
    
    def _create_velocity_profile(self, arc_length: float, max_velocity: float, max_acceleration: float):
        """创建速度分布曲线"""
        # 简化版本：使用五次多项式创建平滑的速度分布
        self.velocity_polynomial = QuinticPolynomial(
            start_pos=0.0,      # 起始位置参数
            start_vel=0.0,      # 起始速度
            start_acc=0.0,      # 起始加速度
            end_pos=arc_length, # 结束位置参数
            end_vel=0.0,        # 结束速度
            end_acc=0.0,        # 结束加速度
            duration=self.duration
        )
    
    def get_arc_position(self, t: float) -> np.ndarray:
        """
        获取t时刻圆弧上的位置
        
        Args:
            t: 时间
            
        Returns:
            位置坐标 [x, y, z]
        """
        if not self.velocity_polynomial:
            raise ValueError("请先规划圆弧轨迹")
        
        # 限制时间范围
        t = max(0, min(t, self.duration))
        
        # 获取弧长参数
        arc_position = self.velocity_polynomial.position(t)
        arc_length = self._calculate_arc_length()
        
        # 计算当前角度
        if arc_length > 0:
            angle_ratio = arc_position / arc_length
        else:
            angle_ratio = 0
        
        current_angle = self.start_angle + angle_ratio * (self.end_angle - self.start_angle)
        
        # 计算在局部坐标系中的位置
        local_x = self.arc_radius * np.cos(current_angle)
        local_y = self.arc_radius * np.sin(current_angle)
        
        # 转换到全局坐标系
        global_position = (self.arc_center + 
                          local_x * self.arc_plane_x_axis + 
                          local_y * self.arc_plane_y_axis)
        
        return global_position
    
    def get_arc_velocity(self, t: float) -> np.ndarray:
        """获取t时刻的速度向量"""
        if not self.velocity_polynomial:
            raise ValueError("请先规划圆弧轨迹")
        
        t = max(0, min(t, self.duration))
        
        # 获取弧长速度
        arc_velocity = self.velocity_polynomial.velocity(t)
        arc_length = self._calculate_arc_length()
        
        if arc_length > 0:
            # 计算角速度
            angular_velocity = arc_velocity / self.arc_radius
            
            # 计算当前角度
            arc_position = self.velocity_polynomial.position(t)
            angle_ratio = arc_position / arc_length
            current_angle = self.start_angle + angle_ratio * (self.end_angle - self.start_angle)
            
            # 计算切向速度方向
            tangent_direction = (-np.sin(current_angle) * self.arc_plane_x_axis + 
                               np.cos(current_angle) * self.arc_plane_y_axis)
            
            # 速度矢量
            velocity_vector = arc_velocity * tangent_direction / np.linalg.norm(tangent_direction)
            
            return velocity_vector
        else:
            return np.zeros(3)
    
    def sample_arc_trajectory(self, sample_rate: float = 100.0) -> List[np.ndarray]:
        """
        采样圆弧轨迹
        
        Args:
            sample_rate: 采样频率 (Hz)
            
        Returns:
            位置点列表
        """
        if not self.velocity_polynomial:
            raise ValueError("请先规划圆弧轨迹")
        
        dt = 1.0 / sample_rate
        samples = []
        
        t = 0.0
        while t <= self.duration:
            position = self.get_arc_position(t)
            samples.append(position)
            t += dt
        
        return samples 