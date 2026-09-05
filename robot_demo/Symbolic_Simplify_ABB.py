from sympy import symbols, simplify, Matrix, cos, sin, pi

# 定义符号变量
theta1, theta2, theta3, theta4, theta5, theta6 = symbols('t1 t2 t3 t4 t5 t6')
d1, d2, d3, d4, d5, d6 = symbols('d1 d2 d3 d4 d5 d6')
a1, a2, a3, a4, a5, a6 = symbols('a1 a2 a3 a4 a5 a6')
alpha1, alpha2, alpha3, alpha4, alpha5, alpha6 = symbols('alpha1 alpha2 alpha3 alpha4 alpha5 alpha6')
nx, ox, ax, px, ny, oy, ay, py, nz, oz, az, pz =symbols('nx ox ax px ny oy ay py nz oz az pz')
# 定义DH矩阵中的单个变换
def mdh_transform(theta, d, a, alpha):
    """
    改进 DH 参数变换矩阵
    """

    return Matrix([
        [cos(theta), -sin(theta)*cos(alpha),  sin(theta)*sin(alpha), a*cos(theta)],
        [sin(theta),  cos(theta)*cos(alpha), -cos(theta)*sin(alpha), a*sin(theta)],
        [0,           sin(alpha),              cos(alpha),            d],
        [0,           0,                       0,                     1]
    ])


# 定义六自由度机械臂的每个关节的变换矩阵
T1 = mdh_transform(theta1, d1, 0, 0)
T2 = mdh_transform(theta2, 0, 0, -pi/2)
T3 = mdh_transform(theta3, 0, a3, 0)
T4 = mdh_transform(theta4, 0, 0, 0)
T5 = mdh_transform(theta5, d5, 0, -pi/2)
T6 = mdh_transform(theta6, 0, 0, pi/2)

T_end=Matrix([[nx, ox, ax, px],[ny, oy, ay, py],[nz, oz, az, pz],[0,0,0,1]])

# 总的变换矩阵
T_R = T1@T2@T3@T4

# 矩阵化简
T_R = simplify(T_R)
T_L=T_end @ Matrix.inv(T5 @ T6)
T_L=simplify(T_L)
# 输出化简后的矩阵
print("Simplified Transformation R:")
for i in range(3):
    print(T_R[i,:4])
    print()

print("Simplified Transformation L:")
for i in range(3):
    print(T_L[i,:4])
    print()

print(T1)
print(T2)
print(T3)
print(T4)
print(T5)
print(T6)