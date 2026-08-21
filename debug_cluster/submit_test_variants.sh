#!/bin/bash
#SBATCH --job-name=rri_variants_test
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:30:00
#SBATCH --output=debug_cluster/rri_variants_test_%j.log
# Descomentar la siguiente linea para forzar el mismo nodo que usa produccion
# (slurm_tiempos_5.sh usa compute-0-17). Si ese nodo esta ocupado, dejar comentada
# y que SLURM elija.
##SBATCH --nodelist=compute-0-17

# Mismas variables que slurm_tiempos_5.sh, para que el binario corra con el
# mismo comportamiento de threads que en produccion (relevante porque el
# codigo tiene !$omp parallel do).
export OMP_NUM_THREADS=1
export OMP_DYNAMIC=FALSE
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

source /share/apps/anaconda3/bin/activate
conda activate /share/apps/anaconda3/envs/rriswmm_env

# Correr este script con: sbatch debug_cluster/submit_test_variants.sh
# desde la raiz del repo (donde estan main.py, RRI_model/, debug_cluster/).
# Asume que build_variants.sh ya corrio antes (los binarios 0_rri_test_*
# ya existen en RRI_source/1.4.2.7-20260121T122640Z-3-001/1.4.2.7/).

srun --cpus-per-task=2 bash debug_cluster/test_variants.sh
