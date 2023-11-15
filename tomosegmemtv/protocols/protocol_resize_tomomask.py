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
from os.path import exists, join, basename

import mrcfile
from scipy.ndimage import zoom
import numpy as np
from pwem.emlib.image import ImageHandler
from pwem.protocols import EMProtocol
from pyworkflow.protocol import PointerParam
from pyworkflow.utils import Message, removeBaseExt, getExt, getParentFolder
from tomo.objects import SetOfTomoMasks, TomoMask


class outputObjects(Enum):
    tomoMasks = SetOfTomoMasks


class ProtResizeSegmentedVolume(EMProtocol):
    """Resize segmented volumes or annotated (TomoMasks)."""

    _label = 'Resize segmented or annotated volume'
    _possibleOutputs = outputObjects
    resizedFileList = []

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
        form.addParam('inTomos', PointerParam,
                      pointerClass='SetOfTomograms',
                      allowsNull=False,
                      label='Input tomograms',
                      help='These tomograms will be used to be the ones to which the resized TomoMasks '
                           'will be referred to. Thus, the resized segmentations will be of the same size '
                           'of those tomograms.')

    def _insertAllSteps(self):
        tomoList = [tomoMask.clone() for tomoMask in self.inTomoMasks.get()]
        for tomoMask in tomoList:
            self._insertFunctionStep(self.resizeStep, tomoMask)
        self._insertFunctionStep(self.createOutputStep)

    def resizeStep(self, tomoMask):
        ih = ImageHandler()
        fileName = tomoMask.getFileName()
        x, y, z, _ = ih.getDimensions(tomoMask)
        nx, ny, nz, _ = ih.getDimensions(self.inTomos.get().getFirstItem())
        with mrcfile.open(fileName, permissive=True) as mrc:
            originalMask = np.round_(mrc.data)

        rx = nx / x
        ry = ny / y
        rz = nz / z

        resizedMask = zoom(originalMask, (rx, ry, rz), order=0)

        # Save resized data into a mrc file
        resizedFileName = self._getResizedMaskFileName(fileName)
        with mrcfile.open(resizedFileName, mode='w+') as mrc:
            mrc.set_data(np.round_(resizedMask))

        self.resizedFileList.append(resizedFileName)

    def createOutputStep(self):
        # Lists of input tomograms and resized tomo masks are sorted by name to ensure that
        # the relation between them is coherent
        inTomoList = [tomo.clone() for tomo in self.inTomos.get()]
        inTomoList.sort(key=self._sortTomoNames)
        resizedFileList = sorted(self.resizedFileList)
        inTomoMasksDir = getParentFolder(self.inTomoMasks.get().getFirstItem().getFileName())

        tomoMaskSet = SetOfTomoMasks.create(self._getPath(), template='tomomasks%s.sqlite', suffix='resized')
        tomoMaskSet.copyInfo(self.inTomos.get())
        counter = 1
        for resizedFile, inTomo in zip(resizedFileList, inTomoList):
            tomoMask = TomoMask()
            tomoMask.copyInfo(inTomo)
            tomoMask.setLocation((counter, resizedFile))
            tomoMask.setVolName(inTomo.getFileName())
            tomoMaskSet.append(tomoMask)

            # Make a symbolic link to the corresponding annotation data file if necessary (in case
            # of input set of annotated tomomasks)
            annotationDataFile = join(inTomoMasksDir, removeBaseExt(resizedFile) + '.txt')
            if exists(annotationDataFile):
                symlink(annotationDataFile, self._getExtraPath(basename(annotationDataFile)))

            counter += 1

        self._defineOutputs(**{outputObjects.tomoMasks.name: tomoMaskSet})
        self._defineSourceRelation(self.inTomoMasks.get(), tomoMaskSet)

    # --------------------------- INFO functions -----------------------------------
    def _summary(self):
        summary = []
        return summary

    # --------------------------- UTIL functions -----------------------------------
    def _getResizedMaskFileName(self, fileName):
        ext = getExt(fileName)
        return self._getExtraPath(removeBaseExt(fileName) + ext)

    @staticmethod
    def _sortTomoNames(tomoList):
        return sorted([tomo for tomo in tomoList.getFileName()])


