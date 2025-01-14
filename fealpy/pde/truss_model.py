import numpy as np

from ..decorator import cartesian 
from ..mesh import EdgeMesh


class TrussBase:
    @staticmethod
    def convert_units(length_in_inches, force_in_pounds):
        """
        英寸 in 转换成毫米 mm 
        磅 lb 转换成牛顿 N
        """
        length_in_mm = length_in_inches * 25.4
        force_in_newtons = force_in_pounds * 4.44822
        return length_in_mm, force_in_newtons


class Truss_3d():
    def __init__(self):
        """
        初始化函数

        在此函数中设置桁架模型的基本参数
        """
        self.A0: float = 2000 # 横截面积 mm^2
        self.E: float = 1500 # 弹性模量 ton/mm^2

    def init_mesh(self):
        """
        初始化网格结构

        此函数用于初始化桁架的网格结构

        返回:
        mesh: EdgeMesh, 初始化的网格对象
        """
        mesh = EdgeMesh.from_tower()

        return mesh

    @cartesian
    def displacement(self, p):
        pass

    @cartesian
    def jacobian(self, p):
        pass

    @cartesian
    def strain(self, p):
        pass

    @cartesian
    def stress(self, p):
        pass

    @cartesian
    def source(self, p):
        shape = len(p.shape[:-1])*(1,) + (-1, )
        val = np.zeros(shape, dtype=np.float_)
        return val 

    @cartesian
    def force(self):
        '''
        施加 (0, 900, 0) 的力，即平行于 y 轴方向大小为 900N 的力
        '''
        val = np.array([0, 900, 0])
        return val

    def is_force_boundary(self, p):
        '''
        对第 0，1 号节点施加力
        '''
        return np.abs(p[..., 2]) == 5080

    @cartesian
    def dirichlet(self, p):
        shape = len(p.shape)*(1, )
        val = np.array([0.0])
        return val.reshape(shape)

    @cartesian
    def is_dirichlet_boundary(self, p):
        return np.abs(p[..., 2]) < 1e-12


class Truss_3d_simple_truss():
    def __init__(self):
        self.A = 1.56 # 横截面积 in^2
        self.E = 10.6e6 # 弹性模量 lb/in^2
        # self.A, self.E = TrussBase.convert_units(self.A, self.E)

    def init_mesh(self):
        mesh = EdgeMesh.from_simple_3d_truss()
        return mesh


class Truss_2d_four_bar():
    def __init__(self):
        self.A = 100 # 横截面积 mm^2
        self.E = 29.5e4 # 弹性模量 ton/mm^2

    def init_mesh(self):
        mesh = EdgeMesh.from_four_bar()
        return mesh

    @cartesian
    def displacement(self, p):
        pass

    @cartesian
    def jacobian(self, p):
        pass

    @cartesian
    def strain(self, p):
        pass

    @cartesian
    def stress(self, p):
        pass

    @cartesian
    def source(self, p):
        shape = len(p.shape[:-1])*(1,) + (-1, )
        val = np.zeros(shape, dtype=np.float_)
        return val 

    @cartesian
    def force(self, p):
        '''
        施加 (0, 900, 0) 的力，即平行于 y 轴方向大小为 900N 的力
        '''
        val = np.array([0, 900, 0])
        return val

    def is_force_boundary(self, p):
        '''
        对第 3, 4 号节点施加力
        '''
        return np.abs(p[..., 1]) < 1e-12 and np.ads(p[..., 0]) > 1e-12

    @cartesian
    def dirichlet(self, p):
        shape = len(p.shape)*(1, )
        val = np.array([0.0])
        return val.reshape(shape)

    @cartesian
    def is_dirichlet_boundary(self, p):
        return np.abs(p[..., 0]) < 1e-12


class Truss_2d_balcony_truss(TrussBase):
    def __init__(self):
        self.A = 8 # 横截面积 in^2
        self.E = 1.9e6 # 弹性模量 lb/in^2
        # self.A, self.E = TrussBase.convert_units(self.A, self.E)

    def init_mesh(self):
        mesh = EdgeMesh.from_balcony_truss()
        return mesh

    @cartesian
    def displacement(self, p):
        pass

    @cartesian
    def jacobian(self, p):
        pass

    @cartesian
    def strain(self, p):
        pass

    @cartesian
    def stress(self, p):
        pass

    @cartesian
    def source(self, p):
        shape = len(p.shape[:-1])*(1,) + (-1, )
        val = np.zeros(shape, dtype=np.float_)
        return val 

    @cartesian
    def force(self, p):
        '''
        施加 (0, 900, 0) 的力，即平行于 y 轴方向大小为 900N 的力
        '''
        val = np.array([0, 900, 0])
        return val

    def is_force_boundary(self, p):
        '''
        对第 3, 4 号节点施加力
        '''
        return np.abs(p[..., 1]) < 1e-12 and np.ads(p[..., 0]) > 1e-12

    @cartesian
    def dirichlet(self, p):
        shape = len(p.shape)*(1, )
        val = np.array([0.0])
        return val.reshape(shape)

    @cartesian
    def is_dirichlet_boundary(self, p):
        return np.abs(p[..., 0]) < 1e-12

class Truss_2d_old():
    def __init__(self):
        self.A = 6451.6 # 横截面积 mm^2
        self.E = 0.7031 # 弹性模量 ton/mm^2

    def init_mesh(self, n=1):
        l = 9143 # 单位 mm
        node = np.array([
            [0, l], [l, l], [2*l, l],
            [0, 0], [l, 0], [2*l, 0]], dtype=np.float64)
        edge = np.array([
            [0, 1], [0, 4], [1, 2], [1, 3], [1, 4],
            [1, 5], [2, 3], [2, 4], [3, 4], [4, 5]], dtype=np.int_)
        mesh = EdgeMesh(node, edge)
        return mesh

    @cartesian
    def displacement(self, p):
        pass

    @cartesian
    def jacobian(self, p):
        pass

    @cartesian
    def strain(self, p):
        pass

    @cartesian
    def stress(self, p):
        pass

    @cartesian
    def source(self, p):
        shape = len(p.shape[:-1])*(1,) + (-1, )
        val = np.zeros(shape, dtype=np.float_)
        return val 

    @cartesian
    def force(self, p):
        '''
        施加 (0, 900, 0) 的力，即平行于 y 轴方向大小为 900N 的力
        '''
        val = np.array([0, 900, 0])
        return val

    def is_force_boundary(self, p):
        '''
        对第 3, 4 号节点施加力
        '''
        return np.abs(p[..., 1]) < 1e-12 and np.ads(p[..., 0]) > 1e-12

    @cartesian
    def dirichlet(self, p):
        shape = len(p.shape)*(1, )
        val = np.array([0.0])
        return val.reshape(shape)

    @cartesian
    def is_dirichlet_boundary(self, p):
        return np.abs(p[..., 0]) < 1e-12


