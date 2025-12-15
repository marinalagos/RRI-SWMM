# RRI-SWMM

# Node mapping
Before coupling both models it is necessary to map every SWMM node to a RRI cell. The 'node2cell' module can be used.
Two files are needed: one containing the coordinates of the SWMM nodes, and the other should be one of the topo files of the RRI model.
The names of those files should be set on the 'set_node2cell.txt' file. After executing 'node2cell.exe' the 'node_ij.txt' will be created. That files contains the mapping results.