#!/bin/bash
# Correr esto DENTRO de RRI_source/1.4.2.7-20260121T122640Z-3-001/1.4.2.7/
# Compila 3 variantes del mismo codigo fuente con distintos flags de punto flotante,
# usando el mismo GCC 4.8.5 del cluster, para ver si el HANG depende de los flags
# de optimizacion en vez de una diferencia de algoritmo.
set -e

SRC="RRI.f90 RRI_Bound.f90 RRI_Dam.f90 RRI_Div.f90 RRI_DT_Check.f90 RRI_Evp.f90 RRI_GW.f90 RRI_Infilt.f90 RRI_Read.f90 RRI_Riv.f90 RRI_RivSlo.f90 RRI_Section.f90 RRI_Slope.f90 RRI_Sub.f90 RRI_Tecout.f90 RRI_TSAS.f90"
MODS="RRI_Mod.f90 RRI_Mod2.f90 RRI_Mod_Dam.f90 RRI_Mod_Tecout.f90"

build_variant () {
  NAME=$1
  shift
  FLAGS="$@"
  echo "=== Building $NAME  (flags: $FLAGS) ==="
  WORKDIR=$(mktemp -d)
  cp $MODS $SRC "$WORKDIR"/
  ( cd "$WORKDIR" && \
    gfortran $FLAGS -c $MODS && \
    gfortran $FLAGS -c $SRC && \
    gfortran $FLAGS *.o -o "$NAME" )
  cp "$WORKDIR/$NAME" ./
  rm -rf "$WORKDIR"
  echo "-> built ./$NAME"
}

# Variante 1: igual al binario actual, mismos flags "tipicos" agresivos (equivalente al -O3 del .bat de Windows)
build_variant 0_rri_test_O3        -O3 -fopenmp

# Variante 2: optimizacion conservadora, sin fusion de operaciones ni fast-math (mas parecido al comportamiento IEEE estricto de ifort sin /fp:fast)
build_variant 0_rri_test_strict    -O2 -fopenmp -fno-fast-math -ffp-contract=off -frounding-math

# Variante 3: sin optimizacion alguna (el mas "literal" posible)
build_variant 0_rri_test_O0        -O0 -fopenmp

echo "Listo. Binarios: 0_rri_test_O3, 0_rri_test_strict, 0_rri_test_O0"
