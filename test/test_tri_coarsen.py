import numpy as np
import matplotlib.pyplot as plt

from fealpy.functionspace.lagrange_fem_space import LagrangeFiniteElementSpace
from fealpy.mesh import Tritree
from fealpy.mesh import TriangleMesh


class Estimator:
    def __init__(self, rho, mesh, theta, beta):
        self.mesh = mesh
        self.rho = rho
        self.theta = theta
        self.beta = beta
        self.area = mesh.entity_measure('cell')
        self.compute_eta()
        self.maxeta = np.max(self.eta)

    def compute_eta(self):
        mesh = self.mesh
        cell = mesh.entity('cell')
        Dlambda = mesh.grad_lambda()
        grad = np.einsum('ij, ijm->im', self.rho[cell], Dlambda)
        self.eta = np.sqrt(np.sum(grad**2, axis=1)*self.area)
        return self.eta
    def update(self, rho, mesh, smooth=True):
        self.rho = rho
        self.mesh = mesh
        self.area = mesh.entity_measure('cell')
        self.smooth_rho()
        self.compute_eta()

    def smooth_rho(self):
        '''
        smooth the rho
        '''
        mesh = self.mesh
        cell = mesh.entity('cell')
        node2cell = mesh.ds.node_to_cell()
        inva = 1/self.area
        s = node2cell@inva
        for i in range(2):
            crho = (self.rho[cell[:, 0]] + self.rho[cell[:, 1]] + self.rho[cell[:, 2]])/3.0
            self.rho = np.asarray(node2cell@(crho*inva))/s

    def is_uniform(self):
        stde = np.std(self.eta)/self.maxeta
        print('The current relative std of eta is ', stde)
        if stde < 0.05:
            return True
        else:
            return False

def f1(p):
    x = p[..., 0]
    y = p[..., 1]
    val = np.exp(5*(x**2 + y**2))/np.exp(10)
    return val

def f2(p):
    x = p[..., 0]
    y = p[..., 1]
    val = np.exp(5*(x**2 + (y-1)**2))/np.exp(10)
    return val

node = np.array([
    (0, 0),
    (1, 0),
    (1, 1),
    (0, 1)], dtype=np.float)

cell = np.array([
    (1, 2, 0), 
    (3, 0, 2)], dtype=np.int)
mesh = TriangleMesh(node, cell)
mesh.uniform_refine(4)

femspace = LagrangeFiniteElementSpace(mesh, p=1) 
uI = femspace.interpolation(f1)

estimator = Estimator(uI[:], mesh, 0.3, 0.3)

fig = plt.figure()
axes = fig.gca() 
mesh.add_plot(axes, cellcolor=estimator.eta, showcolorbar=True)

node = mesh.entity('node')
cell = mesh.entity('cell')
tmesh = Tritree(node, cell)
tmesh.adaptive_refine(estimator)

mesh = estimator.mesh
fig = plt.figure()
axes = fig.gca() 
mesh.add_plot(axes, cellcolor=estimator.eta, showcolorbar=True)

femspace = LagrangeFiniteElementSpace(mesh, p=1)
uI = femspace.interpolation(f2)
estimator = Estimator(uI[:], mesh, 0.3, 0.5)

eta = estimator.compute_eta()
isMarkedCell = tmesh.coarsen_marker(eta, 0.3, "COARSEN")
tmesh.coarsen(isMarkedCell)

fig = plt.figure()
axes = fig.gca()
tmesh.add_plot(axes)

plt.show()



