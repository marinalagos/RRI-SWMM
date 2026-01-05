from helper_functions import get_associated_lengths, get_hs_vector, compute_nodes_inflows, update_hs_raster, read_ascii_raster_no_data, write_hs_grid, read_hs_grid
# from run_rri_step import run_rri_step
# from run_swmm_step import run_swmm_step
from pathlib import Path
import pandas as pd
import shutil
import subprocess
from pyswmm import Simulation, Nodes
import numpy as np


# INITIAL SETTINGS

time_step = '10min' # RRI input file must match with this (e.g., time_step='10m' -> lasth = 0.166667, outnum = 1)
time_step_seconds = pd.Timedelta(time_step).seconds

run_path = Path('C:/Users/lagos/Documents/00_INA/01_SSD/00_PREVENIR/09_Japon_2025/00_ICHARM/08_Coupled_model_para_git/RRI_RUN')
hist_path = Path('C:/Users/lagos/Documents/00_INA/01_SSD/00_PREVENIR/09_Japon_2025/00_ICHARM/08_Coupled_model_para_git/HIST')

SWMM_model_path = Path('C:/Users/lagos/Documents/00_INA/01_SSD/00_PREVENIR/09_Japon_2025/00_ICHARM/08_Coupled_model_para_git/SWMM_model_overflow')
SWMM_model_name = 'network_model_v03_swmmfmt_over'

RRI_model_path = Path('C:/Users/lagos/Documents/00_INA/01_SSD/00_PREVENIR/09_Japon_2025/00_ICHARM/08_Coupled_model_para_git/RRI_model')
RRI_DEM_path = Path('C:/Users/lagos/Documents/00_INA/01_SSD/00_PREVENIR/09_Japon_2025/00_ICHARM/08_Coupled_model_para_git/RRI_model/topo/new_methodology_filled/IDW_NN_dtm_12_01_filled_manual_gauss_075-3_mod2.asc')
RRI_soil_depth_path = Path('C:/Users/lagos/Documents/00_INA/01_SSD/00_PREVENIR/09_Japon_2025/00_ICHARM/08_Coupled_model_para_git/RRI_model/topo/landuse_da.asc')

# PREPARATION

associated_lengths = get_associated_lengths(str(SWMM_model_path.joinpath(SWMM_model_name + '.inp')))
sim = Simulation(str(SWMM_model_path.joinpath(SWMM_model_name + '.inp')),
                 str(SWMM_model_path.joinpath(SWMM_model_name + '.rpt')),
                 str(SWMM_model_path.joinpath(SWMM_model_name + '.out')))

sim.step_advance(time_step_seconds)

nrows, ncols, cells_size, hs = read_ascii_raster_no_data(RRI_DEM_path)
write_hs_grid(hs, out_file=run_path.joinpath('out','gampt_ff_000001.out'), nodata_value=-0.10000)
write_hs_grid(hs, out_file=run_path.joinpath('out','hs_000001.out'), nodata_value=-0.10000)
write_hs_grid(hs, out_file=run_path.joinpath('out','hr_000001.out'), nodata_value=-0.10000)
write_hs_grid(hs, out_file=run_path.joinpath('out','qr_000001.out'), nodata_value=-0.10000)

# nrows = 276
# ncols = 136
# cells_size = 100

cell_surface_area = cells_size**2 # in m²

cells_idxs = pd.read_csv('node_ij_v03.txt', index_col=0, sep='\s+', engine='python', names=['i', 'j'], skiprows=1) # Qin san's file with some changes on the header
# Invert the i(y) index. This files enumerates the rows from bottom to top, but later numpy will access array elements enumarating the rows from top to bottom.
cells_idxs.i = nrows - cells_idxs.i + 1

# Get da vector for cells with infiltration (da = soil_depth * porosity)
da_vector = get_hs_vector(cells_idxs=cells_idxs, 
                          hs_file=RRI_soil_depth_path,
                          nodata_threshold=-1)

# EXECUTION

# Time range definition
time_start = '2024-03-18 20:30'
time_end = '2024-03-23 01:20'
# time_range = pd.date_range(time_start, time_end, freq=time_step, tz='utc')

sim.start_time = pd.to_datetime(time_start)
sim.end_time = pd.to_datetime(time_end)

i = 0
cum_neg_vol = 0

first_step = True
node_inflows = {}

for step in sim:

    i += 1 # this is for RRI outputs indexing
    
    #------------------#
    #  SWMM EXECUTION  #
    #------------------#

    current_sim_time = sim.current_time
    print(current_sim_time)


    if not first_step:
        for node, inflow in node_inflows.items():
            if inflow > 0.0:
                Nodes(sim)[node].generated_inflow(inflow)
            else:
                Nodes(sim)[node].generated_inflow(0.0)

    #-----------------#
    #  RRI EXECUTION  #
    #-----------------#

    # copy rainfall file
    # shutil.copy2(RRI_model_path.joinpath('rain', f'PREC_{current_sim_time:%Y%m%d_%H%M}.txt'), run_path.joinpath('rain', 'P.txt'))
    rainfall_file = RRI_model_path.joinpath('rain', f'PREC_{current_sim_time.replace(minute=(current_sim_time.minute//10)*10, second=0, microsecond=0):%Y%m%d_%H%M}.txt')
    if rainfall_file.is_file():
        shutil.copy2(rainfall_file, run_path.joinpath('rain', 'P.txt'))
    else:
        print('Rainfall file not found. Last file is used instead')
    # print(f'mean rainfall (file average): {read_hs_grid("RRI_RUN/rain/P.txt", skiprows=1).mean()} mm/h')
    # run the model
    try:
        proc = subprocess.run(str(run_path.joinpath('0_rri_1_4_2_7.exe')), 
                                  cwd = run_path, 
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL,
                                #   capture_output = True,
                                #   text = True,
                                  timeout = 1200)
        print(proc.returncode, proc.stdout, proc.stderr)
    except subprocess.TimeoutExpired as e:
        # return -1, "", f"TimeoutExpired: {e}"
        print(f"TimeoutExpired: {e}")

    # save the results in HIST directory
    shutil.copy2(run_path.joinpath('out','gampt_ff_000001.out'), hist_path.joinpath('out', f'gampt_ff_{i:06d}.out'))
    shutil.copy2(run_path.joinpath('out','hs_000001.out'), hist_path.joinpath('out', f'hs_{i:06d}.out'))
    shutil.copy2(run_path.joinpath('out','hr_000001.out'), hist_path.joinpath('out', f'hr_{i:06d}.out'))
    shutil.copy2(run_path.joinpath('out','qr_000001.out'), hist_path.joinpath('out', f'qr_{i:06d}.out'))

    #-----------------#
    #  FLOW EXCHANGE  #
    #-----------------#

    hs_vector = get_hs_vector(cells_idxs=cells_idxs, 
                              hs_file=run_path.joinpath('out','hs_000001.out'), #hs_grid = hs, #(hs - soil_depth_grid).clip(0), 
                              nodata_threshold=0.0)
        
    if hs_vector.isna().sum() > 0:
        # print(f'hs vector has {hs_vector.isna().sum()} nan value/s')
        hs_vector = hs_vector.fillna(0.0)

    hs_vector = hs_vector - da_vector
    hs_vector = hs_vector.clip(0)
    
    node_inflows = compute_nodes_inflows(sim=sim,
                                         associated_lengths=associated_lengths,
                                         surface_depths=hs_vector,
                                         inlet_length_proportion=0.05,
                                         c_orifice=0.6,
                                         c_weir=1.5*np.sqrt(0.3048),
                                         orifice_opening_height=0.15,
                                         compute_effective_h1=False)

    # print(f'MAX inflow: {pd.Series(node_inflows).max():.3f} m³/s - MAX outflow: {pd.Series(node_inflows).min():.3f} m³/s')

    hs, neg_volume = update_hs_raster(hs_file_1 = run_path.joinpath('out','hs_000001.out'), #hs_grid_1 = hs, #
                                      inflows = pd.Series(node_inflows),
                                      cells_idxs = cells_idxs,
                                      hs_file_2 = run_path.joinpath('out','hs_000001.out'),
                                      time_delta = time_step_seconds,
                                      cell_surface_area = cell_surface_area,
                                      nodata_value = -0.10000
                                      )

    cum_neg_vol += neg_volume
    # print(f'MAX Hs: {np.nanmax(hs)} m, CUM NEG VOLUME: {cum_neg_vol} m³')
    # fila_max, col_max = np.unravel_index(np.nanargmax(hs), hs.shape)
    # print(f'np index: {fila_max, col_max},  rri GUI index: {fila_max + 1, col_max + 1} ')
    # nodes_hs_max = cells_idxs[(cells_idxs.i == fila_max + 1) & (cells_idxs.j == col_max + 1)]
    # for node_hs_max in nodes_hs_max.index:
    #     node_swmm = Nodes(sim)[node_hs_max]
    #     print(f'NODO: {node_hs_max}, HEAD: {node_swmm.head}, DELTA_H: {node_swmm.head - node_swmm.full_depth - node_swmm.invert_elevation}')

    first_step = False

sim.close()
print(f'Total negative volume: {cum_neg_vol} m³ ({cum_neg_vol*1000/(240*1000*1000)} mm for the SSD basin)')