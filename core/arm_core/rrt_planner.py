import numpy as np
import random
import math
from typing import List, Tuple, Optional


class RRTNode:
    """RRT节点类"""
    def __init__(self, config: np.ndarray, parent=None):
        self.config = config  # 关节配置
        self.parent = parent  # 父节点
        self.children = []    # 子节点列表
        self.cost = 0.0      # 从起点到该节点的代价


class RRTPlanner:
    """快速随机探索树(RRT)路径规划算法"""
    
    def __init__(self, joint_limits: List[Tuple[float, float]], 
                 step_size: float = 0.1, max_iter: int = 5000):
        """
        初始化RRT规划器
        
        Args:
            joint_limits: 关节限制，每个关节的(min, max)范围
            step_size: 步长
            max_iter: 最大迭代次数
        """
        self.joint_limits = joint_limits
        self.step_size = step_size
        self.max_iter = max_iter
        self.dof = len(joint_limits)  # 自由度
        self.tree = []  # RRT树
        
    def sample_random_config(self) -> np.ndarray:
        """随机采样关节配置"""
        config = np.zeros(self.dof)
        for i in range(self.dof):
            min_val, max_val = self.joint_limits[i]
            config[i] = random.uniform(min_val, max_val)
        return config
    
    def find_nearest_node(self, config: np.ndarray) -> RRTNode:
        """找到最近的节点"""
        min_dist = float('inf')
        nearest_node = None
        
        for node in self.tree:
            dist = np.linalg.norm(node.config - config)
            if dist < min_dist:
                min_dist = dist
                nearest_node = node
                
        return nearest_node
    
    def steer(self, from_config: np.ndarray, to_config: np.ndarray) -> np.ndarray:
        """从from_config向to_config方向移动step_size距离"""
        direction = to_config - from_config
        distance = np.linalg.norm(direction)
        
        if distance <= self.step_size:
            return to_config
        else:
            unit_direction = direction / distance
            return from_config + self.step_size * unit_direction
    
    def is_valid_config(self, config: np.ndarray) -> bool:
        """检查配置是否有效（在关节限制内）"""
        for i in range(self.dof):
            min_val, max_val = self.joint_limits[i]
            if config[i] < min_val or config[i] > max_val:
                return False
        return True
    
    def is_collision_free(self, config: np.ndarray) -> bool:
        """
        碰撞检测（这里只是示例，实际需要结合具体环境）
        可以与MuJoCo环境结合进行碰撞检测
        """
        # 这里可以添加具体的碰撞检测逻辑
        # 例如与环境模型结合检测
        return self.is_valid_config(config)
    
    def is_path_collision_free(self, config1: np.ndarray, config2: np.ndarray, 
                              resolution: int = 10) -> bool:
        """检查两个配置之间的路径是否无碰撞"""
        for i in range(resolution + 1):
            t = i / resolution
            intermediate_config = (1 - t) * config1 + t * config2
            if not self.is_collision_free(intermediate_config):
                return False
        return True
    
    def is_goal_reached(self, config: np.ndarray, goal_config: np.ndarray, 
                       tolerance: float = 0.05) -> bool:
        """检查是否到达目标"""
        return np.linalg.norm(config - goal_config) < tolerance
    
    def plan(self, start_config: np.ndarray, goal_config: np.ndarray) -> Optional[List[np.ndarray]]:
        """
        RRT路径规划
        
        Args:
            start_config: 起始关节配置
            goal_config: 目标关节配置
            
        Returns:
            路径列表，如果规划失败返回None
        """
        # 初始化树
        self.tree = []
        start_node = RRTNode(start_config)
        self.tree.append(start_node)
        
        for iteration in range(self.max_iter):
            # 以一定概率采样目标点，否则随机采样
            if random.random() < 0.1:  # 10%概率采样目标
                random_config = goal_config
            else:
                random_config = self.sample_random_config()
            
            # 找到最近节点
            nearest_node = self.find_nearest_node(random_config)
            
            # 向随机点方向扩展
            new_config = self.steer(nearest_node.config, random_config)
            
            # 检查新配置是否有效且路径无碰撞
            if (self.is_valid_config(new_config) and 
                self.is_path_collision_free(nearest_node.config, new_config)):
                
                # 创建新节点并添加到树中
                new_node = RRTNode(new_config, nearest_node)
                new_node.cost = nearest_node.cost + np.linalg.norm(new_config - nearest_node.config)
                nearest_node.children.append(new_node)
                self.tree.append(new_node)
                
                # 检查是否到达目标
                if self.is_goal_reached(new_config, goal_config):
                    print(f"RRT规划成功！迭代次数: {iteration + 1}")
                    return self.extract_path(new_node)
        
        print("RRT规划失败：超过最大迭代次数")
        return None
    
    def extract_path(self, goal_node: RRTNode) -> List[np.ndarray]:
        """从目标节点回溯提取路径"""
        path = []
        current_node = goal_node
        
        while current_node is not None:
            path.append(current_node.config.copy())
            current_node = current_node.parent
        
        path.reverse()  # 反转路径，从起点到终点
        return path
    
    def smooth_path(self, path: List[np.ndarray], max_iterations: int = 100) -> List[np.ndarray]:
        """路径平滑优化"""
        if len(path) <= 2:
            return path
        
        smoothed_path = path.copy()
        
        for _ in range(max_iterations):
            if len(smoothed_path) <= 2:
                break
                
            # 随机选择两个不相邻的点
            i = random.randint(0, len(smoothed_path) - 3)
            j = random.randint(i + 2, len(smoothed_path) - 1)
            
            # 检查直线连接是否可行
            if self.is_path_collision_free(smoothed_path[i], smoothed_path[j]):
                # 移除中间的点
                smoothed_path = smoothed_path[:i+1] + smoothed_path[j:]
        
        return smoothed_path
    
    def get_tree_info(self) -> dict:
        """获取树的信息"""
        return {
            'node_count': len(self.tree),
            'max_depth': self._get_max_depth(),
            'total_cost': sum(node.cost for node in self.tree)
        }
    
    def _get_max_depth(self) -> int:
        """获取树的最大深度"""
        if not self.tree:
            return 0
        
        max_depth = 0
        for node in self.tree:
            depth = self._get_node_depth(node)
            max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _get_node_depth(self, node: RRTNode) -> int:
        """获取节点深度"""
        depth = 0
        current = node
        while current.parent is not None:
            depth += 1
            current = current.parent
        return depth 