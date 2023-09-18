#!/usr/bin/env python3

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Copyright 2013 California Institute of Technology. ALL RIGHTS RESERVED.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
# http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# 
# United States Government Sponsorship acknowledged. This software is subject to
# U.S. export control laws and regulations and has been classified as 'EAR99 NLR'
# (No [Export] License Required except when exporting to an embargoed country,
# end user, or in support of a prohibited end use). By downloading this software,
# the user agrees to comply with all applicable U.S. export laws and regulations.
# The user has the responsibility to obtain export licenses, or other export
# authority as may be required before exporting this software to any 'EAR99'
# embargoed foreign country or citizen of those countries.
#
# Author: Piyush Agram
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



# giangi: taken Piyush code for snaphu and adapted
import os
import sys
import time
import argparse
import numpy as np
from osgeo import gdal

import isce
import isceobj
from isceobj.Constants import SPEED_OF_LIGHT
from isceobj.Util.ImageUtil import ImageLib as IML
from contrib.Snaphu.Snaphu import Snaphu
import s1a_isce_utils as ut


def createParser():
    '''
    Create command line parser.
    '''

    parser = argparse.ArgumentParser(description='Unwrap interferogram using snaphu')
    parser.add_argument('-i', '--ifg', dest='intfile', type=str, required=True,
            help='Input interferogram')
    parser.add_argument('-u', '--unw', dest='unwfile', type=str, default=None,
            help='Output unwrapped file')
    parser.add_argument('-c', '--coh', dest='cohfile', type=str,
            help='Coherence file')
    parser.add_argument('--nomcf', action='store_true', default=False,
            help='Run full snaphu and not in MCF mode')

    parser.add_argument('-a','--alks', dest='azlooks', type=int, default=1,
            help='Number of azimuth looks')
    parser.add_argument('-r', '--rlks', dest='rglooks', type=int, default=1,
            help='Number of range looks')

    parser.add_argument('-d', '--defomax', dest='defomax', type=float, default=2.0,
            help='Max cycles of deformation')
    parser.add_argument('-s', '--reference', dest='reference', type=str, default='reference',
            help='Reference directory')
    
    parser.add_argument('-m', '--method', dest='method', type=str, default='icu',
            help='unwrapping method')

    parser.add_argument('--rmfilter', action='store_true', default=False,
            help='remove the effect of filtering from final unwrapped interferograms')

    return parser


def cmdLineParse(iargs=None):
    '''
    Command line parser.
    '''

    parser = createParser()
    return parser.parse_args(args = iargs)


def extractInfo(xmlName, inps):
    '''
    Extract required information from pickle file.
    '''
    from isceobj.Planet.Planet import Planet
    from isceobj.Util.geo.ellipsoid import Ellipsoid

    frame = ut.loadProduct(xmlName)

    burst = frame.bursts[0]
    planet = Planet(pname='Earth')
    elp = Ellipsoid(planet.ellipsoid.a, planet.ellipsoid.e2, 'WGS84')

    data = {}
    data['wavelength'] = burst.radarWavelength

    tstart = frame.bursts[0].sensingStart
    tend   = frame.bursts[-1].sensingStop
    #tmid = tstart + 0.5*(tend - tstart)
    tmid = tstart


    orbit = burst.orbit
    peg = orbit.interpolateOrbit(tmid, method='hermite')

    refElp = Planet(pname='Earth').ellipsoid
    llh = refElp.xyz_to_llh(peg.getPosition())
    hdg = orbit.getENUHeading(tmid)
    refElp.setSCH(llh[0], llh[1], hdg)

    earthRadius = refElp.pegRadCur

    altitude   = llh[2]


    #sv = burst.orbit.interpolateOrbit(tmid, method='hermite')
    #pos = sv.getPosition()
    #llh = elp.ECEF(pos[0], pos[1], pos[2]).llh()

    data['altitude'] = altitude  #llh.hgt

    #hdg = burst.orbit.getHeading()
    data['earthRadius'] = earthRadius  #elp.local_radius_of_curvature(llh.lat, hdg)
    
    #azspacing  = burst.azimuthTimeInterval * sv.getScalarVelocity()
    #azres = 20.0 

    #corrfile  = os.path.join(self._insar.mergedDirname, self._insar.coherenceFilename)
    rangeLooks = inps.rglooks
    azimuthLooks = inps.azlooks
    azfact = 0.8
    rngfact = 0.8

    corrLooks = rangeLooks * azimuthLooks/(azfact*rngfact)

    data['corrlooks'] = corrLooks  #inps.rglooks * inps.azlooks * azspacing / azres
    data['rglooks'] = inps.rglooks
    data['azlooks'] = inps.azlooks

    return data

def runUnwrap(infile, outfile, corfile, config, costMode = None,initMethod = None, defomax = None, initOnly = None):

    if costMode is None:
        costMode   = 'DEFO'
    
    if initMethod is None:
        initMethod = 'MST'
    
    if  defomax is None:
        defomax = 4.0
    
    if initOnly is None:
        initOnly = False
    
    wrapName = infile
    unwrapName = outfile

    img = isceobj.createImage()
    img.load(infile + '.xml')


    wavelength = config['wavelength']
    width      = img.getWidth()
    length     = img.getLength()
    earthRadius = config['earthRadius'] 
    altitude   = config['altitude']
    rangeLooks = config['rglooks']
    azimuthLooks = config['azlooks']
    corrLooks = config['corrlooks']
    maxComponents = 20

    snp = Snaphu()
    snp.setInitOnly(initOnly)
    snp.setInput(wrapName)
    snp.setOutput(unwrapName)
    snp.setWidth(width)
    snp.setCostMode(costMode)
    snp.setEarthRadius(earthRadius)
    snp.setWavelength(wavelength)
    snp.setAltitude(altitude)
    snp.setCorrfile(corfile)
    snp.setInitMethod(initMethod)
    snp.setCorrLooks(corrLooks)
    snp.setMaxComponents(maxComponents)
    snp.setDefoMaxCycles(defomax)
    snp.setRangeLooks(rangeLooks)
    snp.setAzimuthLooks(azimuthLooks)

    corImg = isceobj.createImage()
    corImg.load(corfile + '.xml')
    if corImg.bands == 1:
        snp.setCorFileFormat('FLOAT_DATA')

    snp.prepare()
    snp.unwrap()

    ######Render XML
    outImage = isceobj.Image.createUnwImage()
    outImage.setFilename(unwrapName)
    outImage.setWidth(width)
    outImage.setLength(length)
    outImage.setAccessMode('read')
    # outImage.createImage()
    outImage.renderHdr()
    outImage.renderVRT()
    #outImage.finalizeImage()

    #####Check if connected components was created
    if snp.dumpConnectedComponents:
        connImage = isceobj.Image.createImage()
        connImage.setFilename(unwrapName+'.conncomp')
        #At least one can query for the name used
        connImage.setWidth(width)
        connImage.setLength(length)
        connImage.setAccessMode('read')
        connImage.setDataType('BYTE')
        # connImage.createImage()
        connImage.renderHdr()
        connImage.renderVRT()
        # connImage.finalizeImage()

    return


def runUnwrapMcf(infile, outfile, corfile, config, defomax=2):
    runUnwrap(infile, outfile, corfile, config, costMode = 'SMOOTH',initMethod = 'MCF', defomax = defomax, initOnly = True)
    return


def runUnwrapIcu(infile, outfile):
    from mroipac.icu.Icu import Icu
    #Setup images
    img = isceobj.createImage()
    img.load(infile + '.xml')
    width = img.getWidth()

    #intImage
    intImage = isceobj.createIntImage()
    intImage.initImage(infile, 'read', width)
    intImage.createImage()
   

    #unwImage
    unwImage = isceobj.Image.createImage()
    unwImage.setFilename(outfile)
    unwImage.setWidth(width)
    unwImage.imageType = 'unw'
    unwImage.bands = 2
    unwImage.scheme = 'BIL'
    unwImage.dataType = 'FLOAT'
    unwImage.setAccessMode('write')
    unwImage.createImage()
    
    #unwrap with icu
    icuObj = Icu()
    icuObj.filteringFlag = False      
    icuObj.useAmplitudeFlag = False
    icuObj.singlePatch = True
    icuObj.initCorrThreshold = 0.1
    icuObj.icu(intImage=intImage, unwImage = unwImage)

    #ampImage.finalizeImage()
    #intImage.finalizeImage()
    #unwImage.finalizeImage()
    unwImage.renderHdr()


def remove_filter(intfile, filtfile, unwfile):

    outunw = os.path.abspath(unwfile).split('filt_')
    outunw = outunw[0] + outunw[1]

    ds_unw = gdal.Open(unwfile + ".vrt", gdal.GA_ReadOnly)
    width = ds_unw.RasterXSize
    length = ds_unw.RasterYSize

    unw_phase = np.memmap(unwfile, dtype='f', mode='r', shape=(2, length, width))
    filt_phase = np.memmap(filtfile, dtype='f', mode='r', shape=(length, width))
    int_phase = np.memmap(intfile, dtype='f', mode='r', shape=(length, width))

    outfile = np.memmap(outunw, dtype='f', mode='w+', shape=(2, length, width))

    for line in range(length):
        integer_jumps = unw_phase[1, line, :] - np.angle(filt_phase[line, :])
        outfile[1, line, :] = integer_jumps + np.angle(int_phase[line, :])
        outfile[0, line, :] = unw_phase[0, line, :]
    
    unwImage = isceobj.Image.createImage()
    unwImage.setFilename(outunw)
    unwImage.setWidth(width)
    unwImage.setLength(length)
    unwImage.imageType = 'unw'
    unwImage.bands = 2
    unwImage.scheme = 'BIL'
    unwImage.dataType = 'FLOAT'
    unwImage.setAccessMode('read')
    unwImage.renderHdr()

    return

def main(iargs=None):
    '''
    The main driver.
    '''
    start_time = time.time()
    inps = cmdLineParse(iargs)
    print ('unwrapping method : ' , inps.method)

    if inps.method == 'snaphu':
        if inps.nomcf: 
            fncall =  runUnwrap
        else:
            fncall = runUnwrapMcf
        swathList = ut.getSwathList(inps.reference) 
        xmlFile = os.path.join(inps.reference , 'IW{0}.xml'.format(swathList[0]))
        metadata = extractInfo(xmlFile, inps)
        fncall(inps.intfile, inps.unwfile, inps.cohfile, metadata, defomax=inps.defomax)

        #mask out wired values from snaphu
        intImage = isceobj.createImage()
        intImage.load(inps.intfile+'.xml')
        width = intImage.width
        length = intImage.length

        flag = np.fromfile(inps.intfile, dtype=np.complex64).reshape(length, width)
        unw=np.memmap(inps.unwfile, dtype='float32', mode='r+', shape=(length*2, width))
        (unw[0:length*2:2, :])[np.nonzero(flag==0)]=0
        (unw[1:length*2:2, :])[np.nonzero(flag==0)]=0

    elif inps.method == 'icu':
        runUnwrapIcu(inps.intfile, inps.unwfile)

    if inps.rmfilter:
        filtfile = os.path.abspath(inps.intfile)
        intfile = filtfile.split('filt_')
        intfile = intfile[0] + intfile[1]

        remove_filter(intfile, filtfile, inps.unwfile)

    # time usage
    m, s = divmod(time.time() - start_time, 60)
    print('time used: {:02.0f} mins {:02.1f} secs.'.format(m, s))


if __name__ == '__main__':

    main()
