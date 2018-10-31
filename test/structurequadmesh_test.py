
import numpy as np
import matplotlib.pyplot as plt
import sys

#from fealpy.mesh.StructureQuadMesh import StructureQuadMesh
from fealpy.mesh.litest_quadmesh import StructureQuadMesh1
box = [0, 1, 0, 1]
n = 8
qmesh = StructureQuadMesh1(box, nx, ny)
cell2cell = qmesh.ds.cell_to_cell()
print('cell2cell',cell2cell)

NN = qmesh.number_of_nodes()
NE = qmesh.number_of_edges()
NC = qmesh.number_of_cells()

#a = cell2cell[:NC:n,0]
#print('a',a)

X = np.zeros(NE + NC, dtype=np.float)

I = np.arange(NC, dtype=np.int)
J = I

fig = plt.figure()
axes = fig.gca()
qmesh.add_plot(axes)
qmesh.find_node(axes, showindex=True)
qmesh.find_edge(axes, showindex=True)
qmesh.find_cell(axes, showindex=True)
plt.show()
