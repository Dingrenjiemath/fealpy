import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from types import ModuleType

from .mesh_tools import unique_row, find_node, find_entity, show_mesh_1d
from .HalfEdgeMesh import HalfEdgeMesh

class HalfEdgeDomain():
    def __init__(self, vertices, halfedge, NS=None, fixed=None):
        """
        Parameters
        ---------- 
        vertices :  np.ndarray, (NV, GD)
        halfedge :  np.ndarray, (NE, 6)
            halfedge[i, 0] : 指向的区域顶点编号
            halfedge[i, 1] : 左手边的子区域编号
                 0: 表示外部无界区域
                -n: n >= 1, 表示编号为 -n 洞
                 n: n >= 1, 表示编号为  n 的内部子区域
            halfedge[i, 2] : 下一个半边编号
            halfedge[i, 3] : 前一个半边编号
            halfedge[i, 4] : 相对的半边编号
            halfedge[i, 5] : 主半边标记, 1 : 主半边, 0: 次半边.
                 这里还约定, 如果两个相对的半边, 它们左手边的子区域, 
                 如果有一个子区域的编号大于 0, 另一个小于等于 0, 则
                 子区域编号大于 0 的半边为主半边. 如果两个相对半边的
                 子区域编号都大于 0, 则任取一个半边作为主半边.
        """

        self.vertices = vertices # 区域的顶点
        self.halfedge = halfedge #　区域的半边数据结构
        self.GD = vertices.shape[1]
        if NS is None:
            self.NS = len(set(halfedge[:, 1]))
        else:
            self.NS = NS # 子区域的个数
        
        self.NV = len(vertices) # 区域顶点的个数
        self.NE = len(halfedge) # 区域半边的个数
        
        # 默认初始顶点都是固定点
        self.fixed = np.ones(self.NV, dtype=np.bool) if fixed is None else fixed

        self.itype = halfedge.dtype
        self.ftype = vertices.dtype

    def geo_dimension(self):
        return self.vertices.shape[1]

    def top_dimension(self):
        return 2

    def to_halfedgemesh(self):
        node = self.vertices.copy()
        halfedge = self.halfedge.copy()
        subdomain, _, j = np.unique(halfedge[:, 1],
            return_index=True, return_inverse=True)
        halfedge[:, 1] = j
        mesh = HalfEdgeMesh(node, subdomain, halfedge)
        return mesh

    def voronoi_mesh(self, n=4, c=0.618, theta=100):
        self.boundary_uniform_refine(n=n)
        NN = self.NV
        node = self.vertices
        halfedge = self.halfedge
    

        # 这里假设所有边的尺寸是一样的
        # 进一步的算法改进中，这些尺寸应该是自适应的
        # 顶点处的半径应该要平均平均一下
        

        idx0 = halfedge[halfedge[:, 3], 0]
        idx1 = halfedge[:, 0]
        v = node[idx1] - node[idx0]
        h = np.sqrt(np.sum(v**2, axis=-1))
        r = np.zeros(NN, dtype=self.ftype)
        n = np.zeros(NN, dtype=self.itype)
        np.add.at(r, idx0, h)
        np.add.at(r, idx1, h)
        np.add.at(n, idx0, 1)
        np.add.at(n, idx1, 1)
        r /= n
        r *= c
        w = np.array([[0, 1], [-1, 0]])

        # 修正角点相邻点的半径， 如果角点的角度小于 theta 的
        # 这里假设角点相邻的节点， 到角点的距离相等
        isFixed = self.fixed[halfedge[:, 0]]
        idx, = np.nonzero(isFixed)
        pre = halfedge[idx, 3]
        nex = halfedge[idx, 2]

        p0 = node[halfedge[pre, 0]]
        p1 = node[halfedge[idx, 0]]
        p2 = node[halfedge[nex, 0]]

        v0 = p2 - p1
        v1 = p0 - p1
        l0 = np.sqrt(np.sum(v0**2, axis=-1))
        l1 = np.sqrt(np.sum(v1**2, axis=-1))
        c = np.cross(v0, v1)/l0/l1
        a = np.arcsin(c)
        a[c < 0] += 2*np.pi
        a = np.degrees(a)
        isCorner = a < theta
        idx = idx[isCorner]

        v2 = (v0[isCorner] + v1[isCorner])/2
        v2 /= np.sqrt(np.sum(v2**2, axis=-1, keepdims=True))
        v2 *= r[halfedge[idx, 0], None] 
        p = node[halfedge[idx, 0]] + v2
        r[halfedge[pre[idx], 0]] = np.sqrt(np.sum((p - p0[idx])**2, axis=-1))
        r[halfedge[nex[idx], 0]] = np.sqrt(np.sum((p - p2[idx])**2, axis=-1))

        center = (node[idx0] + node[idx1])/2
        r0 = r[idx0]
        r1 = r[idx1]
        c0 = 0.5*(r0**2 - r1**2)/h**2
        c1 = 0.5*np.sqrt(2*(r0**2 + r1**2)/h**2 - (r0**2 - r1**2)**2/h**4 - 1)
        bnode = center + c0.reshape(-1, 1)*v + c1.reshape(-1, 1)*(v@w) 

        # 把一些生成的点合并掉, 这里只检查当前半边和下一个半边的生成的点
        # 这里也假设很近的点对是孤立的. 

        idx2 = halfedge[:, 2]
        v0 = bnode - node[idx1]
        v1 = bnode[idx2] - node[idx1]

        d = np.sqrt(np.sum((v0-v1)**2, axis=-1))
        isNearSite = d < 0.5*r1 

        v = v0[isNearSite] + v1[isNearSite]
        l = np.sqrt(np.sum(v**2, axis=-1, keepdims=True))
        v /= l
        v *= r1[isNearSite, None]
        bnode[isNearSite] = node[idx1[isNearSite]] + v 

        NB = bnode.shape[0]
        idx = np.arange(NB)
        idx[idx2[isNearSite]] = idx[isNearSite]

        isKeepNode = np.zeros(NB, dtype=np.bool)
        isKeepNode[idx] = True
        idxmap = np.zeros(NB, dtype=np.int)
        idxmap[isKeepNode] = range(isKeepNode.sum())

        return bnode[isKeepNode], idxmap[idx] 

    def advance_triangle_mesh(self):

        # 初始网格点的数量
        NN = self.NV
        # 初始半边数
        NE = self.NE

        # 估计网格点和半边的数量, 分配空间
        node = np.zeros((10000, 2), dtype=self.ftype)
        halfedge = np.zeros((20000, 6), dtype=self.itype)

        node[:NN] = self.vertices
        halfedge[:NE] = self.halfedge
        
        
    def boundary_adaptive_refine(self, isMarkedHEdge,
        vertices=None, halfedge=None, edgecenter=None):

        inplace = True
        itype = self.itype

        if (vertices is not None) and (halfedge is not None):
            inplace = False
            itype = halfedge.dtype

        if inplace:
            NE = self.NE
            NV = self.NV
            vertices = self.vertices
            halfedge = self.halfedge
        else:
            NE = len(halfedge)
            NV = len(vertices)

        isMarkedHEdge[halfedge[isMarkedHEdge, 4]] = True
        isMainHEdge = (halfedge[:, 5] == 1) # 主半边标记
        flag0 = isMainHEdge & isMarkedHEdge
        idx = halfedge[flag0, 4]
        if edgecenter is None:
            ec = (vertices[halfedge[flag0, 0]] + vertices[halfedge[idx, 0]])/2
        else:
            ec = edgecenter

        NE1 = 2*len(ec)

        halfedge1 = np.zeros((NE1, 6), dtype=itype)
        flag1 = isMainHEdge[isMarkedHEdge] # 标记加密边中的主半边
        halfedge1[flag1, 0] = range(NV, NV+NE1//2) # 新的节点编号
        idx0 = np.argsort(idx) # 当前边的对偶边的从小到大进行排序
        halfedge1[~flag1, 0] = halfedge1[flag1, 0][idx0] # 按照排序

        halfedge1[:, 1] = halfedge[isMarkedHEdge, 1]
        halfedge1[:, 3] = halfedge[isMarkedHEdge, 3] # 前一个 
        halfedge1[:, 4] = halfedge[isMarkedHEdge, 4] # 对偶边
        halfedge1[:, 5] = halfedge[isMarkedHEdge, 5] # 主边标记

        halfedge[isMarkedHEdge, 3] = range(NE, NE + NE1)
        idx = halfedge[isMarkedHEdge, 4] # 原始对偶边
        halfedge[isMarkedHEdge, 4] = halfedge[idx, 3]  # 原始对偶边的前一条边是新的对偶边

        halfedge = np.r_['0', halfedge, halfedge1]
        halfedge[halfedge[:, 3], 2] = range(NE+NE1)

        if inplace: 
            self.halfedge = halfedge
            self.vertices = np.r_['0', vertices, ec] 
            self.fixed = np.r_['0', 
                    self.fixed,
                    np.zeros_like(ec[:, 0], dtype=np.bool)] 
            self.NV += NE1//2
            self.NE += NE1 
        else:
            return ec, halfedge

    def boundary_uniform_refine(self, n=1, vertices=None, halfedge=None):
        inplace = True
        itype = self.itype
        ftype = self.ftype

        if (vertices is not None) and (halfedge is not None):
            inplace = False
            itype = halfedge.dtype
            ftype = vertices.dtype

        for i in range(n):
            if inplace:
                NE = self.NE
                NV = self.NV
                vertices = self.vertices
                halfedge = self.halfedge
            else:
                NE = len(halfedge)
                NV = len(vertices)
            
            # 求中点
            isMainHEdge = halfedge[:, 5] == 1
            idx = halfedge[isMainHEdge, 4]
            ec = (vertices[halfedge[isMainHEdge, 0]] + vertices[halfedge[idx, 0]])/2

            #细分边
            halfedge1 = np.zeros((NE, 6), dtype=itype)
            halfedge1[isMainHEdge, 0] = range(NV, NV + NE//2) # 新的节点编号
            idx0 = np.argsort(idx) # 当前边的对偶边的从小到大进行排序
            halfedge1[~isMainHEdge, 0] = halfedge1[isMainHEdge, 0][idx0] # 按照排序

            halfedge1[:, 1] = halfedge[:, 1]
            halfedge1[:, 3] = halfedge[:, 3] # 前一个 
            halfedge1[:, 4] = halfedge[:, 4] # 对偶边
            halfedge1[:, 5] = halfedge[:, 5] # 主边标记

            halfedge[:, 3] = range(NE, 2*NE)
            idx = halfedge[:, 4] # 原始对偶边
            halfedge[:, 4] = halfedge[idx, 3]  # 原始对偶边的前一条边是新的对偶边

            vertices = np.r_['0', vertices, ec]
            halfedge = np.r_['0', halfedge, halfedge1]
            halfedge[halfedge[:, 3], 2] = range(2*NE)

            if inplace: 
                self.halfedge = halfedge
                self.vertices = vertices 
                self.fixed = np.r_['0', 
                        self.fixed, 
                        np.zeros_like(ec[:, 0], dtype=np.bool)]
                self.NV += NE//2
                self.NE *= 2
            else:
                return vertices, halfedge

    def number_of_vertices(self):
        return self.NV
    
    def number_of_halfedges(self):
        return self.NE
    
    def number_of_subdomains(self):
        return self.NS

    def create_finite_voronoi(self, points):
        """
        给定一组点, 生成相应 finite  Voronoi Regions 
        """
        from scipy.spatial import Voronoi
        from scipy.spatial import KDTree

        itype = self.itype
        ftype = self.ftype

        NG = len(points) # 生成子的个数
        voronoi = Voronoi(points)
        tree = KDTree(points)

        rp = voronoi.ridge_points
        rv = np.array(voronoi.ridge_vertices)
        nv = len(voronoi.vertices)

        rp[0, 0], rp[0, 1] = rp[0, 1], rp[0, 0]

        # 无限边转化为有限边
        w = np.array([(0,-1),(1,0)])
        isInfVertices = (rv[:, 0] == -1)
        nn = isInfVertices.sum()
        ve = np.zeros((nv+nn, 2), dtype=ftype)
        ve[:nv] = voronoi.vertices
        ve[nv:] += ve[rv[isInfVertices, 1]]
        ve[nv:] += 2*(points[rp[isInfVertices, 1]] - points[rp[isInfVertices, 0]])@w
        rv[isInfVertices, 0] = range(nv, nv+nn)

        edge = rp[isInfVertices]
        val = np.ones(nn, dtype=np.bool)
        m0 = csr_matrix((val, (range(nn), edge[:, 0])), shape=(nn, NG), dtype=np.bool)
        m1 = csr_matrix((val, (range(nn), edge[:, 1])), shape=(nn, NG), dtype=np.bool)
        _, nex = (m0*m1.T).nonzero()
        _, pre = (m1*m0.T).nonzero()

        # 建立 generator 的邻接关系矩阵
        neighbor  = coo_matrix((rv[:, 0] + 1, (rp[:, 0], rp[:, 1])), shape=(NG, NG))
        neighbor += coo_matrix((rv[:, 1] + 1, (rp[:, 1], rp[:, 0])), shape=(NG, NG))
        neighbor = neighbor.tocsr()

        # 建立半边数据结构
        ne = len(rv)
        NE = 2*ne + 2*nn
        mid = ne + nn
        halfedge = np.zeros((NE, 6), dtype=itype)
        halfedge[:ne, 0] = rv[:, 1]
        halfedge[:ne, 1] = rp[:, 0]
        halfedge[:ne, 4] = range(mid, mid+ne)
        halfedge[:ne, 5] = 1

        halfedge[ne:mid, 0] = np.arange(nv, nv+nn) 
        halfedge[ne:mid, 1] = rp[isInfVertices, 0] 
        halfedge[ne:mid, 4] = range(mid+ne, NE)
        halfedge[ne:mid, 5] = 1

        halfedge[mid:mid+ne, 0] = rv[:, 0]
        halfedge[mid:mid+ne, 1] = rp[:, 1]
        halfedge[mid:mid+ne, 4] = range(ne)

        halfedge[mid+ne:, 0] = halfedge[ne:mid, 0][pre] 
        halfedge[mid+ne:, 1] = NG
        halfedge[mid+ne:, 4] = range(ne, mid)

        # 建立连接关系
        node = ve
        NN = node.shape[0]
        NC = NG
        flag =  np.ones(NE, dtype=np.bool)
        idx = np.arange(NE)
        node2halfedge = np.zeros((NN, 3), dtype=itype)
        node2halfedge[halfedge[:, 0], 0] = idx 
        flag[node2halfedge[:, 0]] = False
        node2halfedge[halfedge[flag, 0], 1] = idx[flag]
        flag[node2halfedge[:, 1]] = False
        node2halfedge[halfedge[flag, 0], 2] = idx[flag]

        idx0 = halfedge[node2halfedge[:, 0], 4]
        idx1 = halfedge[node2halfedge[:, 1], 4]
        idx2 = halfedge[node2halfedge[:, 2], 4]

        flag = halfedge[node2halfedge[:, 0], 1] == halfedge[idx1, 1]
        halfedge[node2halfedge[flag, 0], 2] = idx1[flag]
        flag = halfedge[node2halfedge[:, 1], 1] == halfedge[idx0, 1]
        halfedge[node2halfedge[flag, 1], 2] = idx0[flag]

        flag = halfedge[node2halfedge[:, 0], 1] == halfedge[idx2, 1]
        halfedge[node2halfedge[flag, 0], 2] = idx2[flag]
        flag = halfedge[node2halfedge[:, 2], 1] == halfedge[idx0, 1]
        halfedge[node2halfedge[flag, 2], 2] = idx0[flag]

        flag = halfedge[node2halfedge[:, 1], 1] == halfedge[idx2, 1]
        halfedge[node2halfedge[flag, 1], 2] = idx2[flag]
        flag = halfedge[node2halfedge[:, 2], 1] == halfedge[idx1, 1]
        halfedge[node2halfedge[flag, 2], 2] = idx1[flag]

        mesh = HalfEdgeMesh(node, halfedge, NC)
        return mesh 



    def create_voronoi_1(self, points):
        """
        给定一组点, 生成相应 Clipped  Voronoi Regions 
        """
        from scipy.spatial import Voronoi
        from scipy.spatial import KDTree

        itype = self.itype
        ftype = self.ftype

        NG = len(points) # 生成子的个数
        voronoi = Voronoi(points)
        tree = KDTree(points)

        rp = voronoi.ridge_points
        rv = voronoi.ridge_vertices
        nv = len(voronoi.vertices)

        # 无限边转化为有限边
        w = np.array([(0,-1),(1,0)])
        isInfVertices = (rv[:, 0] == -1)
        nn = isInfVertices.sum()
        ve = np.zeros((nv+nn, 2), dtype=ftype)
        ve[:nv] = voronoi.vertices
        ve[nv:] += ve[rv[isInfVertices, 1]]
        ve[nv:] += 3*(points[rp[isInfVertices, 1]] - points[rp[isInfVertices, 0]])@w
        rv[isInfVertices, 0] = range(nv, nv+nn)

        # 建立 generator 的邻接关系矩阵
        neighbor  = coo_matrix((rv[:, 0] + 1, (rp[0], rp[1])), shape=(NG, NG))
        neighbor += coo_matrix((rv[:, 1] + 1, (rp[1], rp[0])), shape=(NG, NG))
        neighbor = neighbor.tocsr()

        # 分配空间
        vertices = np.zeros((100, 2), dtype=ftype)
        gindex = np.zeros(100, dtype=itype)
        end = self.NV     # 初始节点的个数 
        vertices[:end] = self.vertices
        tmp, gindex[:end] = tree.query(vertices[:end])
        halfedge1 = self.halfedge.copy()

        # 自适应加密边界, 直到相邻边界点所属的 Voronoi Region 相同或者相邻
        while True:
            NE = len(halfedge1)
            isMainHEdge = (halfedge1[:, 5] == 1)

            e0 = halfedge1[halfedge1[isMainHEdge, 3], 0]
            e1 = halfedge1[isMainHEdge, 0]

            d0 = neighbor[gindex[e0], gindex[e1]]
            d1 = neighbor[gindex[e1], gindex[e0]]
            isNGenerator =  d0 > 0 # 相邻生成子标记
            if np.any(isNGenerator): 
                # 判断生成子是否真的相邻
                p0 = vertices[e0[isNGenerator]]
                p1 = vertices[e1[isNGenerator]]
                v0 = ve[d0[isNGenerator]-1]
                v1 = ve[d1[isNGenerator]-1]
                isIntersect = self.is_intersect(p0, p1, v0, v1)
                isNGenerator[~isIntersect] = False

            isNotSGenerator = (gindex[e0] != gindex[e1])
            isMarkedHEdge = np.zeros(NE, dtype=np.bool)
            isMarkedHEdge[isMainHEdge][~isNGenerator & isNotSGenerator] =True
            if np.any(isMarkedHEdge):
                nn = isMarkedHEdge.sum()//2
                vertices[end:end+nn], halfedge1 = self.halfedge_adaptive_refine(
                    isMarkedHEdge, vertices=vertices, halfedge=halfedge1)
                gindex[end:end+nn] = tree.query(vertices[end:end+nn])
                end += nn
            else:
                break

        # 计算边界与 Voronoi Region 的交点
        isMainHEdge = halfedge1[:, 5] == 1
        e0 = halfedge1[halfedge1[isMainHEdge, 3], 0]
        e1 = halfedge1[isMainHEdge, 0]

        d0 = neighbor[gindex[e0], gindex[e1]]
        d1 = neighbor[gindex[e1], gindex[e0]]
        isNotSGenerator = (gindex[e0] != gindex[e1])

        p0 = vertices[e0[isNotSGenerator]]
        p1 = vertices[e1[isNotSGenerator]]
        v0 = ve[d0[isNotSGenerator]-1]
        v1 = ve[d1[isNotSGenerator]-1]

        isIntersect, ec = self.is_intersect(p0, p1, v0, v1, returnin=True)
        NE = len(halfedge1)
        isMarkedHEdge = np.zeros(NE, dtype=np.bool)
        isMarkedHEdge[isMainHEdge][isNotSGenerator] =True
        nn = isMarkedHEdge.sum()//2
        vertices[end:end+nn], halfedge1 = self.halfedge_adaptive_refine(
            isMarkedHEdge, vertices=vertices, halfedge=halfedge1, 
            edgecenter=ec)
        end += nn

        # 生成半边网格, 注意这里可以暂时不需要生成:下一个和上一个半边的信息

        node = np.r_['0', vertices[:end], ve]
        halfedge = np.r_['0']

        mesh = HalfEdgeMesh()
        return mesh

    def is_intersect(self, p0, p1, v0, v1, returnin=False):
        ftype = p0.dtype
        s = p1 - p0
        r = v1 - v0
        v = v0 - p1
        n = len(s)

        c0 = np.cross(r, s)
        c1 = np.cross(v, r)
        c2 = np.cross(v, s)

        isColinear = (np.abs(c0) == 0.0) & (np.abs(c1) == 0.0)
        isParallel = (np.abs(c0) == 0.0) & (np.abs(c1) != 0.0)

        flag = (~isColinear) & (~isParallel)
        t = np.zeros(n, dtype=ftype)
        u = np.zeros(n, dtype=ftype)

        t[flag] = c2[flag]/c0[flag]
        u[flag] = c1[flag]/c0[flag] 

        isIntersect = flag & t >= 0.0 & t <= 1.0 & u >= 0.0 & u <=1.0
        if returnin:
            return isIntersect, p0 + s*t.reshape(-1, 1)
        else:
            return isIntersect
