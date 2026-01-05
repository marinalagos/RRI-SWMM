import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point

def inp2df(inpfile, subcatchments=False, junctions=False, storage=False, conduits=False, xsections=False, coordinates=False, polygons=False, orifices=False, weirs=False):
    
    a_inp = open(inpfile, 'r', encoding='latin-1')
    dict_results = {}

    general_dict = {
        'subcatchments': {'attributes': ['Name', 'Rgage', 'OutID', 'Area', '%Imperv', 'Width', 'Slope', 'Clength'],
                        'flag': False,
                        'request': subcatchments},
        'junctions': {'attributes': ['Name', 'Elev', 'Ymax', 'Y0', 'Ysur', 'Apond'],
                    'flag': False,
                    'request': junctions},
        'storage': {'attributes': ['Name', 'Elev.', 'MaxDepth', 'InitDepth', 'Shape', 'Curve', 'Type/Params', 'SurDepth', 'Fevap', 'Psi', 'Ksat', 'IMD'],
                    'flag': False,
                    'request': storage},
        'conduits': {'attributes': ['Name', 'From Node', 'To Node', 'Length', 'Roughness', 'InOffset', 'OutOffse', 'InitFlow', 'MaxFlow'],
                    'flag': False,
                    'request': conduits},
        'xsections': {'attributes': ['Link', 'Shape', 'Geom1','Geom2', 'Geom3', 'Geom4', 'Barrels', 'Culvert'],
                    'flag': False,
                    'request': xsections},
        'coordinates': {'attributes': ['Node', 'X-Coord', 'Y-Coord'],
                        'flag': False,
                        'request': coordinates},
        'polygons': {'attributes': ['Subcatchment', 'X-Coord', 'Y-Coord'],
                    'flag': False,
                    'request': polygons},
        'orifices': {'attributes': ['Name', 'From Node', 'To Node', 'Type', 'Offset', 'Qcoeff', 'Gated', 'CloseTime'],
                    'flag': False,
                    'request': orifices},
        'weirs': {'attributes': ['Name', 'From Node', 'To Node', 'Type', 'CrestHt', 'Qcoeff', 'Gated', 'EndCon', 'EndCoeff', 'Surcharge', 'RoadWidth', 'RoadSurf', 'Coeff. Curve'],
                    'flag': False,
                    'request': weirs},
                            }

    def get_ini_fin(object, linea, line, contador):
        if linea.upper().find('[' + object.upper() + ']') != -1:
            general_dict[object]['ini'] = contador
            general_dict[object]['flag'] = True
        if (len(line) == 1 or line.startswith('\t')) and general_dict[object]['flag']:
            general_dict[object]['fin'] = contador
            general_dict[object]['flag'] = False

    contador = 0

    for line in a_inp:
        linea = line.rstrip()
        contador+=1

        for object in general_dict:
            get_ini_fin(object=object, line=line, linea=linea, contador=contador)

    contador+=1
    last_line = contador
    a_inp.close()

    for object in general_dict:
        if general_dict[object]['request']:
            print(object.upper() + '\n')
            skip1 = general_dict[object]['ini'] + 2
            skip2 = last_line - general_dict[object]['fin']
            df_object = pd.read_csv(inpfile,
                                    sep='\s+',
                                    skiprows=skip1, 
                                    skipfooter=skip2,
                                    header=None,
                                    names=general_dict[object]['attributes'],
                                    engine='python',
                                    encoding='ISO-8859-1')
            df_object[df_object.columns[0]] = df_object[df_object.columns[0]].astype('str')
            df_object.set_index(df_object[df_object.columns[0]], inplace=True)
            del df_object[df_object.columns[0]]
            dict_results[object] = df_object
            print(df_object)
            print('\n')
    
    return dict_results

if __name__ == "__main__":
    results = inp2df('C:/Users/lagos/Documents/00_INA/01_SSD/00_PREVENIR/09_Japon_2025/00_ICHARM/01_SWMM/00_Original/model_actualizado_v13.inp',
                     junctions=True, conduits=True, xsections=True, coordinates=True)
# ver = inp2df('/home/phc/Git/sistema-de-prevision-de-inundaciones-urbanas/Carpeta_base_SWMM/model_base.inp', subcatchments=True, junctions=True) 

    junctions = results['junctions']
    conduits = results['conduits']
    xsections = results['xsections']
    coordinates = results['coordinates']

    junctions = junctions.merge(coordinates, left_index=True, right_index=True, how='left')
    conduits = conduits.merge(xsections, left_index=True, right_index=True, how='left')
    conduits = conduits.merge(junctions, left_on='From Node', right_index=True, how='left')
    conduits = conduits.merge(junctions, left_on='To Node', right_index=True, how='left', suffixes=('_1', '_2'))
    conduits = conduits[~conduits.index.str.contains('street')]
    conduits = conduits.dropna(subset=["X-Coord_1", "Y-Coord_1", "X-Coord_2", "Y-Coord_2"])

    conduits["geometry"] = conduits.apply(
        lambda row: LineString([(row["X-Coord_1"], row["Y-Coord_1"]),
                                (row["X-Coord_2"], row["Y-Coord_2"])]),
        axis=1
    )
    gdf = gpd.GeoDataFrame(conduits, geometry="geometry", crs="EPSG:5347")  # Cambiá el CRS según corresponda
    # gdf.to_file('conduits.shp', crs=5347)


    # Crear geometría Point
    junctions["geometry"] = junctions.apply(lambda row: Point(row["X-Coord"], row["Y-Coord"]), axis=1)

    # Convertir a GeoDataFrame
    gdf_points = gpd.GeoDataFrame(junctions, geometry="geometry", crs="EPSG:5347")  # Ajusta CRS según corresponda
    # gdf_points.to_file('junctions.shp')