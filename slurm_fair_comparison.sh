#!/bin/bash
#SBATCH --job-name=fair_comparison
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --exclusive
#SBATCH --nodelist=compute-0-17
#SBATCH --output=fair2_%j.log
#SBATCH --time=7-00:00:00

# "Fair" resource comparison: RRI-SWMM vs SWMM 5.2 standalone, both with
# 2 CPUs and SWMM's THREADS option set to 2 (matching the CPUs actually
# available), instead of the original benchmark's 2-vs-1-CPU / THREADS=4
# mismatch. SWMM 5.1 is not part of this comparison.
#
# Same node and thread-limiting env vars as slurm_tiempos_5.sh, so RRI's
# and Python's own behavior stays identical between the two experiments --
# SWMM's CPU/THREADS configuration is the only thing being varied here.

export OMP_NUM_THREADS=1
export OMP_DYNAMIC=FALSE
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

source /share/apps/anaconda3/bin/activate
conda activate /share/apps/anaconda3/envs/rriswmm_env

# Generate the THREADS=2 .inp variants (idempotent, safe to re-run)
python make_threads_variant.py SWMM_model/model.inp 2
python make_threads_variant.py benchmark/model.inp 2

ejecutar_rriswmm() {
    rm -rf HIST/out/ && echo "HIST/out borrado"
    rm -rf RRI_model/out/ && echo "RRI_model/out borrado"
    srun --cpus-per-task=2 --cpu-bind=cores python main_parallel_with_logger.py --swmm-model-name model_threads2

    echo "==========================================="
    echo " RESUMEN DEL REPORTE (Iteración $i) "
    echo "==========================================="

    if [ -f "SWMM_model/model_threads2.rpt" ]; then
        tail -n 5 "SWMM_model/model_threads2.rpt"
        cp "SWMM_model/model_threads2.rpt" "SWMM_model/fair_model${i}.rpt"
    else
        echo "ALERTA: El archivo model_threads2.rpt no fue generado."
    fi
    echo "==========================================="
}

ejecutar_swmm() {
    cd benchmark/
    rm -f model_threads2.out
    srun --cpus-per-task=2 --cpu-bind=cores ./runswmm model_threads2.inp "fair_model${i}.rpt" model_threads2.out
    cd ..

    echo "==========================================="
    echo " RESUMEN DEL REPORTE (Iteración $i) "
    echo "==========================================="

    if [ -f "benchmark/fair_model${i}.rpt" ]; then
        tail -n 5 "benchmark/fair_model${i}.rpt"
    else
        echo "ALERTA: El archivo .rpt no fue generado."
    fi
    echo "==========================================="
}

echo "Iniciando Benchmark Justo (2 CPUs, THREADS=2 en ambos): $(date)"
echo "-------------------------------------------"

for i in $(seq 1 11); do
    echo "--- Iteración $i ---"

    echo -n "SWMM: 5.2"
    echo "$(date)"
    ejecutar_swmm

    echo -n "RRI-SWMM: "
    echo "$(date)"
    ejecutar_rriswmm
done

echo "-------------------------------------------"
echo "Benchmark finalizado: $(date)"
