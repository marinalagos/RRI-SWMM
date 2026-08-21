#!/bin/bash
#SBATCH --job-name=rri_pipeline_short_test
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:30:00
#SBATCH --output=debug_cluster/rri_pipeline_short_test_%j.log

export OMP_NUM_THREADS=1
export OMP_DYNAMIC=FALSE
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

source /share/apps/anaconda3/bin/activate
conda activate /share/apps/anaconda3/envs/rriswmm_env

# Correr con: sbatch debug_cluster/submit_test_pipeline_short.sh
# desde la raiz del repo. Requiere que RRI_model/0_rri_1_4_2_7 ya sea
# el binario con el fix (ver debug_cluster/build_variants.sh).

rm -rf HIST/out/ && echo "HIST/out borrado"
rm -rf RRI_model/out/ && echo "RRI_model/out borrado"

srun --cpus-per-task=2 python debug_cluster/test_pipeline_short.py
