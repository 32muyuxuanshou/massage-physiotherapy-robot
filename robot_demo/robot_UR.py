import numpy as np
from . import robot_cal_util
import time
class UR_Robot_kinematic:
    def __init__(self, dh_params=None):
        """
        初始化机器人，基于 DH 参数。
        Args:
            dh_params (list of dict): 每个关节的 DH 参数，包含以下键：
                - alpha: 扭转角（弧度）
                - theta: 关节角（弧度）
                - a: 连杆长度
                - d: 连杆偏移
        """
        ## UR类型的机械臂theta的offset一般都为0，所以后面直接进行theta角度的替换了
        ## 其他存在theta offset的机械臂，更新curDH时需要用电机角度+ theta offset
        if not dh_params:
             dh_params = [
            {'alpha': 0,        'theta': 0,       'a': 0,         'd': 0.1519},
            {'alpha': np.pi,  'theta': 0,       'a': 0,         'd': 0.11985},
            {'alpha': -np.pi/2,        'theta': 0,       'a': -0.24365,  'd': -0.09285},
            {'alpha': 0,        'theta': 0,       'a': -0.213,    'd': 0.0834},
            {'alpha': np.pi/2,  'theta': 0,       'a': 0,         'd': 0.0834},
            {'alpha': -np.pi/2, 'theta': 0,       'a': 0,         'd': 0.0824},]
        self.cur_DH = dh_params

    def update_theta(self,theta):
        """
        由于机械臂出现转动更新DH参数中的theta项。
        计算1000次时间为0.001
        args:
            theta:要更新的theta(来源于电机数据的读取)
        Returns:
            None，无需返回，只需要更新好参数
        """
        assert len(self.cur_DH)==len(theta),'The angular length entered does not match the number of robot joints'
        for i in range(len(self.cur_DH)):
            self.cur_DH[i]['theta']=theta[i]
        return None
    
    def close_zero_one(self,value,threshold=1e-10):
        """
        辅助一些对0或者1敏感的函数，减少64位误差带来的影响。
        比如tan和arctan arccos  arcsin
        计算1000次时间为0.001
        args:
            value:要对比的数字
            threshold:要对比阈值，小于1e-10的将被设置为0
        Returns:
            如果是小于阈值的将被设置为0，否则设置为原数字
        """
        if abs(value)<threshold:
            return 0
        if abs(value-1)<threshold:
            return 0
        return value

    def forward_kinematics(self,theta_cal=None):
        """
        计算正向运动学1000次时间为0.14s
        计算正向运动学，返回基座到末端执行器的齐次变换矩阵。
        args:
            theta_cal,需要计算的theta输入，如果没有默认计算机械臂状态的DH参数
            只有当进行虚拟测试时可以输入theta_cal进行测试。
        Returns:
            np.ndarray: 4x4 齐次变换矩阵。
        """
        if not theta_cal is None:
            assert len(self.cur_DH)==len(theta_cal),'The angular length entered does not match the number of robot joints'
        transform = np.eye(4)  # 初始为单位矩阵
        #循环遍历所有关节，计算每个关节的齐次变换相乘，得到末端的齐次坐标
        for i in range(len(self.cur_DH)):
            alpha, a, d = self.cur_DH[i]['alpha'], self.cur_DH[i]['a'], self.cur_DH[i]['d']
            if not theta_cal is None:
                theta=theta_cal[i]
            else:
                theta=self.cur_DH[i]['theta']
            transform = transform @ robot_cal_util.dh_to_matrix(alpha, theta, a, d)
        return transform 

    def find_equivalent_angle(theta):
    # 假设输入 theta 在 -pi/2 到 pi/2 之间
        if theta < -np.pi/2 or theta > np.pi/2:
            raise ValueError("Input angle must be in the range -pi/2 to pi/2")
    
        # 根据符号判断另一个解
        if theta > 0:
            return theta - np.pi
        else:
            return theta + np.pi
        
    def Inverse_Kinematics(self,matrix):
        """
        计算逆向运动学，根据末端的齐次坐标矩阵解算关节角度。
        计算逆向运动学1000次时间为0.37s
        args:
            matrix,末端齐次矩阵。
        Returns:
            thetas: 逆运动学求解出来的6个关节角度。
        """
        nx, ox, ax, px = matrix[0,:4]
        ny, oy, ay, py = matrix[1,:4]
        nz, oz, az, pz = matrix[2,:4]
        d1, d2, d3 = self.cur_DH[0]['d'],self.cur_DH[1]['d'],self.cur_DH[2]['d']
        d4, d5, d6 = self.cur_DH[3]['d'],self.cur_DH[4]['d'],self.cur_DH[5]['d']
        a2,a3=self.cur_DH[2]['a'],self.cur_DH[3]['a']


    #  计算关节一的角度
        m1 = d6 * ax - px 
        n1 = py - d6 * ay
        phi1 = np.arctan2(n1, self.close_zero_one(m1))
        sin_q1_plus_phi = (-d2 - d3 - d4) / np.sqrt(np.power(m1, 2) + np.power(n1, 2))
        cos_q1_plus_phi_1 = np.sqrt(1 - np.power(sin_q1_plus_phi, 2))
        cos_q1_plus_phi_2 = -np.sqrt(1 - np.power(sin_q1_plus_phi, 2))

        if (abs(sin_q1_plus_phi) > 1):
            print('该末端位姿下机械臂无关节逆解!!!')
        else:
            q1_1 = np.arctan2(sin_q1_plus_phi, self.close_zero_one(cos_q1_plus_phi_1)) - phi1
            q1_2 = np.arctan2(sin_q1_plus_phi, self.close_zero_one(cos_q1_plus_phi_2)) - phi1

    #  计算关节5的角度
	    ###########  q1_1对应
        cosq5_1 = self.close_zero_one(ax * np.sin(q1_1) - ay * np.cos(q1_1)) 
        if (abs(cosq5_1) <= 1):
            q5_1 = np.arccos(cosq5_1) 
            q5_2 = -np.arccos(cosq5_1) 
        else:
            q5_1 = np.nan
            q5_2 = np.nan

	    ##########  q1_2对应
        cosq5_2 = self.close_zero_one(ax * np.sin(q1_2) - ay * np.cos(q1_2)) 
        if (abs(cosq5_2) <= 1):
            q5_3 = np.arccos(cosq5_2) 
            q5_4 = -np.arccos(cosq5_2) 
        else:
            q5_3 = np.nan
            q5_4 = np.nan

    #  计算关节6的角度
	    ########## q1_1对应
        u6_1 = ox * np.sin(q1_1) - oy * np.cos(q1_1) 
        v6_1 = ny * np.cos(q1_1) - nx * np.sin(q1_1) 
        if (abs(cosq5_1) <= 1) :
            q6_1 = np.arctan2((-np.sin(q5_1)) / np.sqrt(np.power(u6_1, 2) + np.power(v6_1, 2)), 0) - np.arctan2(v6_1, self.close_zero_one(u6_1)) 
            q6_2 = np.arctan2((-np.sin(q5_2)) / np.sqrt(np.power(u6_1, 2) + np.power(v6_1, 2)), 0) - np.arctan2(v6_1, self.close_zero_one(u6_1)) 
        else :
            q6_1 =  np.nan 
            q6_2 =  np.nan 
	    ########## q1_2对应
        u6_2 = ox * np.sin(q1_2) - oy * np.cos(q1_2) 
        v6_2 = ny * np.cos(q1_2) - nx * np.sin(q1_2) 
        if (abs(cosq5_2) <= 1) :
            q6_3 = np.arctan2((-np.sin(q5_3)) / np.sqrt(np.power(u6_2, 2) + np.power(v6_2, 2)), 0) - np.arctan2(v6_2, self.close_zero_one(u6_2)) 
            q6_4 = np.arctan2((-np.sin(q5_4)) / np.sqrt(np.power(u6_2, 2) + np.power(v6_2, 2)), 0) - np.arctan2(v6_2, self.close_zero_one(u6_2)) 
        else :
            q6_3 =  np.nan 
            q6_4 =  np.nan 
    #  计算关节3的角度
	    ############q1_1对应
        t14_1 = d5 * (np.cos(q6_1) * (ox * np.cos(q1_1) + oy * np.sin(q1_1)) + np.sin(q6_1) * (nx * np.cos(q1_1) + ny * np.sin(q1_1))) - d6 * (ax * np.cos(q1_1) + ay * np.sin(q1_1)) + px * np.cos(q1_1) + py * np.sin(q1_1) 
        t34_1 = pz - d1 - az * d6 + d5 * (oz * np.cos(q6_1) + nz * np.sin(q6_1)) 
        t14_2 = d5 * (np.cos(q6_2) * (ox * np.cos(q1_1) + oy * np.sin(q1_1)) + np.sin(q6_2) * (nx * np.cos(q1_1) + ny * np.sin(q1_1))) - d6 * (ax * np.cos(q1_1) + ay * np.sin(q1_1)) + px * np.cos(q1_1) + py * np.sin(q1_1) 
        t34_2 = pz - d1 - az * d6 + d5 * (oz * np.cos(q6_2) + nz * np.sin(q6_2)) 

        cosq3_1 = self.close_zero_one((np.power(t14_1, 2) + np.power(t34_1, 2) - np.power(a2, 2) - np.power(a3, 2)) / (2 * a2 * a3)) 
        cosq3_2 = self.close_zero_one((np.power(t14_2, 2) + np.power(t34_2, 2) - np.power(a2, 2) - np.power(a3, 2)) / (2 * a2 * a3)) 
        if (abs(cosq5_1) <= 1):
            if (abs(cosq3_1) <= 1) :
                q3_1 = np.arccos(cosq3_1) 
                q3_2 = -np.arccos(cosq3_1) 
            else :
                q3_1 =  np.nan 
                q3_2 =  np.nan 

            if (abs(cosq3_2) <= 1) :
                q3_3 = np.arccos(cosq3_2) 
                q3_4 = -np.arccos(cosq3_2) 
            else :
                q3_3 =  np.nan 
                q3_4 =  np.nan 
        else :
            q3_1 =  np.nan 
            q3_2 =  np.nan 
            q3_3 =  np.nan 
            q3_4 =  np.nan 

        ################q1_2对应
        t14_3 = d5 * (np.cos(q6_3) * (ox * np.cos(q1_2) + oy * np.sin(q1_2)) + np.sin(q6_3) * (nx * np.cos(q1_2) + ny * np.sin(q1_2))) - d6 * (ax * np.cos(q1_2) + ay * np.sin(q1_2)) + px * np.cos(q1_2) + py * np.sin(q1_2) 
        t34_3 = pz - d1 - az * d6 + d5 * (oz * np.cos(q6_3) + nz * np.sin(q6_3)) 
        t14_4 = d5 * (np.cos(q6_4) * (ox * np.cos(q1_2) + oy * np.sin(q1_2)) + np.sin(q6_4) * (nx * np.cos(q1_2) + ny * np.sin(q1_2))) - d6 * (ax * np.cos(q1_2) + ay * np.sin(q1_2)) + px * np.cos(q1_2) + py * np.sin(q1_2) 
        t34_4 = pz - d1 - az * d6 + d5 * (oz * np.cos(q6_4) + nz * np.sin(q6_4)) 

        cosq3_3 = self.close_zero_one((np.power(t14_3, 2) + np.power(t34_3, 2) - np.power(a2, 2) - np.power(a3, 2)) / (2 * a2 * a3)) 
        cosq3_4 = self.close_zero_one((np.power(t14_4, 2) + np.power(t34_4, 2) - np.power(a2, 2) - np.power(a3, 2)) / (2 * a2 * a3)) 
    
        if (abs(cosq5_2) <= 1) :
            if (abs(cosq3_3) <= 1) :
                q3_5 = np.arccos(cosq3_3) 
                q3_6 = -np.arccos(cosq3_3) 
            else :
                q3_5 =  np.nan 
                q3_6 =  np.nan 
            if (abs(cosq3_4) <= 1) :
                q3_7 = np.arccos(cosq3_4) 
                q3_8 = -np.arccos(cosq3_4) 
            else :
                q3_7 =  np.nan 
                q3_8 =  np.nan 
        else :
            q3_5 =  np.nan 
            q3_6 =  np.nan 
            q3_7 =  np.nan 
            q3_8 =  np.nan 
        
    #/*****关节2*****/
	    #// q1_1对应
        g2_1,h2_1 = a3 * np.sin(q3_1) , a2 + a3 * np.cos(q3_1)
        g2_2,h2_2 = a3 * np.sin(q3_2)  , a2 + a3 * np.cos(q3_2)
        g2_3,h2_3 = a3 * np.sin(q3_3)  ,a2 + a3 * np.cos(q3_3)
        g2_4,h2_4 = a3 * np.sin(q3_4) , a2 + a3 * np.cos(q3_4)

        if (abs(cosq5_1) <= 1) :
            q2_1 = np.arctan2((h2_1 * t34_1 - g2_1 * t14_1), self.close_zero_one(h2_1 * t14_1 + g2_1 * t34_1))
            q2_2 = np.arctan2((h2_2 * t34_1 - g2_2 * t14_1), self.close_zero_one(h2_2 * t14_1 + g2_2 * t34_1))
            q2_3 = np.arctan2((h2_3 * t34_2 - g2_3 * t14_2), self.close_zero_one(h2_3 * t14_2 + g2_3 * t34_2))
            q2_4 = np.arctan2((h2_4 * t34_2 - g2_4 * t14_2), self.close_zero_one(h2_4 * t14_2 + g2_4 * t34_2))
	 
        else :
            q2_1 =  np.nan
            q2_2 =  np.nan
            q2_3 =  np.nan
            q2_4 =  np.nan
	 

	    #// q1_2对应
        g2_5,h2_5 = a3 * np.sin(q3_5) , a2 + a3 * np.cos(q3_5)
        g2_6,h2_6 = a3 * np.sin(q3_6) , a2 + a3 * np.cos(q3_6)
        g2_7,h2_7 = a3 * np.sin(q3_7)  ,a2 + a3 * np.cos(q3_7)
        g2_8,h2_8 = a3 * np.sin(q3_8) , a2 + a3 * np.cos(q3_8)

        if (abs(cosq5_2) <= 1) :
            q2_5 = np.arctan2((h2_5 * t34_3 - g2_5 * t14_3), self.close_zero_one(h2_5 * t14_3 + g2_5 * t34_3))
            q2_6 = np.arctan2((h2_6 * t34_3 - g2_6 * t14_3), self.close_zero_one(h2_6 * t14_3 + g2_6 * t34_3))
            q2_7 = np.arctan2((h2_7 * t34_4 - g2_7 * t14_4), self.close_zero_one(h2_7 * t14_4 + g2_7 * t34_4))
            q2_8 = np.arctan2((h2_8 * t34_4 - g2_8 * t14_4), self.close_zero_one(h2_8 * t14_4 + g2_8 * t34_4))
        else :
            q2_5 =  np.nan
            q2_6 =  np.nan
            q2_7 =  np.nan
            q2_8 =  np.nan
	 

	#/*****关节4*****/
	    #// q1_1对应
        sin234_1 = -np.cos(q6_1) * (ox * np.cos(q1_1) + oy * np.sin(q1_1)) - np.sin(q6_1) * (nx * np.cos(q1_1) + ny * np.sin(q1_1))
        sin234_2 = -np.cos(q6_2) * (ox * np.cos(q1_1) + oy * np.sin(q1_1)) - np.sin(q6_2) * (nx * np.cos(q1_1) + ny * np.sin(q1_1))
        cos234_1 = oz * np.cos(q6_1) + nz * np.sin(q6_1)
        cos234_2 = oz * np.cos(q6_2) + nz * np.sin(q6_2)
        if (abs(cosq5_1) <= 1) :
            q4_1 = np.arctan2(sin234_1, self.close_zero_one(cos234_1)) - q2_1 - q3_1
            q4_2 = np.arctan2(sin234_1, self.close_zero_one(cos234_1)) - q2_2 - q3_2
            q4_3 = np.arctan2(sin234_2, self.close_zero_one(cos234_2)) - q2_3 - q3_3
            q4_4 = np.arctan2(sin234_2, self.close_zero_one(cos234_2)) - q2_4 - q3_4
        else :
            q4_1 =  np.nan
            q4_2 =  np.nan
            q4_3 =  np.nan
            q4_4 =  np.nan

	    #// q1_2对应
        sin234_3 = -np.cos(q6_3) * (ox * np.cos(q1_2) + oy * np.sin(q1_2)) - np.sin(q6_3) * (nx * np.cos(q1_2) + ny * np.sin(q1_2))
        sin234_4 = -np.cos(q6_4) * (ox * np.cos(q1_2) + oy * np.sin(q1_2)) - np.sin(q6_4) * (nx * np.cos(q1_2) + ny * np.sin(q1_2))
        cos234_3 = oz * np.cos(q6_3) + nz * np.sin(q6_3)
        cos234_4 = oz * np.cos(q6_4) + nz * np.sin(q6_4)

        if (abs(cosq5_2) <= 1) :   
            q4_5 = np.arctan2(sin234_3, self.close_zero_one(cos234_3)) - q2_5 - q3_5
            q4_6 = np.arctan2(sin234_3, self.close_zero_one(cos234_3)) - q2_6 - q3_6
            q4_7 = np.arctan2(sin234_4, self.close_zero_one(cos234_4)) - q2_7 - q3_7
            q4_8 = np.arctan2(sin234_4, self.close_zero_one(cos234_4)) - q2_8 - q3_8
	 
        else :
            q4_5 =  np.nan
            q4_6 =  np.nan
            q4_7 =  np.nan
            q4_8 =  np.nan

        result=[]
        if not (np.isnan(q1_1) or np.isnan(q2_1) or np.isnan(q3_1) or np.isnan(q4_1) or np.isnan(q5_1) or np.isnan(q6_1)):
            result.append(np.array([q1_1, q2_1, q3_1, q4_1, q5_1, q6_1]))

        if not (np.isnan(q1_1) or np.isnan(q2_2) or np.isnan(q3_2) or np.isnan(q4_2) or np.isnan(q5_1) or np.isnan(q6_1)):
            result.append(np.array([q1_1, q2_2, q3_2, q4_2, q5_1, q6_1]))

        if not (np.isnan(q1_1) or np.isnan(q2_3) or np.isnan(q3_3) or np.isnan(q4_3) or np.isnan(q5_2) or np.isnan(q6_2)):
            result.append(np.array([q1_1, q2_3, q3_3, q4_3, q5_2, q6_2]))

        if not (np.isnan(q1_1) or np.isnan(q2_4) or np.isnan(q3_4) or np.isnan(q4_4) or np.isnan(q5_2) or np.isnan(q6_2)):
            result.append(np.array([q1_1, q2_4, q3_4, q4_4, q5_2, q6_2]))

        if not (np.isnan(q1_2) or np.isnan(q2_5) or np.isnan(q3_5) or np.isnan(q4_5) or np.isnan(q5_3) or np.isnan(q6_3)):
            result.append(np.array([q1_2, q2_5, q3_5, q4_5, q5_3, q6_3]))

        if not (np.isnan(q1_2) or np.isnan(q2_6) or np.isnan(q3_6) or np.isnan(q4_6) or np.isnan(q5_3) or np.isnan(q6_3)):
            result.append(np.array([q1_2, q2_6, q3_6, q4_6, q5_3, q6_3]))

        if not (np.isnan(q1_2) or np.isnan(q2_7) or np.isnan(q3_7) or np.isnan(q4_7) or np.isnan(q5_4) or np.isnan(q6_4)):
            result.append(np.array([q1_2, q2_7, q3_7, q4_7, q5_4, q6_4]))

        if not (np.isnan(q1_2) or np.isnan(q2_8) or np.isnan(q3_8) or np.isnan(q4_8) or np.isnan(q5_4) or np.isnan(q6_4)):
            result.append(np.array([q1_2, q2_8, q3_8, q4_8, q5_4, q6_4]))

        return result
    
    def select_nearest_solution(self,result_list,ref_angle=None,angle_weight=None):
        """
        寻找最优解1000次时间为0.24s
        寻找最优解，可以提供。
        args:
            result_list,可选择的解
            ref_angle: 参考的角度，寻找对应该角度的最有解
            angle_weight: 有没有关节重要性，比如某个关节尽量少转动
        Returns:
            np.ndarray: 4x4 齐次变换矩阵。
        """

        if len(result_list) == 0:
            print("当前末端位姿无有效逆解!!!")
            return None
        
        #更新参考角度，如果没有则设置为当前机械臂的关节角度
        if not ref_angle:
            ref_angle=[]
            for item in self.cur_DH:
                ref_angle.append(item['theta'])
        #更新权重，如果没有则设置为【1，1，1，1，1，1】
        if  angle_weight:
            angle_weight=np.array(angle_weight)
        else:
            angle_weight=np.ones(len(self.cur_DH))

        # 循环查找最优解
        variation_angle = np.sum(angle_weight*np.abs(np.array(ref_angle) - np.array(result_list[0])))
        for q in result_list:
            variation_angle_cur = np.sum(angle_weight*np.abs(np.array(ref_angle) - np.array(q)))
            if variation_angle_cur < variation_angle:
                variation_angle = variation_angle_cur
                res = q
        return res
 
    def compute_jacobian(self,joint_angles=None):
        """
        计算雅可比矩阵
        :param joint_angles: 当前关节角度列表 [theta1, theta2, ...],若没有则用DH参数里面的theta
        :return: 雅可比矩阵 (6xN)
        计算jacobian的时间开销1000次时间为0.22s
        """
        num_joints = len(self.cur_DH)
        T = np.eye(4)  # 基坐标系到当前关节的变换矩阵
        positions = []  # 存储每个关节的位置
        z_axes = []     # 存储每个关节的Z轴方向

        # 计算每个关节的变换矩阵
        for i in range(num_joints):
            a, alpha, d = self.cur_DH[i]['a'],self.cur_DH[i]['alpha'],self.cur_DH[i]['d']
            if not joint_angles is None:
                theta = joint_angles[i]
            else:
                theta=self.cur_DH[i]['theta']
            T_i = robot_cal_util.dh_to_matrix(alpha,theta,a, d)
            T = np.dot(T, T_i)  # 累乘得到 T0^i
            positions.append(T[:3, 3])  # 提取位置
            z_axes.append(T[:3, 2])    # 提取Z轴方向
        # 末端位置
        p_n = positions[-1]
        # 构造雅可比矩阵
        J_v = []  # 位置部分
        J_omega = []  # 旋转部分
        for i in range(num_joints):
            z = z_axes[i]
            p = positions[i]
            # 计算位置部分
            J_v_i = np.cross(z, p_n - p)
            J_v.append(J_v_i)
            # 计算旋转部分
            J_omega_i = z
            J_omega.append(J_omega_i)
        # 拼接位置和旋转部分
        J = np.vstack((np.array(J_v).T, np.array(J_omega).T))
        return J
    
    def inverse_kinematics_homogeneous(self,target_matrix, initial_guess, max_iterations=100, tolerance=1e-5,iterate_mode=1):
        """
        基于数值解的六自由度机械臂逆运动学求解器 (齐次矩阵形式)
        求解速度与initial_guess的准确性相关，距离越近迭代次数越少速度越快，缺点是迭代一次的时间损耗比直接求逆解要高
        主要原因是过程中求解了雅可比矩阵，雅可比矩阵时间开销与逆解开销相似

        :param target_matrix: 目标末端齐次变换矩阵 (4x4)
        :param initial_guess: 初始关节角度猜测 [theta1, theta2, ..., theta6]
        :param max_iterations: 最大迭代次数
        :param tolerance: 收敛容忍度
        :param iterate_mode:迭代方式  0是牛顿法，1是违逆牛顿法，对于冗余机械臂、奇异点周围有较好的效果。
        :return: 求解后的关节角度数组 [theta1, theta2, ..., theta6]
        """
        joint_angles = np.array(initial_guess, dtype=float)
        for iteration in range(max_iterations):
            # 当前末端齐次变换矩阵
            current_matrix = self.forward_kinematics(joint_angles)
            # 计算位置误差和平移误差
            position_error = target_matrix[:3, 3] - current_matrix[:3, 3]
            # 计算姿态误差 (旋转部分)
            orientation_error = robot_cal_util.compute_orientation_error(current_matrix[:3, :3], target_matrix[:3, :3])
            # 将误差拼接为 6x1 向量 (位置误差 + 姿态误差)
            error = np.hstack((position_error, orientation_error))
            # 判断是否收敛
            if np.linalg.norm(error) < tolerance:
                print(f"Converged in {iteration + 1} iterations.")
                return robot_cal_util.normalize_angle(joint_angles)
            # 计算雅可比矩阵
            J = self.compute_jacobian(joint_angles)
            # 计算关节角度增量 (Δθ = J^+ * error)
            if iterate_mode==0:
                delta_theta = np.linalg.pinv(J).dot(error)
            elif iterate_mode==1:
                lambda_min,lambda_max=0.001, 0.1
                U, S, Vt = np.linalg.svd(J)
                sigma_min = np.min(S)
                # 动态阻尼因子
                damping_factor = np.clip(lambda_min + (lambda_max - lambda_min) * (1 / (1 + sigma_min)), lambda_min, lambda_max)
                # 构造阻尼矩阵
                damping_matrix = np.diag(S / (S**2 + damping_factor**2))
                # 计算伪逆
                jacobian_damped_pinv = Vt.T @ damping_matrix @ U.T
                # 求解增量
                delta_theta = jacobian_damped_pinv @ error
                # 更新关节角度
            joint_angles += delta_theta

        print("Warning: Maximum iterations reached without convergence.")
        return robot_cal_util.normalize_angle(joint_angles)

    def is_singular_point_jacobian(self,joint_angles, threshold=1e-6):
        self.compute_jacobian(joint_angles)
        """
        判断齐次矩阵对应的点是否是奇异点。
        :param joint_angles: 关节角度 (4x4)
        :param jacobian_func: 计算雅可比矩阵的函数，输入为齐次矩阵，输出为雅可比矩阵
        :param threshold: 判断奇异点的条件数阈值 (默认为1e-6)
        :return: 布尔值，True表示是奇异点，False表示不是奇异点
        """
        # 计算雅可比矩阵
        jacobian = self.compute_jacobian(joint_angles)
        # 计算雅可比矩阵的奇异值分解 (SVD)
        _, singular_values, _ = np.linalg.svd(jacobian)
        # 检查最小奇异值是否小于阈值
        if np.min(singular_values) < threshold:
            return True  # 是奇异点
        else:
            return False  # 不是奇异点

    
if __name__ == "__main__":
    # 创建机器人对象
    robot = UR_Robot_kinematic()
    # 计算正向运动学1000次时间为0.14s
    # 计算逆向运动学1000次时间为 0.37s
    #
    start=time.time()
    target_pose=[0.2, 0.3, 0.5, 0.2, 0.2,0.1]
    T = robot.forward_kinematics(target_pose)
    res=robot.Inverse_Kinematics(T)
    print(res)

    for i in range(1):
        ret=robot.inverse_kinematics_homogeneous(T,[0.5, 0.1, 0.2, 0.6, 0.9,0.11])
    print(ret)

    print(time.time()-start)
    a=[100,100,100]
    
