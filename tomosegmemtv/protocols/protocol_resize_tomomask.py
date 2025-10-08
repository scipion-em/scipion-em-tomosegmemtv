# *
# * Authors:     Scipion Team
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 2 of the License, or
# * (at your option) any later version.
# *
# * This program is distributed in the hope that it will be useful,
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# * You should have received a copy of the GNU General Public License
# * along with this program; if not, write to the Free Software
# * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
# * 02111-1307  USA
# *
# *  All comments concerning this program package may be sent to the
# *  e-mail address 'scipion-users@lists.sourceforge.net'
# *
# **************************************************************************
from enum import Enum
from os import symlink
from os.path import exists, join
import mrcfile
from scipy.ndimage import zoom
import numpy as np

from pwem.convert.headers import setMRCSamplingRate
from pwem.emlib.image import ImageHandler
from pyworkflow.protocol import PointerParam, STEPS_PARALLEL
from pyworkflow.utils import Message, removeBaseExt, getExt, getParentFolder
from tomo.objects import SetOfTomoMasks
from tomosegmemtv.protocols.protocol_base import ProtocolBase


class outputObjects(Enum):
    tomoMasks = SetOfTomoMasks


class ProtResizeSegmentedVolume(ProtocolBase):
    """Resize segmented volumes or annotated (TomoMasks).

    Given a TomoMask and a Tomogram the tomoMask will be upsampled or downsampled to
    according to the sampling rate of the input tomograms. The outpu tomoMasks will
    have the same sampling rate than the Tomograms.

    The used algorithm for scaling is based on splines, see:
    https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.zoom.html
    """

    _label = 'Resize segmented or annotated volume'
    _possibleOutputs = outputObjects
    resizedFileList = []
    stepsExecutionMode = STEPS_PARALLEL

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tomoMaskDict = None
        self.inTomosDict = None
        self.ih = None
        self.inTomoMasksDir = None

    def _defineParams(self, form):
        """ Define the input parameters that will be used.
        Params:
            form: this is the form to be populated with sections and params.
        """
        # You need a params to belong to a section:
        form.addSection(label=Message.LABEL_INPUT)
        form.addParam('inTomoMasks', PointerParam,
                      pointerClass='SetOfTomoMasks',
                      allowsNull=False,
                      label='Input segmentations (TomoMasks)')
        self.insertInTomosParam(form,
                                helpMsg='These tomograms will be used to be the ones to which the resized TomoMasks '
                                        'will be referred to. Thus, the resized segmentations will be of the same size '
                                        'of those tomograms.')
        form.addParallelSection(threads=1, mpi=0)

    def _insertAllSteps(self):
        self._initialize()
        stepIds = []
        for tsId in self.tomoMaskDict.keys():
            rsId = self._insertFunctionStep(self.resizeStep, tsId,
                                            prerequisites=None,
                                            needsGPU=False)
            cOutId = self._insertFunctionStep(self.createOutputStep, tsId,
                                              prerequisites=rsId,
                                              needsGPU=False)
            stepIds.append(cOutId)
        self._insertFunctionStep(self._closeOutputSet,
                                 prerequisites=stepIds,
                                 needsGPU=False)

    def _initialize(self):
        self.ih = ImageHandler()
        tomoMasks = self.inTomoMasks.get()
        tomograms = self.inTomos.get()
        tomoMasksIds = tomoMasks.getTSIds()
        tomogramsIds = tomograms.getTSIds()
        commonTsIds = set(tomoMasksIds) & set(tomogramsIds)
        self.tomoMaskDict = {tomoMask.getTsId(): tomoMask.clone() for tomoMask in tomoMasks
                             if tomoMask.getTsId() in commonTsIds}
        self.inTomosDict = {tomo.getTsId(): tomo.clone() for tomo in tomograms
                            if tomo.getTsId() in commonTsIds}
        self.inTomoMasksDir = getParentFolder(self.inTomoMasks.get().getFirstItem().getFileName())

    def resizeStep(self, tsId: str):
        tomoMask = self.tomoMaskDict[tsId]
        fileName = tomoMask.getFileName()
        x, y, z, _ = self.ih.getDimensions(tomoMask)
        nx, ny, nz, _ = self.ih.getDimensions(self.inTomosDict[tsId])
        with mrcfile.open(fileName, permissive=True) as mrc:
            originalMask = np.round_(mrc.data)

        rx = nx / x
        ry = ny / y
        rz = nz / z

        resizedMask = zoom(originalMask, (rx, ry, rz), order=0)

        # Save resized data into a mrc file
        resizedFileName = self._getResizedMaskFileName(tsId)
        with mrcfile.open(resizedFileName, mode='w+') as mrc:
            mrc.set_data(np.round_(resizedMask))

        self.resizedFileList.append(resizedFileName)

    def createOutputStep(self, tsId: str):
        with self._lock:
            inTomo = self.inTomosDict[tsId]
            resizedFile = self._getResizedMaskFileName(tsId)
            setMRCSamplingRate(resizedFile, inTomo.getSamplingRate())  # Update the apix value in file header
            self.addTomoMask(inTomo, resizedFile)

            # Make a symbolic link to the corresponding annotation data file if necessary (in case
            # of input set of annotated tomomasks)
            annotationDataFile = join(self.inTomoMasksDir, removeBaseExt(resizedFile) + '.txt')
            if exists(annotationDataFile):
                symlink(annotationDataFile, self._getExtraPath(removeBaseExt(resizedFile) + '.txt'))

    # --------------------------- INFO functions -----------------------------------
    def _summary(self):
        summary = []
        return summary

    # --------------------------- UTIL functions -----------------------------------
    def _getResizedMaskFileName(self, tsId: str):
        tomoMask = self.tomoMaskDict[tsId]
        ext = getExt(tomoMask.getFileName())
        return self._getExtraPath(f'{tsId}{ext}')
