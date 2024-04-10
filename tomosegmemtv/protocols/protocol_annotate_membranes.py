# **************************************************************************
# *
# * Authors:     Scipion Team
# *
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
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************
import glob
from enum import Enum
from os.path import join, basename

from pwem.protocols import EMProtocol
from pyworkflow.object import Integer
from pyworkflow.protocol import PointerParam
from pyworkflow.utils import removeBaseExt, makePath, createLink, replaceBaseExt
from tomo.objects import SetOfTomoMasks, TomoMask

from tomosegmemtv.viewers_interactive.memb_annotator_tomo_viewer import MembAnnotatorDialog
from tomosegmemtv.viewers_interactive.memb_annotator_tree import MembAnnotatorProvider

EXT_MRC = '.mrc'
FLT_SUFFIX = '_flt'

class outputObjects(Enum):
    tomoMasks = SetOfTomoMasks


class ProtAnnotateMembranes(EMProtocol):
    """ Manual annotation tool for segmented membranes\n

    The annotation tool will open a graphical interface that will allow to manually
    label the set of tomo mask. The graphical interface will call the function membseg2
    for supervising the segmentation. This graphical interface was slightly modified
    in collaboration with the autor for simplifying its use.

    A complete tutorial about the use of this tool can be seen in:

    https://scipion-em.github.io/docs/release-3.0.0/docs/user/denoising_mbSegmentation_pysegDirPicking/tomosegmemTV-pySeg-workflow.html#membrane-annotation

    """
    _label = 'annotate segmented membranes'
    _possibleOutputs = outputObjects

    def __init__(self, **kwargs):
        EMProtocol.__init__(self, **kwargs)
        self._objectsToGo = Integer()
        self._provider = None
        self._tomoMaskDict = None
        
    def _defineParams(self, form):

        form.addSection(label='Input')
        form.addParam('inputTomoMasks', PointerParam,
                      label="Input Tomo Masks",
                      important=True,
                      pointerClass='SetOfTomoMasks',
                      allowsNull=False,
                      help='Select the Tomogram Masks (segmented tomograms) for the membrane annotation.')

        form.addParam('inputTomos', PointerParam,
                      label="Tomograms (Optional, only used for visualization)",
                      pointerClass='SetOfTomograms',
                      allowsNull=True,
                      help='Select the the set of tomogram used for obtaining the Tomo Masks. This set will'
                           'only be used for visualization purpose in order to simplify the annotation. Of the '
                           'tomo masks.')

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):

        self._initialize()

        self._insertFunctionStep(self.convertInputStep)
        self._insertFunctionStep(self.runMembraneAnnotator, interactive=True)

    # --------------------------- STEPS functions -----------------------------
    def convertInputStep(self):
        for tsId, tomoMask in self._tomoMaskDict.items():
            tsIdPath = self._getExtraPath(tsId)
            makePath(tsIdPath)

            createLink(tomoMask.getFileName(), self.getfltFile(tomoMask, FLT_SUFFIX + EXT_MRC))
            if self.inputTomos.get():
                tomo = self._tomoDict.get(tsId, None)
                if tomo:
                    createLink(tomo.getFileName(), self.getTomoMaskFile(tomo))
                else:
                    createLink(tomoMask.getFileName(), self.getTomoMaskFile(tomoMask))
            else:
                createLink(tomoMask.getFileName(), self.getfltFile(tomoMask) + EXT_MRC)

    def getfltFile(self, tomoMask, suffix=''):
        tsId = tomoMask.getTsId()
        return self._getExtraPath(tsId, removeBaseExt(tomoMask.getFileName().replace('_flt', '')) + suffix)

    def getTomoMaskFile(self, tomoMask):
        tsId = tomoMask.getTsId()
        return self._getExtraPath(tsId, basename(tomoMask.getFileName()))


    def runMembraneAnnotator(self):
        # There are still some objects which haven't been annotated --> launch GUI
        self._getAnnotationStatus()
        if self._objectsToGo.get() > 0:
            MembAnnotatorDialog(None, self._getExtraPath(), provider=self._provider, prot=self)

        # All the objetcs have been annotated --> create output objects
        self._getAnnotationStatus()
        if self._objectsToGo.get() == 0:
            print("\n==> Generating the outputs")
            labelledSet = self._genOutputSetOfTomoMasks()
            self._defineOutputs(**{outputObjects.tomoMasks.name: labelledSet})
            self._defineSourceRelation(self.inputTomoMasks.get(), labelledSet)

        self._store()

    # --------------------------- INFO functions -----------------------------------
    def _summary(self):
        summary = []
        objects2go = self._objectsToGo.get()
        if objects2go is not None:
            if objects2go > 0:
                summary.append('*%i* remaining segmentations to be annotated.' % objects2go)
            else:
                summary.append('All segmentations have been already annotated.')
        return summary

    def _validate(self):
        error = []
        # This is a tolerance in the sampling rate to ensure that tomoMask and tomograms have similar pixel size
        tolerance = 0.001
        if self.inputTomos.get():
            if abs(self.inputTomos.get().getSamplingRate() - self.inputTomoMasks.get().getSamplingRate()) > tolerance:
                error.append('The sampling rate of the tomograms does not match the sampling rate of the input masks')

        return error

    # --------------------------- UTIL functions -----------------------------------

    def _initialize(self):
        import time
        time.sleep(12)
        self._tomoMaskDict = {tomoMask.getTsId(): tomoMask.clone() for tomoMask in self.inputTomoMasks.get().iterItems()}
        if self.inputTomos.get():
            self._tomoDict = {tomo.getTsId(): tomo.clone() for tomo in self.inputTomos.get().iterItems()}
        self._provider = MembAnnotatorProvider(list(self._tomoMaskDict.values()), self._getExtraPath(), 'membAnnotator')
        self._getAnnotationStatus()

    def _getAnnotationStatus(self):
        """Check if all the tomo masks have been annotated and store current status in a text file"""
        doneTomes = [self._provider.getObjectInfo(tomo)['tags'] == 'done' for tomo in list(self._tomoMaskDict.values())]
        self._objectsToGo.set(len(self._tomoMaskDict) - sum(doneTomes))

    def _getCurrentTomoMaskFile(self, inTomoFile):
        baseName = removeBaseExt(inTomoFile)
        return glob.glob(self._getExtraPath(baseName + '_materials.mrc'))[0]

    def _genOutputSetOfTomoMasks(self):
        tomoMaskSet = SetOfTomoMasks.create(self._getPath(), template='tomomasks%s.sqlite', suffix='annotated')
        inTomoSet = self.inputTomoMasks.get()
        tomoMaskSet.copyInfo(inTomoSet)
        counter = 1
        for inTomo in inTomoSet:
            tomoMask = TomoMask()
            inTomoFile = inTomo.getVolName()
            tomoMask.copyInfo(inTomo)
            tomoMask.setLocation((counter, self._getCurrentTomoMaskFile(inTomoFile)))
            tomoMask.setVolName(inTomoFile)
            tomoMaskSet.append(tomoMask)
            counter += 1

        return tomoMaskSet
