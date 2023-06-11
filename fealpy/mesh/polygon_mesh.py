import numpy as np
from typing import Union
from numpy.typing import NDArray
from scipy.sparse import csr_matrix, coo_matrix
import inspect

from ..common import ranges

from .mesh_base import Mesh2d, Plotable
from .mesh_data_structure import Mesh2dDataStructure


class PolygonMesh(Mesh2d, Plotable):
    """
    @brief Polygon mesh type.
    """
    ds: "PolygonMeshDataStructure"

    def __init__(self, node: NDArray, cell: NDArray, cellLocation=None, topdata=None):
        self.node = node
        if cellLocation is None:
            if len(cell.shape) == 2:
                NC = cell.shape[0]
                NV = cell.shape[1]
                cell = cell.reshape(-1)
                cellLocation = np.arange(0, (NC+1)*NV, NV)
            else:
                raise ValueError("Miss `cellLocation` array!")

        self.ds = PolygonMeshDataStructure(node.shape[0], cell, cellLocation,
                topdata=None)
        self.meshtype = 'polygon'
        self.itype = cell.dtype
        self.ftype = node.dtype

        self.celldata = {}
        self.nodedata = {}
        self.edgedata = {}
        self.facedata = self.edgedata
        self.meshdata = {}


    def integrator(self, q, etype='cell', qtype='legendre'):
        """
        @brief 获取不同维度网格实体上的积分公式
        """
        if etype in {'cell', 2}:
            from ..quadrature import TriangleQuadrature
            return TriangleQuadrature(q)
        elif etype in {'edge', 'face', 1}:
            if qtype in {'legendre'}:
                from ..quadrature import GaussLegendreQuadrature
                return GaussLegendreQuadrature(q)
            elif qtype in {'lobatto'}:
                from ..quadrature import GaussLobattoQuadrature
                return GaussLobattoQuadrature(q)

    def entity_barycenter(self, etype: Union[int, str]='cell', index=np.s_[:]):

        node = self.entity('node')
        GD = self.geo_dimension()

        if etype in {'cell', 2}:
            cell2node = self.ds.cell_to_node()
            NV = self.ds.number_of_vertices_of_cells().reshape(-1, 1)
            bc = cell2node*node/NV
        elif etype in {'edge', 'face', 1}:
            edge = self.ds.edge
            bc = np.mean(node[edge, :], axis=1).reshape(-1, GD)
        elif etype in {'node', 0}:
            bc = node
        return bc

    def bc_to_point(self, bc: NDArray, etype: Union[int, str]='cell',
                    index=np.s_[:]) -> NDArray:
        if etype in {'cell', 2}:
            raise NotImplementedError("cell_bc_to_point has not been implemented"
                                      "for polygon mesh.")
        else:
            return self.edge_bc_to_point(bcs=bc, index=index)

    def edge_bc_to_point(self, bcs: NDArray, index=np.s_[:]):
        """
        @brief 给出边上的重心坐标，返回其对应的插值点
        """
        node = self.entity('node')
        edge = self.entity('edge')
        ps = np.einsum('ij, kjm->ikm', bcs, node[edge[index]])
        return ps

    face_bc_to_point = edge_bc_to_point

    def number_of_global_ipoints(self, p: int) -> int:
        """
        @brief 插值点总数
        """
        gdof = self.number_of_nodes()
        if p > 1:
            NE = self.number_of_edges()
            NC = self.number_of_cells()
            gdof += NE*(p-1) + NC*(p-1)*p//2
        return gdof

    def number_of_local_ipoints(self,
            p: int, iptype: Union[int, str]='all') -> Union[NDArray, int]:
        """
        @brief 获取局部插值点的个数
        """
        if iptype in {'all'}:
            NV = self.ds.number_of_vertices_of_cells()
            ldof = NV + (p-1)*NV + (p-1)*p//2
            return ldof
        elif iptype in {'cell', 2}:
            return (p-1)*p//2
        elif iptype in {'edge', 'face', 1}:
            return (p+1)
        elif iptype in {'node', 0}:
            return 1

    def cell_to_ipoint(self, p: int, index=np.s_[:]) -> NDArray:
        """
        @brief
        """
        cell = self.entity('cell')
        if p == 1:
            return cell[index]
        else:
            NC = self.number_of_cells()
            ldof = self.number_of_local_ipoints(p, iptype='all')

            location = np.zeros(NC+1, dtype=self.itype)
            location[1:] = np.add.accumulate(ldof)

            cell2ipoint = np.zeros(location[-1], dtype=self.itype)

            edge2ipoint = self.edge_to_ipoint(p)
            edge2cell = self.ds.edge_to_cell()

            idx = location[edge2cell[:, [0]]] + edge2cell[:, [2]]*p + np.arange(p)
            cell2ipoint[idx] = edge2ipoint[:, 0:p]

            isInEdge = (edge2cell[:, 0] != edge2cell[:, 1])
            idx = (location[edge2cell[isInEdge, 1]] + edge2cell[isInEdge, 3]*p).reshape(-1, 1) + np.arange(p)
            cell2ipoint[idx] = edge2ipoint[isInEdge, p:0:-1]

            NN = self.number_of_nodes()
            NV = self.ds.number_of_vertices_of_cells()
            NE = self.number_of_edges()
            cdof = self.number_of_local_ipoints(p, iptype='cell')
            idx = (location[:-1] + NV*p).reshape(-1, 1) + np.arange(cdof)
            cell2ipoint[idx] = NN + NE*(p-1) + np.arange(NC*cdof).reshape(NC, cdof)
            return np.hsplit(cell2ipoint, location[1:-1])[index]

    def edge_to_ipoint(self, p: int, index=np.s_[:]) -> NDArray:
        """
        @brief 获取网格边与插值点的对应关系
        """
        if isinstance(index, slice) and index == slice(None):
            NE = self.number_of_edges()
            index = np.arange(NE)
        elif isinstance(index, np.ndarray) and (index.dtype == np.bool_):
            index, = np.nonzero(index)
            NE = len(index)
        elif isinstance(index, list) and (type(index[0]) is np.bool_):
            index, = np.nonzero(index)
            NE = len(index)
        else:
            NE = len(index)

        NN = self.number_of_nodes()

        edge = self.entity('edge', index=index)
        edge2ipoints = np.zeros((NE, p+1), dtype=self.itype)
        edge2ipoints[:, [0, -1]] = edge
        if p > 1:
            idx = NN + np.arange(p-1)
            edge2ipoints[:, 1:-1] =  (p-1)*index[:, None] + idx
        return edge2ipoints

    face_to_ipoint = edge_to_ipoint


    def node_to_ipoint(self):
        """
        @brief 网格节点到插值点的映射关系
        """
        NN = self.number_of_nodes()
        return np.arange(NN)

    def interpolation_points(self, p: int,
            index=np.s_[:], scale: float=0.3):
        """
        @brief 获取多边形网格上的插值点
        """
        node = self.entity('node')

        if p == 1:
            return node

        gdof = self.number_of_global_ipoints(p)

        GD = self.geo_dimension()
        NN = self.number_of_nodes()
        NE = self.number_of_edges()
        NC = self.number_of_cells()
        start = 0
        ipoint = np.zeros((gdof, GD), dtype=self.ftype)
        ipoint[start:NN, :] = node

        start += NN

        edge = self.entity('edge')
        qf = self.integrator(p+1, etype='edge', qtype='lobatto')
        bcs = qf.quadpts[1:-1, :]
        ipoint[start:NN+(p-1)*NE, :] = np.einsum('ij, ...jm->...im', bcs, node[edge, :]).reshape(-1, GD)
        start += (p-1)*NE

        if p == 2:
            ipoint[start:] = self.entity_barycenter('cell')
            return ipoint

        h = np.sqrt(self.cell_area())[:, None]*scale
        bc = self.entity_barycenter('cell')
        t = np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [0.5, np.sqrt(3)/2]], dtype=self.ftype)
        t -= np.array([0.5, np.sqrt(3)/6.0], dtype=self.ftype)

        tri = np.zeros((NC, 3, GD), dtype=self.ftype)
        tri[:, 0, :] = bc + t[0]*h
        tri[:, 1, :] = bc + t[1]*h
        tri[:, 2, :] = bc + t[2]*h

        bcs = self.multi_index_matrix(p-2)/(p-2)
        ipoint[start:] = np.einsum('ij, ...jm->...im', bcs, tri).reshape(-1, GD)
        return ipoint


    @staticmethod
    def multi_index_matrix(p: int, etype=2):
        """
        @brief 获取三角形上的 p 次的多重指标矩阵

        @param[in] p positive integer

        @return multiIndex  ndarray with shape (ldof, 3)
        """
        if etype in {'cell', 2}:
            ldof = (p+1)*(p+2)//2
            idx = np.arange(0, ldof)
            idx0 = np.floor((-1 + np.sqrt(1 + 8*idx))/2)
            multiIndex = np.zeros((ldof, 3), dtype=np.int_)
            multiIndex[:,2] = idx - idx0*(idx0 + 1)/2
            multiIndex[:,1] = idx0 - multiIndex[:,2]
            multiIndex[:,0] = p - multiIndex[:, 1] - multiIndex[:, 2]
            return multiIndex
        elif etype in {'face', 'edge', 1}:
            ldof = p+1
            multiIndex = np.zeros((ldof, 2), dtype=np.int_)
            multiIndex[:, 0] = np.arange(p, -1, -1)
            multiIndex[:, 1] = p - multiIndex[:, 0]
            return multiIndex

    def shape_function(self, bc: NDArray, p: int) -> NDArray:
        raise NotImplementedError

    def grad_shape_function(self, bc: NDArray, p: int, index=np.s_[:]) -> NDArray:
        raise NotImplementedError

    def uniform_refine(self, n: int=1) -> None:
        raise NotImplementedError

    def integral(self, u, q=3, celltype=False):
        """
        @brief 多边形网格上的数值积分

        @param[in] u 被积函数, 需要两个参数 (x, index)
        @param[in] q 积分公式编号
        """
        node = self.entity('node')
        edge = self.entity('edge')
        edge2cell = self.ds.edge_to_cell()
        NC = self.number_of_cells()

        bcs, ws = self.integrator(q).get_quadrature_points_and_weights()

        bc = self.entity_barycenter('cell')
        tri = [bc[edge2cell[:, 0]], node[edge[:, 0]], node[edge[:, 1]]]

        v1 = node[edge[:, 0]] - bc[edge2cell[:, 0]]
        v2 = node[edge[:, 1]] - bc[edge2cell[:, 0]]
        a = np.cross(v1, v2)/2.0

        pp = np.einsum('ij, jkm->ikm', bcs, tri, optimize=True)
        val = u(pp, edge2cell[:, 0])

        shape = (NC, ) + val.shape[2:]
        e = np.zeros(shape, dtype=np.float64)

        ee = np.einsum('i, ij..., j->j...', ws, val, a, optimize=True)
        np.add.at(e, edge2cell[:, 0], ee)

        isInEdge = (edge2cell[:, 0] != edge2cell[:, 1])
        if np.sum(isInEdge) > 0:
            tri = [
                    bc[edge2cell[isInEdge, 1]],
                    node[edge[isInEdge, 1]],
                    node[edge[isInEdge, 0]]
                    ]
            v1 = node[edge[isInEdge, 1]] - bc[edge2cell[isInEdge, 1]] 
            v2 = node[edge[isInEdge, 0]] - bc[edge2cell[isInEdge, 1]] 
            a = np.cross(v1, v2)/2.0

            pp = np.einsum('ij, jkm->ikm', bcs, tri, optimize=True)
            val = u(pp, edge2cell[isInEdge, 1])
            ee = np.einsum('i, ij..., j->j...', ws, val, a, optimize=True)
            np.add.at(e, edge2cell[isInEdge, 1], ee)

        if celltype is True:
            return e
        else:
            return e.sum(axis=0)

    def error(self, u, v, q=3, celltype=False, power=2):
        """
        @brief 在当前多边形网格上计算误差 \int |u - v|^power dx

        @param[in] u 函数
        @param[in] v 函数
        @param[in] q 积分公式编号
        """

        nu = len(inspect.signature(u).parameters)
        nv = len(inspect.signature(v).parameters)

        assert 1 <= nu <= 2
        assert 1 <= nv <= 2

        if (nu == 1) and (nv == 2):
            def efun(x, index):
                return np.abs(u(x) - v(x, index))**power
        elif (nu == 2) and (nv == 2):
            def efun(x, index):
                return np.abs(u(x, index) - v(x, index))**power
        elif (nu == 1) and (nv == 1):
            def efun(x, index):
                return np.abs(u(x) - v(x))**power
        else:
            def efun(x, index):
                return np.abs(u(x, index) - v(x))**power

        e = self.integral(efun, q, celltype=celltype)
        if isinstance(e, np.ndarray):
            n = len(e.shape) - 1
            if n > 0:
                for i in range(n):
                    e = e.sum(axis=-1)
        if celltype == False:
            e = np.power(np.sum(e), 1/power)
        else:
            e = np.power(np.sum(e, axis=tuple(range(1, len(e.shape)))), 1/power)
        return e

    @classmethod
    def from_one_triangle(cls, meshtype='iso'):
        if meshtype == 'equ':
            node = np.array([
                    [0.0, 0.0],
                    [1.0, 0.0],
                    [0.5, np.sqrt(3)/2]], dtype=np.float_)
        elif meshtype =='iso':
            node = np.array([
                    [0.0, 0.0],
                    [1.0, 0.0],
                    [0.0, 1.0]], dtype=np.float_)
        cell = np.array([[0, 1, 2]],dtype=np.int_)
        return cls(node, cell)

    @classmethod
    def from_one_square(cls):
        node = np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0]],dtype=np.float_)
        cell = np.array([[0, 1, 2, 3]], dtype=np.int_)
        return cls(node, cell)

    @classmethod
    def from_triangle_mesh_by_dual(cls, mesh, bc=True):
        """
        @brief 生成三角形网格的对偶网格，目前默认用三角形的重心做为对偶网格的顶点

        @param mesh
        @param bc bool 如果为真，则对偶网格点为三角形单元重心; 否则为三角形单元外心
        """
        from .TriangleMesh import TriangleMeshWithInfinityNode

        mesh = TriangleMeshWithInfinityNode(mesh, bc=bc)
        pnode, pcell, pcellLocation = mesh.to_polygonmesh()
        return cls(pnode, pcell, pcellLocation)

    @classmethod
    def from_one_pentagon(cls):
        pi = np.pi
        node = np.array([
            (0.0, 0.0),
            (np.cos(2/5*pi), -np.sin(2/5*pi)),
            (np.cos(2/5*pi)+1, -np.sin(2/5*pi)),
            ( 2*np.cos(1/5*pi), 0.0),
            (np.cos(1/5*pi), np.sin(1/5*pi))],dtype=np.float_)
        cell = np.array([0, 1, 2, 3, 4], dtype=np.int_)
        cellLocation = np.array([0, 5], dtype=np.int_)
        return cls(node, cell, cellLocation)

    @classmethod
    def from_one_hexagon(cls):
        node = np.array([
            [0.0, 0.0],
            [1/2, -np.sqrt(3)/2],
            [3/2, -np.sqrt(3)/2],
            [2.0, 0.0],
            [3/2, np.sqrt(3)/2],
            [1/2, np.sqrt(3)/2]], dtype=np.float_)
        cell = np.array([0, 1, 2, 3, 4, 5], dtype=np.int_)
        cellLocation = np.array([0, 6], dtype=np.int_)
        return cls(node, cell ,cellLocation)

    @classmethod
    def from_mixed_polygon(cls):
        """
        @brief 生成一个包含多种类型多边形的网格，方便测试相关的程序
        """
        pass

    @classmethod
    def from_mesh(cls, mesh: Mesh2d):
        node = mesh.entity('node')
        cell = mesh.entity('cell')
        NC = mesh.number_of_cells()
        NV = cell.shape[1]
        cellLocation = np.arange(0, (NC+1)*NV, NV)
        return cls(node, cell.reshape(-1), cellLocation)

    @classmethod
    def from_quadtree(cls, quadtree):
        node, cell, cellLocation = quadtree.to_pmesh()
        return cls(node, cell, cellLocation)


    @classmethod
    def distorted_concave_rhombic_quadrilaterals_mesh(cls, box=[0, 1, 0, 1], nx=10, ny=10, ratio=0.618):
        """
        @brief 虚单元网格，矩形内部包含一个菱形，两者共用左下和右上的节点

        @param box 网格所占区域
        @param nx 沿 x 轴方向剖分段数
        @param ny 沿 y 轴方向剖分段数
        @param ratio 矩形内部菱形的大小比例
        """
        from .QuadrangleMesh import QuadrangleMesh
        from .UniformMesh2d import UniformMesh2d

        hx = (box[1] - box[0]) / nx
        hy = (box[3] - box[2]) / ny

        mesh0 = UniformMesh2d([0, nx, 0, ny], h=(hx, hy), origin=(box[0], box[2]))
        node0 = mesh0.entity("node")
        cell0 = mesh0.entity("cell")[:, [0, 2, 3, 1]]
        mesh = QuadrangleMesh(node0, cell0)

        edge = mesh.entity("edge")
        node = mesh.entity("node")
        cell = mesh.entity("cell")
        NC = mesh.number_of_cells()
        NN = mesh.number_of_nodes()

        node_append1 = node[cell[:, 3]] * (1-ratio) + node[cell[:, 1]] * ratio
        node_append2 = node[cell[:, 3]] * ratio + node[cell[:, 1]] * (1-ratio)
        new_node = np.vstack((node, node_append1, node_append2))

        cell = np.tile(cell, (3, 1))
        idx1 = np.arange(NN, NN + NC)
        idx2 = np.arange(NN + NC, NN + 2 * NC)
        cell[0:NC, 3] = idx1
        cell[NC:2 * NC, 1] = idx1
        cell[NC:2 * NC, 3] = idx2
        cell[2 * NC:3 * NC, 1] = idx2

        return PolygonMesh(new_node, cell)


    @classmethod
    def nonconvex_octagonal_mesh(cls, box=[0, 1, 0, 1], nx=10, ny=10):
        """
        @brief 虚单元网格，矩形网格的每条内部边上加一个点后形成的八边形网格

        @param box 网格所占区域
        @param nx 沿 x 轴方向剖分段数
        @param ny 沿 y 轴方向剖分段数
        """
        from .QuadrangleMesh import QuadrangleMesh
        from .UniformMesh2d import UniformMesh2d

        hx = (box[1] - box[0]) / nx
        hy = (box[3] - box[2]) / ny
        NN = (nx + 1) * (ny + 1)

        mesh0 = UniformMesh2d([0, nx, 0, ny], h=(hx, hy), origin=(box[0], box[2]))
        node0 = mesh0.entity("node")
        cell0 = mesh0.entity("cell")[:, [0, 2, 3, 1]]
        mesh = QuadrangleMesh(node0, cell0)

        edge = mesh.entity("edge")
        node = mesh.entity("node")
        cell = mesh.entity("cell")
        NE = mesh.number_of_edges()
        NC = mesh.number_of_cells()

        cell2edge = mesh.ds.cell_to_edge()
        isbdedge = mesh.ds.boundary_edge_flag()
        isbdcell = mesh.ds.boundary_cell_flag()

        nie = np.sum(~isbdedge)
        hx = 1 / nx
        hy = 1 / ny
        newnode = np.zeros((NN + nie, 2), dtype=np.float_)
        newnode[:NN] = node
        newnode[NN:] = 0.5 * node[edge[~isbdedge, 0]] + 0.5 * node[edge[~isbdedge, 1]]
        newnode[NN: NN + (nx - 1) * ny] = newnode[NN: NN + (nx - 1) * ny] + np.array([[0.2 * hx, 0.1 * hy]])
        newnode[NN + (nx - 1) * ny:] = newnode[NN + (nx - 1) * ny:] + np.array([[0.1 * hx, 0.2 * hy]])

        edge2newnode = -np.ones(NE, dtype=np.int_)
        edge2newnode[~isbdedge] = np.arange(NN, newnode.shape[0])
        newcell = np.zeros((NC, 8), dtype=np.int_)
        newcell[:, ::2] = cell
        newcell[:, 1::2] = edge2newnode[cell2edge]

        flag = newcell > -1
        num = np.zeros(NC + 1, dtype=np.int_)
        num[1:] = np.sum(flag, axis=-1)
        newcell = newcell[flag]
        cellLocation = np.cumsum(num)

        return PolygonMesh(newnode, newcell, cellLocation)



    def cell_area(self, index=None):
        #TODO: 3D Case
        NC = self.number_of_cells()
        node = self.node
        edge = self.ds.edge
        edge2cell = self.ds.edge2cell
        isInEdge = (edge2cell[:, 0] != edge2cell[:, 1])
        w = np.array([[0, -1], [1, 0]], dtype=self.itype)
        v= (node[edge[:, 1], :] - node[edge[:, 0], :])@w
        val = np.sum(v*node[edge[:, 0], :], axis=1)
        a = np.bincount(edge2cell[:, 0], weights=val, minlength=NC)
        a+= np.bincount(edge2cell[isInEdge, 1], weights=-val[isInEdge], minlength=NC)
        a /=2
        return a

PolygonMesh.set_ploter('polygon2d')


class PolygonMeshDataStructure(Mesh2dDataStructure):
    TD: int = 2
    def __init__(self, NN: int, cell: NDArray, cellLocation: NDArray, topdata=None):
        self.NN = NN
        self._cell = cell
        self.cellLocation = cellLocation
        self.itype = cell.dtype

        if topdata is None:
            self.construct()
        else:
            self.edge = topdata[0]
            self.edge2cell = topdata[1]

    def reinit(self, NN: int, cell: NDArray, cellLocation: NDArray):
        self.NN = NN
        self._cell = cell
        self.itype = cell.dtype
        self.cellLocation = cellLocation
        self.construct()

    def number_of_cells(self) -> int:
        return self.cellLocation.shape[0] - 1

    def number_of_vertices_of_cells(self):
        return self.cellLocation[1:] - self.cellLocation[0:-1]

    number_of_edges_of_cells = number_of_vertices_of_cells
    number_of_faces_of_cells = number_of_vertices_of_cells

    def total_edge(self) -> NDArray:
        totalEdge = np.zeros((self._cell.shape[0], 2), dtype=self.itype)
        totalEdge[:, 0] = self._cell
        totalEdge[:-1, 1] = self._cell[1:]
        totalEdge[self.cellLocation[1:] - 1, 1] = self._cell[self.cellLocation[:-1]]
        return totalEdge

    total_face = total_edge

    def construct(self):
        totalEdge = self.total_edge()
        _, i0, j = np.unique(np.sort(totalEdge, axis=1),
                return_index=True,
                return_inverse=True,
                axis=0)
        NE = i0.shape[0]
        self.edge2cell = np.zeros((NE, 4), dtype=self.itype)

        i1 = np.zeros(NE, dtype=self.itype)
        i1[j] = np.arange(len(self._cell))

        self.edge = totalEdge[i0]

        NV = self.number_of_vertices_of_cells()
        NC = self.number_of_cells()
        cellIdx = np.repeat(range(NC), NV)

        localIdx = ranges(NV)

        self.edge2cell[:, 0] = cellIdx[i0]
        self.edge2cell[:, 1] = cellIdx[i1]
        self.edge2cell[:, 2] = localIdx[i0]
        self.edge2cell[:, 3] = localIdx[i1]

    @property
    def cell(self):
        return np.hsplit(self._cell, self.cellLocation[1:-1])

    ### cell ###

    def cell_to_node(self):
        """
        @brief 单元到节点的拓扑关系，默认返回稀疏矩阵
        @note 当获取单元实体时，请使用 `mesh.entity('cell')` 接口
        """
        NN = self.number_of_nodes()
        NC = self.number_of_cells()

        NV = self.number_of_vertices_of_cells()
        I = np.repeat(range(NC), NV)
        J = self._cell

        val = np.ones(len(self._cell), dtype=np.bool_)
        cell2node = csr_matrix((val, (I, J)), shape=(NC, NN), dtype=np.bool_)
        return cell2node

    def cell_to_edge(self) -> NDArray:
        raise NotImplementedError

    cell_to_face = cell_to_edge

    def edge_to_cell(self, return_sparse=False):
        NE = self.number_of_edges()
        NC = self.number_of_cells()
        edge2cell = self.edge2cell
        if return_sparse:
            val = np.ones(NE, dtype=np.bool_)
            edge2cell = coo_matrix((val, (range(NE), edge2cell[:, 0])), shape=(NE, NC), dtype=np.bool_)
            edge2cell+= coo_matrix((val, (range(NE), edge2cell[:, 1])), shape=(NE, NC), dtype=np.bool_)
            return edge2cell.tocsr()
        else:
            return edge2cell

    face_to_cell = edge_to_cell
