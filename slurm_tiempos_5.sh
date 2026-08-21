#!/bin/bash
#SBATCH --job-name=bench_intercalado
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --exclusive
#SBATCH --nodelist=compute-0-17
#SBATCH --output=bench2_%j.log
#SBATCH --time=7-00:00:00

export OMP_NUM_THREADS=1
export OMP_DYNAMIC=FALSE
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

source /share/apps/anaconda3/bin/activate
conda activate /share/apps/anaconda3/envs/rriswmm_env

ejecutar_rriswmm() {
    # Aquí puedes poner todas las líneas que necesites
    rm -rf HIST/out/ && echo "HIST/out borrado"
    rm -rf RRI_model/out/ && echo "RRI_model/out borrado"
    srun --cpus-per-task=2 python main_parallel_with_logger.py

    echo "==========================================="
    echo " RESUMEN DEL REPORTE (Iteración $i) "
    echo "==========================================="
    
    if [ -f "SWMM_model/model.rpt" ]; then
        tail -n 5 "SWMM_model/model.rpt"  # Ajusta el -n según cuántas líneas quieras ver
        cp "SWMM_model/model.rpt" "SWMM_model/model${i}.rpt" 
    else
        echo "ALERTA: El archivo model.rpt no fue generado."
    fi
    echo "==========================================="
}

# Definimos los pasos del Algoritmo B como una función
ejecutar_swmm() {
    # Aquí puedes poner todas las líneas que necesites
    cd benchmark/
    rm -f model.out
    srun --cpus-per-task=1 --cpu-bind=cores swmm5 model.inp "model${i}.rpt" model.out
    cd ..

    echo "==========================================="
    echo " RESUMEN DEL REPORTE (Iteración $i) "
    echo "==========================================="
    
    if [ -f "benchmark/model${i}.rpt" ]; then
        tail -n 5 "benchmark/model${i}.rpt"  # Ajusta el -n según cuántas líneas quieras ver
    else
        echo "ALERTA: El archivo model.rpt no fue generado."
    fi
    echo "==========================================="
}

# Definimos los pasos del Algoritmo B como una función
ejecutar_swmm_51() {
    # Aquí puedes poner todas las líneas que necesites
    cd benchmark/
    rm -f model_51.out
    srun --cpus-per-task=1 --cpu-bind=cores swmm5_1-011-cluster model.inp "model_51_${i}.rpt" model_51.out
    cd ..

    echo "==========================================="
    echo " RESUMEN DEL REPORTE (Iteración $i) "
    echo "==========================================="
    
    if [ -f "benchmark/model_51_${i}.rpt" ]; then
        tail -n 5 "benchmark/model_51_${i}.rpt"  # Ajusta el -n según cuántas líneas quieras ver
    else
        echo "ALERTA: El archivo model.rpt no fue generado."
    fi
    echo "==========================================="
}


# Número de repeticiones totales por algoritmo

echo "Iniciando Benchmark Intercalado: $(date)"
echo "-------------------------------------------"

# Bucle para intercalar las ejecuciones
for i in $(seq 41 51); do
    echo "--- Iteración $i ---"
    
    echo -n "RRI-SWMM: "
    echo "$(date)"
    ejecutar_rriswmm
    
    echo -n "SWMM 5.1: "
    echo "$(date)"
    ejecutar_swmm_51  # Ejecuta todas las líneas de la función
	
    echo -n "SWMM: 5.2"
    echo "$(date)"
    ejecutar_swmm  # Ejecuta todas las líneas de la función
done

echo "-------------------------------------------"
echo "Benchmark finalizado: $(date)"
