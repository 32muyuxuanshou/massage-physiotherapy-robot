import numpy as np
import robot_cal_util
import time
class ABB_Robot_kinematic:
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
        ## ABB类型的机械臂theta建模时存在offset，后面更新角度的时候需要添加theta的offset

        if not dh_params:
            dh_params = [
            {'alpha': 0,         'theta': 0,       'a': 0,         'd': 445},
            {'alpha': -np.pi/2,  'theta': np.pi/2, 'a': 150,       'd': 0},
            {'alpha': 0,         'theta': 0,       'a': -700,      'd': 0},
            {'alpha': np.pi/2,   'theta': 0,       'a': -115,      'd': 795},
            {'alpha': -np.pi/2,  'theta': 0,       'a': 0,         'd': 0},
            {'alpha': np.pi/2,   'theta': 0,       'a': 0,         'd': 85},]
        self.init_DH = dh_params
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
            self.cur_DH[i]['theta']=theta[i]+self.init_DH[i]['theta']
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
                theta=theta_cal[i]+self.init_DH[i]['theta']
            else:
                theta=self.cur_DH[i]['theta']
            transform = transform @ robot_cal_util.dh_to_matrix(alpha, theta, a, d)
        return transform 

    def find_equivalent_angle(self,theta):
        # 假设输入 theta 在 -pi/2 到 pi/2 之间
        if theta < -np.pi/2 or theta > np.pi/2:
            raise ValueError("Input angle must be in the range -pi/2 to pi/2")
    
        # 根据符号判断另一个解
        if theta > 0:
            return theta - np.pi
        else:
            return theta + np.pi
        
    def normalize_angle(self,angle):
        """
        将任意输入角度值归一化到 [-π, π] 的范围内。
    
        参数:
            angle (float): 输入角度值，单位为弧度。
    
        返回:
            float: 归一化后的角度值，范围为 [-π, π]。
        """
        # 使用 math.fmod 保留余数并手动归一化到 [-π, π]
        normalized_angle = (angle + np.pi) % (2 * np.pi) - np.pi
        return normalized_angle
        
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
        a1, a2, a3 = self.cur_DH[1]['a'], self.cur_DH[2]['a'],self.cur_DH[3]['a']

        #  计算关节一的角度
        #  倘若有d2的话则存在两个解（左右型臂），不存在d2时另一个解在一轴旋转180°处

        q1_1=np.arctan((ay*d6-py)/(ax*d6-px))
        q1_2=self.find_equivalent_angle(q1_1)
        #print('q1: ',q1_1,q1_2)
        
        #  计算关节二的角度
        k1_1=a1-(py-d6*ay)/np.sin(q1_1)
        k1_2=a1-(py-d6*ay)/np.sin(q1_2)
        k2=d1-(pz-d6*az)

        temp1_1=(np.power(k1_1,2)+np.power(k2,2)+np.power(a2,2)-np.power(a3,2)-np.power(d4,2))/(2*a2*np.sqrt(np.power(k1_1,2)+np.power(k2,2)))
        temp1_2=(np.power(k1_2,2)+np.power(k2,2)+np.power(a2,2)-np.power(a3,2)-np.power(d4,2))/(2*a2*np.sqrt(np.power(k1_2,2)+np.power(k2,2)))
        if abs(temp1_1)<=1:
            q2_1=np.arcsin(temp1_1)-np.arctan2(k2/(np.power(k1_1,2)+np.power(k2,2)),k1_1/(np.power(k1_1,2)+np.power(k2,2)))
            q2_2=np.pi-np.arcsin(temp1_1)-np.arctan2(k2/(np.power(k1_1,2)+np.power(k2,2)),k1_1/(np.power(k1_1,2)+np.power(k2,2)))
        else:
            q2_1=np.nan
            q2_2=np.nan
        if abs(temp1_2)<=1:
            q2_3=np.arcsin(temp1_2)-np.arctan2(k2/(np.power(k1_2,2)+np.power(k2,2)),k1_2/(np.power(k1_2,2)+np.power(k2,2)))
            q2_4=np.pi-np.arcsin(temp1_2)-np.arctan2(k2/(np.power(k1_2,2)+np.power(k2,2)),k1_2/(np.power(k1_2,2)+np.power(k2,2)))
        else:
            q2_3=np.nan
            q2_4=np.nan
        #print('q2: ',q2_1,q2_2,q2_3,q2_4)

        #  计算关节三的角度
        temp=np.power(a3,2)+np.power(d4,2)
        if q2_1 is np.nan:
            q3_1=np.nan
            q3_2=np.nan
        else:
            A1,B1=k1_1-a2*np.sin(q2_1),k2-a2*np.cos(q2_1)
            A2,B2=k1_1-a2*np.sin(q2_2),k2-a2*np.cos(q2_2)
            sin23_1=(a3*A1+d4*B1)/temp
            sin23_2=(a3*A2+d4*B2)/temp
            cos23_1=(a3*B1-d4*A1)/temp
            cos23_2=(a3*B2-d4*A2)/temp
            q3_1=np.arctan2(sin23_1,cos23_1)-q2_1
            q3_2=np.arctan2(sin23_2,cos23_2)-q2_2
        if q2_3 is np.nan:
            q3_3=np.nan
            q3_4=np.nan
        else:
            A3,B3=k1_2-a2*np.sin(q2_3),k2-a2*np.cos(q2_3)
            A4,B4=k1_2-a2*np.sin(q2_4),k2-a2*np.cos(q2_4)
            sin23_3=(a3*A3+d4*B3)/temp
            sin23_4=(a3*A4+d4*B4)/temp
            cos23_3=(a3*B3-d4*A3)/temp
            cos23_4=(a3*B4-d4*A4)/temp
            q3_3=np.arctan2(sin23_3,cos23_3)-q2_3
            q3_4=np.arctan2(sin23_4,cos23_4)-q2_4
        #print('q3: ',q3_1,q3_2,q3_3,q3_4)

        #  计算关节五的角度
        if q2_1 is np.nan:
            q5_1=np.nan
            q5_2=np.nan
            q5_3=np.nan
            q5_4=np.nan
        else:
            cos5_1=ax*cos23_1*np.cos(q1_1)+ay*cos23_1*np.sin(q1_1)-az*sin23_1
            cos5_2=ax*cos23_2*np.cos(q1_1)+ay*cos23_2*np.sin(q1_1)-az*sin23_2
            q5_1=np.arccos(cos5_1)
            q5_2=np.arccos(cos5_2)
            q5_3=-q5_1
            q5_4=-q5_2

        if q2_3 is np.nan:
            q5_5=np.nan
            q5_6=np.nan
            q5_7=np.nan
            q5_8=np.nan
        else:
            cos5_3=ax*cos23_3*np.cos(q1_2)+ay*cos23_3*np.sin(q1_2)-az*sin23_3
            cos5_4=ax*cos23_4*np.cos(q1_2)+ay*cos23_4*np.sin(q1_2)-az*sin23_4
            q5_5=np.arccos(cos5_3)
            q5_6=np.arccos(cos5_4)
            q5_7=-q5_5
            q5_8=-q5_6
        #print('q5:  ',q5_1,q5_2,q5_3,q5_4,q5_6,q5_7,q5_8)

        #  计算关节4的角度:
        if q2_1 is np.nan:
            q4_1=np.nan
            q4_2=np.nan
            q4_3=np.nan
            q4_4=np.nan
        else:
            temp=(ay*np.cos(q1_1)-ax*np.sin(q1_1))
            sin4_1=temp/np.sin(q5_1)
            sin4_2=temp/np.sin(q5_2)
            sin4_3=temp/np.sin(q5_3)
            sin4_4=temp/np.sin(q5_4)
            cos4_1=(-az*cos23_1-ax*sin23_1*np.cos(q1_1)-ay*sin23_1*np.sin(q1_1))/np.sin(q5_1)
            cos4_2=(-az*cos23_2-ax*sin23_2*np.cos(q1_1)-ay*sin23_2*np.sin(q1_1))/np.sin(q5_2)
            cos4_3=(-az*cos23_1-ax*sin23_1*np.cos(q1_1)-ay*sin23_1*np.sin(q1_1))/np.sin(q5_3)
            cos4_4=(-az*cos23_2-ax*sin23_2*np.cos(q1_1)-ay*sin23_2*np.sin(q1_1))/np.sin(q5_4)
            q4_1=np.arctan2(sin4_1,cos4_1)
            q4_2=np.arctan2(sin4_2,cos4_2)
            q4_3=np.arctan2(sin4_3,cos4_3)
            q4_4=np.arctan2(sin4_4,cos4_4)
        if q2_3 is np.nan:
            q4_5=np.nan
            q4_6=np.nan
            q4_7=np.nan
            q4_8=np.nan
        else:
            temp=(ay*np.cos(q1_2)-ax*np.sin(q1_2))
            sin4_5=temp/np.sin(q5_5)
            sin4_6=temp/np.sin(q5_6)
            sin4_7=temp/np.sin(q5_7)
            sin4_8=temp/np.sin(q5_8)
            cos4_5=(-az*cos23_3-ax*sin23_3*np.cos(q1_2)-ay*sin23_3*np.sin(q1_2))/np.sin(q5_5)
            cos4_6=(-az*cos23_4-ax*sin23_4*np.cos(q1_2)-ay*sin23_4*np.sin(q1_2))/np.sin(q5_6)
            cos4_7=(-az*cos23_3-ax*sin23_3*np.cos(q1_2)-ay*sin23_3*np.sin(q1_2))/np.sin(q5_7)
            cos4_8=(-az*cos23_4-ax*sin23_4*np.cos(q1_2)-ay*sin23_4*np.sin(q1_2))/np.sin(q5_8)
            q4_5=np.arctan2(sin4_5,cos4_5)
            q4_6=np.arctan2(sin4_6,cos4_6)
            q4_7=np.arctan2(sin4_7,cos4_7)
            q4_8=np.arctan2(sin4_8,cos4_8)
        #print('q4:  ',q4_1,q4_2,q4_3,q4_4,q4_5,q4_6,q4_7,q4_8)

        if q2_1 is np.nan:
            q6_1=np.nan
            q6_2=np.nan
            q6_3=np.nan
            q6_4=np.nan
        else:
            sin6_1=(ox*cos23_1*np.cos(q1_1)+oy*cos23_1*np.sin(q1_1)-oz*sin23_1)/np.sin(q5_1)
            sin6_2=(ox*cos23_2*np.cos(q1_1)+oy*cos23_2*np.sin(q1_1)-oz*sin23_2)/np.sin(q5_2)
            sin6_3=(ox*cos23_1*np.cos(q1_1)+oy*cos23_1*np.sin(q1_1)-oz*sin23_1)/np.sin(q5_3)
            sin6_4=(ox*cos23_2*np.cos(q1_1)+oy*cos23_2*np.sin(q1_1)-oz*sin23_2)/np.sin(q5_4)
            cos6_1=(nz*sin23_1-nx*cos23_1*np.cos(q1_1)-ny*cos23_1*np.sin(q1_1))/np.sin(q5_1)
            cos6_2=(nz*sin23_2-nx*cos23_2*np.cos(q1_1)-ny*cos23_2*np.sin(q1_1))/np.sin(q5_2)
            cos6_3=(nz*sin23_1-nx*cos23_1*np.cos(q1_1)-ny*cos23_1*np.sin(q1_1))/np.sin(q5_3)
            cos6_4=(nz*sin23_2-nx*cos23_2*np.cos(q1_1)-ny*cos23_2*np.sin(q1_1))/np.sin(q5_4)
            q6_1=np.arctan2(sin6_1,cos6_1)
            q6_2=np.arctan2(sin6_2,cos6_2)
            q6_3=np.arctan2(sin6_3,cos6_3)
            q6_4=np.arctan2(sin6_4,cos6_4)

        if q2_3 is np.nan:
            q6_5=np.nan
            q6_6=np.nan
            q6_7=np.nan
            q6_8=np.nan
        else:
            sin6_5=(ox*cos23_3*np.cos(q1_2)+oy*cos23_3*np.sin(q1_2)-oz*sin23_3)/np.sin(q5_5)
            sin6_6=(ox*cos23_4*np.cos(q1_2)+oy*cos23_4*np.sin(q1_2)-oz*sin23_4)/np.sin(q5_6)
            sin6_7=(ox*cos23_3*np.cos(q1_2)+oy*cos23_3*np.sin(q1_2)-oz*sin23_3)/np.sin(q5_7)
            sin6_8=(ox*cos23_4*np.cos(q1_2)+oy*cos23_4*np.sin(q1_2)-oz*sin23_4)/np.sin(q5_8)
            cos6_5=(nz*sin23_3-nx*cos23_3*np.cos(q1_2)-ny*cos23_3*np.sin(q1_2))/np.sin(q5_5)
            cos6_6=(nz*sin23_4-nx*cos23_4*np.cos(q1_2)-ny*cos23_4*np.sin(q1_2))/np.sin(q5_6)
            cos6_7=(nz*sin23_3-nx*cos23_3*np.cos(q1_2)-ny*cos23_3*np.sin(q1_2))/np.sin(q5_7)
            cos6_8=(nz*sin23_4-nx*cos23_4*np.cos(q1_2)-ny*cos23_4*np.sin(q1_2))/np.sin(q5_8)
            q6_5=np.arctan2(sin6_5,cos6_5)
            q6_6=np.arctan2(sin6_6,cos6_6)
            q6_7=np.arctan2(sin6_7,cos6_7)
            q6_8=np.arctan2(sin6_8,cos6_8)
        print('q6:  ',q6_1,q6_2,q6_3,q6_4,q6_5,q6_6,q6_7,q6_8)
        result=[]
        if not (np.isnan(q2_1)):
            result.append(np.array([self.normalize_angle(q1_1), self.normalize_angle(q2_1), 
                                    self.normalize_angle(q3_1), q4_1, q5_1, q6_1]))
            result.append(np.array([self.normalize_angle(q1_1), self.normalize_angle(q2_1), 
                                    self.normalize_angle(q3_1), q4_3, q5_3, q6_3]))
            result.append(np.array([self.normalize_angle(q1_1), self.normalize_angle(q2_2), 
                                    self.normalize_angle(q3_2), q4_2, q5_2, q6_2]))
            result.append(np.array([self.normalize_angle(q1_1), self.normalize_angle(q2_2), 
                                    self.normalize_angle(q3_2), q4_4, q5_4, q6_4]))
        if not (np.isnan(q2_3)):
            result.append(np.array([self.normalize_angle(q1_2), self.normalize_angle(q2_3), 
                                    self.normalize_angle(q3_3), q4_5, q5_5, q6_5]))
            result.append(np.array([self.normalize_angle(q1_2), self.normalize_angle(q2_3), 
                                    self.normalize_angle(q3_3), q4_7, q5_7, q6_7]))
            result.append(np.array([self.normalize_angle(q1_2), self.normalize_angle(q2_4), 
                                    self.normalize_angle(q3_4), q4_6, q5_6, q6_6]))
            result.append(np.array([self.normalize_angle(q1_2), self.normalize_angle(q2_4), 
                                    self.normalize_angle(q3_4), q4_8, q5_8, q6_8]))

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
                theta = joint_angles[i]+self.init_DH[i]['theta']
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
        #每迭代1000次耗时0.35
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
                #print(f"Converged in {iteration + 1} iterations.")
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
    robot = ABB_Robot_kinematic()
    # 计算正向运动学1000次时间为0.14s
    # 计算逆向运动学1000次时间为 0.37s
    #
    start=time.time()
    target_pose=[0.2, 0.3, 0.5, 0.2, 0.2,0.1]
    T = robot.forward_kinematics(target_pose)
    res=robot.Inverse_Kinematics(T)
    for item in res:
        print(robot.forward_kinematics(item))
        print()
    print(res)
    for i in range(1000):
        ret=robot.inverse_kinematics_homogeneous(T,[-0.22,0.32 , 0.51, 0.19, 0.19,0.11])
    print(ret)
    print(time.time()-start)
    a=[100,100,100]
    
