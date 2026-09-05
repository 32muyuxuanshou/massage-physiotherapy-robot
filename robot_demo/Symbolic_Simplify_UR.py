from sympy import symbols, simplify, Matrix, cos, sin, pi

# 定义符号变量
theta1, theta2, theta3, theta4, theta5, theta6 = symbols('t1 t2 t3 t4 t5 t6')
d1, d2, d3, d4, d5, d6 = symbols('d1 d2 d3 d4 d5 d6')
a1, a2, a3, a4, a5, a6 = symbols('a1 a2 a3 a4 a5 a6')
t = symbols("t")
alpha1, alpha2, alpha3, alpha4, alpha5, alpha6 = symbols('alpha1 alpha2 alpha3 alpha4 alpha5 alpha6')
nx, ox, ax, px, ny, oy, ay, py, nz, oz, az, pz = symbols('nx ox ax px ny oy ay py nz oz az pz')
# 定义DH矩阵中的单个变换
def dh_transform(theta, d, a, alpha):
    return Matrix([
        [cos(theta), -sin(theta), 0, a],
        [sin(theta)*cos(alpha), cos(theta)*cos(alpha), -sin(alpha), -sin(alpha)*d],
        [sin(theta)*sin(alpha), cos(theta)*sin(alpha), cos(alpha), cos(alpha)*d],
        [0, 0, 0, 1]
    ])

# 定义六自由度机械臂的每个关节的变换矩阵
T1 = dh_transform(theta1          ,  d1, 0, 0)
T2 = dh_transform(theta2 + pi      , 0, 0, pi / 2)
T3 = dh_transform(theta3 - t      , 0, a2, 0)
T4 = dh_transform(theta4 + t - 180, 0, a3, 0)
T5 = dh_transform(theta5 - pi / 2 , 0, a4, -pi / 2)
T6 = dh_transform(theta6, d6     , 0, -pi/2)
T_end=Matrix([[nx,ox,ax,px],[ny,oy,ay,py],[nz,oz,az,pz],[0,0,0,1]])
# 右边的变换矩阵
T_right =T2 @ T3 @ T4 @ T5
# 左边的变换矩阵
T_left = Matrix.inv(T1) @ T_end@ Matrix.inv(T6)
# 矩阵化简
T_s_R = simplify(T_right)
T_s_L = simplify(T_left)

print('Right matrix')
for i in range(3):
    print(T_s_R[i,0:4])

print('Left matrix')
for i in range(3):
    print(T_s_L[i,0:4])
