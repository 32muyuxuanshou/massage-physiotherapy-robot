from scipy.spatial.transform import Rotation as R
import numpy as np


def dh_to_matrix(alpha, theta, a, d):
    """
    根据DH参数生成齐次变换矩阵。
    Args:
        alpha (float): 前一关节的轴与当前关节轴的夹角 (以弧度表示)。
        theta (float): 当前关节的转角 (以弧度表示)。
        a (float): 两关节之间的连杆长度。
        d (float): 当前关节的偏移量。
    Returns:
        np.ndarray: 4x4 齐次变换矩阵。
    """
    # 构建齐次变换矩阵
    matrix = np.array([
        [np.cos(theta), -np.sin(theta), 0, a],
        [np.sin(theta) * np.cos(alpha), np.cos(theta) * np.cos(alpha), -np.sin(alpha), -d * np.sin(alpha)],
        [np.sin(theta) * np.sin(alpha), np.cos(theta) * np.sin(alpha), np.cos(alpha), d * np.cos(alpha)],
        [0, 0, 0, 1]
    ])
    #print(np.cos(alpha),np.sin(theta))
    return matrix

def matrix_to_quaternion(matrix):
    """
    将齐次变换矩阵转换为四元数和平移向量。
    
    Args:
        matrix (np.ndarray): 4x4 齐次变换矩阵。
    
    Returns:
        tuple: 四元数 (q_w, q_x, q_y, q_z) 和平移向量 [x, y, z]。
    """
    # 提取旋转矩阵部分
    rotation_matrix = matrix[:3, :3]
    # 提取平移向量部分
    translation = matrix[:3, 3]
    # 使用 scipy 计算四元数
    quaternion = R.from_matrix(rotation_matrix).as_quat()  # 返回 [q_x, q_y, q_z, q_w]
    return quaternion, translation

def quaternion_to_matrix(quaternion, translation):
    """
    将四元数和平移向量转换为齐次变换矩阵。
    
    Args:
        quaternion (list or np.ndarray): 四元数 [q_x, q_y, q_z, q_w]。
        translation (list or np.ndarray): 平移向量 [x, y, z]。
    Returns:
        np.ndarray: 4x4 齐次变换矩阵。
    """
    # 使用 scipy 计算旋转矩阵
    rotation_matrix = R.from_quat(quaternion).as_matrix()  # 从四元数生成旋转矩阵
    # 构造齐次矩阵
    matrix = np.eye(4)
    matrix[:3, :3] = rotation_matrix
    matrix[:3, 3] = translation
    return matrix

def compute_orientation_error(current_rotation, target_rotation):
    """
    计算姿态误差 (基于旋转矩阵的李代数表示)
    :param current_rotation: 当前末端旋转矩阵 (3x3)
    :param target_rotation: 目标末端旋转矩阵 (3x3)
    :return: 姿态误差向量 (3x1)
    """
    # 旋转误差矩阵
    R_error = target_rotation @ current_rotation.T
    # 提取李代数的反对称分量，得到旋转向量
    orientation_error = 0.5 * np.array([
            R_error[2, 1] - R_error[1, 2],
            R_error[0, 2] - R_error[2, 0],
            R_error[1, 0] - R_error[0, 1]
    ])
    return orientation_error

def normalize_angle(angle):
    """
    将角度规范化为 -pi 到 pi 范围内，支持标量、列表和 NumPy 数组输入。
    :param angle: 输入角度，支持标量(float/int)、列表、NumPy 数组
    :return: 规范化后的角度，格式与输入保持一致
    """
    # 如果是列表或数组，先转换为 NumPy 数组进行处理
    if isinstance(angle, (list, np.ndarray)):
        angle = np.array(angle)
        angle = np.fmod(angle, 2 * np.pi)  # 归一化到 [-2*pi, 2*pi]
        angle[angle > np.pi] -= 2 * np.pi  # 超过 pi 的角度减去 2*pi
        angle[angle < -np.pi] += 2 * np.pi  # 小于 -pi 的角度加上 2*pi
        return angle.tolist() if isinstance(angle, list) else angle
    else:
        # 单个标量处理
        angle = np.fmod(angle, 2 * np.pi)
        if angle > np.pi:
            angle -= 2 * np.pi
        elif angle < -np.pi:
            angle += 2 * np.pi
    return angle

import time

if __name__ == "__main__":
    print('test')