import math
from pyswmm import Simulation, Nodes, Links
from pathlib import Path
from read_inp import inp2df
import pandas as pd
import numpy as np
import re
import warnings

def get_effective_hs(hs):
    if hs <= 0:
        he = hs
    else:
        if hs <= 0.70:
            sup = 0.05 * hs / 0.70
        elif hs < 5.0:
            sup = 0.05 + (1-0.05)/(5-0.70) * (hs - 0.70)
        else:
            sup = 1.0

        he = hs/sup

    return he

def get_associated_lengths(inp_path):
    """
    Compute the cumulative lengths of conduits and channels associated with each node.
    
    For each node, sums half the length of each connected link, separating conduits and channels.

    Args:
        inp_path (str): Path to the SWMM .inp file.

    Returns:
        dict: Keys are node IDs, values are dicts with 'conduits_length' and 'channels_length' representing the accumulated lengths.
    """

    inp_info = inp2df(inpfile = inp_path, conduits = True)
    links_properties = inp_info['conduits']
    
    sim = Simulation(inputfile = inp_path)
    links = Links(sim)

    nodes_connections = {}

    for link in links:
        lid = link.linkid
        link_length = links_properties.Length[lid]

        for node in link.connections:
            if node not in nodes_connections:
                nodes_connections[node] = {'channels_length': 0.0, 
                                        'conduits_length': 0.0}
            if "conduit" in  lid.lower():
                nodes_connections[node]['conduits_length'] += link_length/2
                
            if ("channel" in  lid.lower()) or ('salida' in  lid.lower()):
                nodes_connections[node]['channels_length'] += link_length/2

    sim.close()

    return nodes_connections

def compute_nodes_inflows(sim, associated_lengths, surface_depths, inlet_length_proportion=0.05, c_orifice=0.6, c_weir=1.5*np.sqrt(0.3048), orifice_opening_height=0.15, compute_effective_h1 = False):
    """
    Computes inflows (or outflows) for each node based on surface depth and associated link lengths.

    Calculates the contribution from conduits (through orifices) and channels (through weirs) using their respective lengths and hydraulic coefficients. 

    Args:
        sim (Simulation): PySWMM Simulation object.
        associated_lengths (dict): Node-associated semilengths of conduits and channels.
        surface_depths (dict): Node surface depths (h1) values [m].
        inlet_length_proportion (float, optional): Fraction of conduit length used for orifice. Defaults to 0.05.
        c_orifice (float, optional): Orifice dimensionless discharge coefficient. Defaults to 0.6.
        c_weir (float, optional): Weir discharge coefficient [m^0.5/s]. Defaults to 1.84.
        orifice_opening_height (float, optional): Height of the orifice opening [m]. Defaults to 0.05.

    Notes:
        "inlet_length_proportion" example: For a street segment 100 m long with an inlet 
        on each side of 5 m, the inlet_length_proportion would be 0.05.

    Returns:
        dict: Node IDs as keys, inflow values as floats.
    """
    inflows = {}
    g = 9.81              # gravity acceleration [m/s²]

    for node in Nodes(sim):

        # Case A: the node is flooded
        if node.flooding > 0:
            inflows[node.nodeid] = - node.flooding

        # Case B: the node is not flooded
        else:
            # Get surface flow depth
            h1 = surface_depths[node.nodeid] 
            if compute_effective_h1:
                h1 = get_effective_hs(h1)

            # Check if actually is not flooded
            h2 = max(node.head - (node.invert_elevation + node.full_depth), 0.0) # head above ground level
            if h2 > 0:
                print(f"UNEXPECTED BEHAVIOR. FLOODING WAS ZERO. h2: {h2} m")

            # Case B.1: the node is not flooded and there's no water on surface
            if h1 <= 0:
                q = 0.0

            # Case B.2: the node is not flooded and there's some inflow coming from surface
            else:
                # B.2.1. Conduit exchange computation
                l_conduits = associated_lengths[node.nodeid]['conduits_length']
                l_orifice = 2 * inlet_length_proportion * l_conduits  

                if h1 < orifice_opening_height:
                    # weir discharge law
                    Cw_L = c_orifice * l_orifice * math.sqrt(g)
                    q_conduits = Cw_L * h1**(3/2)
                
                else: # h1 >= orifice_opening_height
                    # orifice discharge law
                    he = h1 - orifice_opening_height/2
                    q_conduits = c_orifice * l_orifice * orifice_opening_height * math.sqrt(2 * g * he)

                # B.2.2. Channel exchange computation
                l_channels = associated_lengths[node.nodeid]['channels_length']
                l_weir = 2 * l_channels
                # l_weir = l_channels # RRI equation

                q_channels = c_weir * (l_weir**0.83) * (h1**5/3)  # SWMM equation, use it with cw between 1.5 and 2.6 ft^(1/2)/s. (0.82 to 1.44 m^(1/2)/s)
                # q_channels = (2/3)**(3/2) * h1 * math.sqrt(g * h1) * l_weir # RRI equation

                # B.2.2. Sum of both types of exchange
                q = q_conduits + q_channels
            
            inflows[node.nodeid] = q

    return inflows

def read_hs_grid(hs_file, skiprows=0):
    """
    Lee un archivo de salida hs (matriz en texto) y devuelve un numpy array 2D (nrows, ncols).
    Mantiene el orden de líneas tal cual (cada línea = fila).
    """
    rows = []
    # leemos línea a línea para preservar estructura de filas
    with open(hs_file, 'r', encoding='utf-8', errors='ignore') as f:
        for _ in range(skiprows):
            next(f, None)

        for line in f:
            # extrae todos los números (enteros o float)
            # nums = re.findall(r'[-+]?\d*\.\d+|\d+', line)
            nums = re.findall(r'[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|[-+]?\d+(?:[eE][-+]?\d+)?', line)
            if not nums:
                continue
            # convertir a float
            row = [float(x) for x in nums]
            rows.append(row)

    if not rows:
        raise ValueError(f"No se encontraron números en {hs_file}")

    # comprobar que todas las filas tienen misma longitud
    lengths = [len(r) for r in rows]
    if len(set(lengths)) != 1:
        raise ValueError(f"Filas con longitudes diferentes en {hs_file}: {set(lengths)}")

    arr = np.array(rows, dtype=float)
    return arr  # shape = (nrows, ncols)

def get_hs_vector(cells_idxs, hs_file, nodata_threshold=0.0):
    """
    Get hs values (surface depth) for each node.

    Args:
        cells_idxs (pd.DataFrame): DataFrame containing the corresponding cell indexes (i, j) for each node.
            Expected columns: at least ['NodeID', 'i', 'j'] or an index as node names and columns 'i','j'.
            i (row / y) and j (col / x) are expected to be 1-based (as in RRI outputs).
        hs_file (str): path to the hs output file from RRI (a text grid of whitespace-separated numbers).
        nodata_threshold (float): values lower to this threshold will be converted to np.nan.
            Default = 0.0, to catch nodata values like -0.10000.

    Returns:
        pd.Series: index are node names, and values are hs at the corresponding cells.
    """

    # --- Step 1: Read hs grid ---
    hs_grid = read_hs_grid(hs_file)
    nrows, ncols = hs_grid.shape

    # --- Step 2: Prepare cell index DataFrame ---
    df = cells_idxs.copy()

    # Ensure i and j columns exist
    if 'i' not in df.columns or 'j' not in df.columns:
        raise ValueError("cells_idxs must contain columns 'i' and 'j' with 1-based cell indices.")

    # Use NodeID as index if present, otherwise use current index
    if 'NodeID' in df.columns:
        df_index = df['NodeID'].astype(str)
    else:
        df_index = df.index.astype(str)

    # Convert i and j to integer arrays
    i_vals = df['i'].astype(int).to_numpy()
    j_vals = df['j'].astype(int).to_numpy()

    # Convert from 1-based to 0-based indices for NumPy access
    rows_idx = i_vals - 1
    cols_idx = j_vals - 1
    
    # --- Step 3: Range checking ---
    oob = (rows_idx < 0) | (rows_idx >= nrows) | (cols_idx < 0) | (cols_idx >= ncols)
    if oob.any():
        # informamos qué nodos están fuera de rango
        bad = np.where(oob)[0]
        bad_names = df_index.iloc[bad].tolist()
        # raise IndexError(f"Some nodes reference cells outside the grid bounds of {hs_file}: {bad_names}. "
        #                  f"Grid shape = (rows={nrows}, cols={ncols}).")
        raise IndexError(f"Some nodes reference cells outside the grid bounds of hs_grid: {bad_names}. "
                         f"Grid shape = (rows={nrows}, cols={ncols}).")
    
    # --- Step 4: Extract hs values for each node ---
    hs_vals = hs_grid[rows_idx, cols_idx].astype(float)

    # Replace nodata values with NaN
    hs_vals = np.where(hs_vals < nodata_threshold, np.nan, hs_vals)

    # --- Step 5: Return as a labeled Series ---
    s = pd.Series(hs_vals, index=df_index)
    s.name = 'hs'
    return s

def write_hs_grid(grid, out_file, nodata_value, fmt="{: .5f}"):
    """
    Write a 2D NumPy array to a plain-text hs grid file.
    NaN values in the array are written as nodata_value.
    fmt is a Python format string for each number (default 5 decimal places).
    """
    nrows, ncols = grid.shape
    with open(out_file, 'w', encoding='utf-8') as f:
        for r in range(nrows):
            row_vals = []
            for c in range(ncols):
                v = grid[r, c]
                if np.isnan(v):
                    # row_vals.append(f"{nodata_value}")
                    row_vals.append(fmt.format(nodata_value))
                else:
                    row_vals.append(fmt.format(v))
            f.write(" ".join(row_vals) + "\n")

def update_hs_raster(hs_file_1, inflows, cells_idxs, hs_file_2, time_delta, cell_surface_area, nodata_value):
    """
    Update hs output file from RRI applying surface<->drainage exchange and write the new hs file.

    Args:
        hs_file_1 (np.array): input hs grid
        inflows (pd.Series): index = node names, values = inflow (m^3/s). Positive means surface -> drainage.
        cell_idxs (pd.DataFrame): mapping nodes -> (i,j). Expected columns: 'NodeID','i','j' OR index = node names and columns 'i','j'. i and j are 1-based (rows,cols).
        hs_file_2 (str): path to write updated hs grid.
        time_delta (float): flow exchage timestep in seconds.
        cell_surface_area (float): cell area in m^2.
        nodata_value (float): value used for nodata in input and output (e.g., -0.10000).
    
    Returns:
        hs_new (np.ndarray): updated hs grid (2D array), with nodata cells as np.nan internally.
        negative_volume_m3 (float): estimated volume (m^3) corresponding to negative hs_new values.
    """

    # --- 1) Read input hs grid ---
    hs_grid = read_hs_grid(hs_file_1)
    # hs_grid = hs_grid_1
    nrows, ncols = hs_grid.shape

    # --- Step 2: Prepare cell index DataFrame ---
    df_index = cells_idxs.copy()

    # Ensure i and j columns exist
    if 'i' not in df_index.columns or 'j' not in df_index.columns:
        raise ValueError("cells_idxs must contain columns 'i' and 'j' with 1-based cell indices.")

    # # Use NodeID as index if present, otherwise use current index
    # if 'NodeID' in df.columns:
    #     df_index = df['NodeID'].astype(str)
    # else:
    #     df_index = df.index.astype(str)

    # Normalize index and inflows index to strings for robust matching
    df_index.index = df_index.index.astype(str)
    inflows.index = inflows.index.astype(str)

    # --- 3) Handle inflows that don't have mapping in cell_idxs ---
    inflow_nodes = set(inflows.index)
    mapped_nodes = set(df_index.index)
    # nodes in inflows not mapped
    unmapped = sorted(list(inflow_nodes - mapped_nodes))
    if unmapped:
        # warn with examples (up to 20)
        sample = unmapped[:20]
        warnings.warn(f"{len(unmapped)} inflow nodes have no mapping in cell_idxs and will be ignored. "
                      f"Examples: {sample}")
        
    common_nodes = sorted(list(inflow_nodes & mapped_nodes))
    if len(common_nodes) == 0:
        warnings.warn("No inflow nodes match entries in cell_idxs. No changes will be applied.")
        # still write a copy of input to output (with nodata preserved) and return zero volume
        # convert input nodata to np.nan for hs_new
        hs_new = hs_grid.astype(float).copy()
        hs_new[hs_new <= nodata_value] = np.nan
        write_hs_grid(hs_new, hs_file_2, nodata_value)
        return hs_new, 0.0

    # Subset df_index and inflows to common nodes (only these will be aggregated to cells)
    df_nodes = df_index.loc[common_nodes].copy()
    inflows_sub = inflows.loc[common_nodes].astype(float)
    df_nodes['inflow_m3s'] = inflows_sub.values

    # --- 4) Aggregate inflows per cell (i,j) ---
    df_nodes['i'] = df_nodes['i'].astype(int)
    df_nodes['j'] = df_nodes['j'].astype(int)
    grouped = df_nodes.groupby(['i', 'j'])['inflow_m3s'].sum().reset_index()

    # --- 5) Create total_inflow grid (m3/s) matching hs grid ---
    total_inflow_grid = np.zeros((nrows, ncols), dtype=float)
    oob_cells = []
    for _, row in grouped.iterrows():
        i = int(row['i']); j = int(row['j'])
        r = i - 1; c = j - 1  # convert to 0-based
        if r < 0 or r >= nrows or c < 0 or c >= ncols:
            oob_cells.append((i, j))
            continue
        total_inflow_grid[r, c] = row['inflow_m3s']
    if oob_cells:
        warnings.warn(f"{len(oob_cells)} aggregated cell indices are outside the hs grid and were ignored. "
                      f"Examples: {oob_cells[:10]}")
        
    # --- 6) Detect nodata cells in original hs_grid using nodata_value ---
    # Treat any cell with hs_old <= nodata_value as nodata.
    hs_old = hs_grid.astype(float).copy()
    orig_nodata_mask = (hs_old <= nodata_value)
    # Convert nodata sentinel to np.nan for internal calculations
    hs_old[orig_nodata_mask] = np.nan

    # --- 7) Compute delta_h and apply ---
    delta_h = (total_inflow_grid * float(time_delta)) / float(cell_surface_area)  # m
    # initialize hs_new as copy of hs_old (np.nan already in nodata positions)
    hs_new = hs_old.copy()
    # apply only where hs_old is not nan
    apply_mask = ~np.isnan(hs_old)
    hs_new[apply_mask] = hs_old[apply_mask] - delta_h[apply_mask]


    # --- 8) Compute negative-volume estimate from cells that ended up with hs_new < 0 ---
    negative_mask = (hs_new < 0) & (~np.isnan(hs_new))
    if negative_mask.any():
        # volume is sum of (-hs_new) * cell_surface_area across those cells
        negative_volume_m3 = float(np.sum(-hs_new[negative_mask] * float(cell_surface_area)))
    else:
        negative_volume_m3 = 0.0

    # Clip negative hs_new value to zero
    hs_new[negative_mask] = 0.0

    # --- 9) Write output: replace np.nan with nodata_value in output file ---
    write_hs_grid(hs_new, hs_file_2, nodata_value)

    # Return hs_new (with np.nan internal nodata) and negative volume in m3
    return hs_new, negative_volume_m3

def read_ascii_raster_no_data(filepath):
    """
    Reads an ASCII raster (.asc) file and returns raster metadata and the empty (zero) array keeping the no data positions.
    
    Returns:
        nrows (int): Number of rows in the raster
        ncols (int): Number of columns in the raster
        cell_size (float): Cell size of the raster grid
        data (np.ndarray): Array with np.nan in NODATA locations and 0 elsewhere
    """
    header_keys = ["ncols", "nrows", "xllcorner", "yllcorner", "cellsize", "NODATA_value"]
    header_values = {}

    with open(filepath, "r") as f:
        # Read header (first 6 lines)
        for _ in range(6):
            line = f.readline().strip().split()
            key, value = line[0], line[1]
            if key in header_keys:
                header_values[key] = float(value) if "." in value else int(value)

        # Read the rest of the file as numerical data
        data = np.loadtxt(f)

    ncols = header_values["ncols"]
    nrows = header_values["nrows"]
    cell_size = header_values["cellsize"]
    nodata = header_values["NODATA_value"]

    # Replace NODATA_value with np.nan, and all other values with 0
    data_processed = np.where(data == nodata, np.nan, 0)

    return nrows, ncols, cell_size, data_processed


if __name__ == "__main__":

    # opening_type = 'orifice'      # 'orifice' or 'weir'
    # h1 = 2.5              # hydraulic head upstreams
    # h2 = 2.00             # hydraulic head downstreams
    # z = 2.10              # elevation of the bottom of the orifice opening / elevation of the weir's crest
    # c = 0.6               # discharge coefficient for orifice (dimensionless) / weir (m^0.5/s)
    # l = 2                 # length
    # a = 0.15              # only for orifices, height of its opening

    # q = compute_flow(opening_type=opening_type,
    #                  h1=h1, h2=h2, z=z,
    #                  c=c, l=l, a=a)
    
    # print(q)

    # model_path = Path('C:/Users/lagos/Documents/00_INA/01_SSD/00_PREVENIR/09_Japon_2025/00_ICHARM/07_Coupled_model/SWMM_model')
    # model_name = 'network_model_v02_swmmfmt_sur.inp'

    # nodes_connections = get_associated_lengths(str(model_path.joinpath(model_path, model_name)))

    # inp_info = inp2df(str(model_path.joinpath(model_path, model_name)), conduits=True)
    # links_properties = inp_info['conduits']

    # cells_idxs = pd.read_csv('node_ij.txt', index_col=0, sep='\s+', engine='python', names=['i', 'j'], skiprows=1)
    # hs_file = 'RRI_RUN/out/hs_000001.out'

    # sim = Simulation(str(model_path.joinpath(model_path, model_name)))

    # results = compute_nodes_inflows(sim=sim, associated_lengths=nodes_connections, surface_depths=hs)

    # sim.close()
    pass
