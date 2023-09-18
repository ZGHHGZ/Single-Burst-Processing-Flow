#*****************************************************************************#
#*****************************************************************************#
########################      data download      ##############################
#*****************************************************************************#
#*****************************************************************************#

import os
import numpy
from pathlib import Path
from hyp3lib.get_orb import downloadSentinelOrbitFile
from burst import download_bursts, get_burst_params, get_isce2_burst_bbox, get_region_of_interest
from hyp3_isce2.dem import download_dem_for_isce2
from hyp3_isce2.s1_auxcal import download_aux_cal
import warnings
import multiprocessing

warnings.filterwarnings("ignore")
orbit_dir = Path('orbits')
aux_cal_dir = Path('aux_cal')
dem_dir = Path('dem')
data=numpy.loadtxt('stack.txt',dtype=str,delimiter=',')

#影像数据下载（BURST）
def imgae_download(data):
    scene_name = data[0]
    swath_number = data[1]
    burst_number = data[2]
    params = get_burst_params(scene_name ,swath_number, int(burst_number))
    metadata = download_bursts([params])
    if not os.path.exists("./" + str(params.granule) + '.SAFE/preview/map-overlay.kml'):
        footprint = get_isce2_burst_bbox(params)
        footprint=footprint.buffer(0.2).bounds
        print("坐标写入kml")
        cord_list=str(footprint)[1:-1].split(', ')
        print(cord_list)
        cord_kml=str(cord_list[0])+','+str(cord_list[1])+' '+str(cord_list[2])+','+str(cord_list[1])+' '+str(cord_list[2])+','+str(cord_list[3])+' '+str(cord_list[1])+','+str(cord_list[2])
        path = "./" + str(params.granule) + '.SAFE/preview'
        if not os.path.exists(path):
            os.mkdir(path)
        with open('../../code/map-overlay.txt', 'r') as f:
            kml=f.read()
            f.close()
        kml = kml.replace('          <coordinates>', '          <coordinates>' + cord_kml)  # 在第一个</coordinates>前插入
        with open(path+'/map-overlay.kml', 'w') as f:
            f.write(kml)
        print(str(params.granule)+"------kml创建成功")

################################################################################
pool = multiprocessing.Pool()
results = pool.map(imgae_download, data)
pool.close()
pool.join()
################################################################################

#轨道数据下载    
download_aux_cal(aux_cal_dir)
orbit_dir.mkdir(exist_ok=True, parents=True)
def orbit_download(data):
    scene_name = data[0]
    downloadSentinelOrbitFile(scene_name, str(orbit_dir))
################################################################################
pool = multiprocessing.Pool()
results = pool.map(orbit_download, data)
pool.close()
pool.join()
################################################################################

#DEM数据下载    
scene_name = data[0][0]
swath_number = data[0][1]
burst_number = data[0][2]
params = get_burst_params(scene_name ,swath_number, int(burst_number))    
dem_roi = get_isce2_burst_bbox(params).bounds
print(dem_roi)
dem_path = download_dem_for_isce2(dem_roi,dem_name='glo_30', dem_dir=dem_dir, buffer=0.2)


#*****************************************************************************#
#*****************************************************************************#
########################      isce process      ###############################
#*****************************************************************************#
#*****************************************************************************#
import os
import numpy
import isce 
import shutil
from pathlib import Path
from burst import download_bursts, get_burst_params, get_isce2_burst_bbox, get_region_of_interest
from topsStack import stackSentinel
from osgeo import gdal
import glob

os.chdir('../')
path= "./run_files"
if os.path.exists(path):
    print("run_files were existed")


else:
    os.chdir('./data')
    data=numpy.loadtxt('stack.txt',dtype=str,delimiter=',')
    ref_params = get_burst_params(data[0][0],data[0][1],int(data[0][2]))
    sec_params = get_burst_params(data[1][0],data[0][1],int(data[0][2]))
    ref_metadata = download_bursts(([ref_params]))
    is_ascending = ref_metadata.orbit_direction == 'ascending'
    ref_footprint = get_isce2_burst_bbox(ref_params)
    sec_footprint = get_isce2_burst_bbox(sec_params)
    insar_roi = get_region_of_interest(ref_footprint, sec_footprint, is_ascending=is_ascending)
 
    ###################################################################################################

    roi=" -b '" + str(insar_roi[1]) + " " + str(insar_roi[3]) + " " + str(insar_roi[0]) + " " + str(insar_roi[2]) + "'"
    print("burst的选择区域："+roi)
    os.chdir('../')
    os.system("python ../code/topsStack/stackSentinel.py -s ../process/data -d ./data/dem/full_res.dem.wgs84  -a ./data/aux_cal/ -o ./data/orbits -C geometry  -W slc -n '1'"+roi)
    line = open('./run_files/run_01_unpack_topo_reference').readline()
    line = line.replace("\n", "")
    line=str(line)+'0'
    print(line)
    open('./run_files/run_00_unpack_topo_reference','w').writelines(str(line))
    lines = open('./configs/config_reference').readlines()
    open('./configs/config_reference0','w').writelines(lines[0:13])
    open('./configs/config_reference','w').writelines(lines[0:4] + lines[16:])
    open('./configs/run_00_unpack_topo_reference','w').writelines(str(line))


run=[]
run.append("run_00_unpack_topo_reference")    #0
run.append('run_02_unpack_secondary_slc')    #1
run.append('run_01_unpack_topo_reference')    #2
run.append('run_03_average_baseline')    #3
run.append('run_04_fullBurst_geo2rdr')    #4
run.append('run_05_fullBurst_resample')    #5
run.append('run_06_extract_stack_valid_region')    #6
run.append('run_07_merge_reference_secondary_slc')    #7
run.append('run_08_grid_baseline')    #8


def swap_burst_vrts():
    """
    Swap the VRTs generated by topsApp for the reference and secondary bursts
    To convince topsApp to process a burst pair, we need to swap the VRTs it generates for the
    reference and secondary bursts with custom VRTs that point to the actual burst rasters.
    """
    ref_vrt_list = glob.glob('./reference/**/*.vrt')
    sec_vrt_list = glob.glob('./secondarys/**/**/*.vrt')
    path=os.getcwd()
    print(str(path))
    print(ref_vrt_list)
    print(sec_vrt_list)
    if len(ref_vrt_list)>0:
        for vrt_path in (ref_vrt_list):
            print(vrt_path)
            print(str(path)+str(vrt_path)[1:])
            vrt = gdal.Open(str(path)+str(vrt_path)[1:])
            base = gdal.Open(vrt.GetFileList()[1])
            del vrt
            gdal.Translate(str(path)+str(vrt_path)[1:], base, format='VRT')
            print("修改VRT")
            del base
    if len(sec_vrt_list)>0:     
        for i in range(len(sec_vrt_list)):
            print(str(path)+str(sec_vrt_list[i])[1:])
            vrt = gdal.Open(str(path)+str(sec_vrt_list[i])[1:])
            base = gdal.Open(vrt.GetFileList()[1])
            print(base)
            del vrt
            gdal.Translate(str(path)+str(sec_vrt_list[i])[1:], base, format='VRT')
            print("修改VRT")
            del base
    
    
    
#要运行的步骤
     
for i in range(len(run)):
    runstep=run[i]    
    with open('./run_files/'+str(runstep),"r") as f:
        a=f.readlines()
        print(str(a[0])[0:6])
    if str(a[0])[0:6]!="python":
        for i in range(len(a)):
            a[i]="python ../code/topsStack/"+a[i]
        with open('./run_files/'+str(runstep),"w") as f:
            for i in range(len(a)):
                f.write(str(a[i]))
    if runstep == run[1] or runstep == run[2]:
        swap_burst_vrts()     
    os.system('python ../code/topsStack/run.py -i ./run_files/'+str(runstep)+' -p 8')