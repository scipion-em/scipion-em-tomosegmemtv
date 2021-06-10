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

from pwem.protocols import EMProtocol
from pyworkflow import BETA
from pyworkflow.object import Integer
from pyworkflow.protocol import PointerParam
from pyworkflow.utils import removeBaseExt
from tomo.objects import SetOfTomoMasks, TomoMask

from tomosegmemtv.viewers_interactive.memb_annotator_tomo_viewer import MembAnnotatorDialog
from tomosegmemtv.viewers_interactive.memb_annotator_tree import MembAnnotatorProvider


class ProtAnnotateMembranes(EMProtocol):
    """ Manual annotation tool for segmented membranes
    """
    _label = 'annotate segmented membranes'
    _devStatus = BETA

    def __init__(self, **kwargs):
        EMProtocol.__init__(self, **kwargs)
        self._objectsToGo = Integer()
        self._provider = None
        self._tomoList = None
        
    def _defineParams(self, form):

        form.addSection(label='Input')
        form.addParam('inputTomoMasks', PointerParam,
                      label="Input Tomo Masks",
                      important=True,
                      pointerClass='SetOfTomoMasks',
                      allowsNull=False,
                      help='Select the Tomogram Masks (segmented tomograms) for the membrane annotation.')

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):
        self._initialize()
        self._insertFunctionStep('runMembraneAnnotator', interactive=True)

    # --------------------------- STEPS functions -----------------------------

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
            self._defineOutputs(outputSetofTomoMasks=labelledSet)

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

    # --------------------------- UTIL functions -----------------------------------

    def _initialize(self):
        self._tomoList = [tomo.clone() for tomo in self.inputTomoMasks.get().iterItems()]
        self._provider = MembAnnotatorProvider(self._tomoList, self._getExtraPath(), 'membAnnotator')
        self._getAnnotationStatus()

    def _getAnnotationStatus(self):
        """Check if all the tomo masks have been annotated and store current status in a text file"""
        doneTomes = [self._provider.getObjectInfo(tomo)['tags'] == 'done' for tomo in self._tomoList]
        self._objectsToGo.set(len(self._tomoList) - sum(doneTomes))

    def _getCurrentTomoMaskFile(self, inTomoFile):
        baseName = removeBaseExt(inTomoFile)
        return glob.glob(self._getExtraPath(baseName + '*_materials.mrc'))[0]

    def _genOutputSetOfTomoMasks(self):
        tomoMaskSet = SetOfTomoMasks.create(self._getPath(), template='tomomasks%s.sqlite', suffix='annotated')
        inTomoSet = self.inputTomoMasks.get()
        tomoMaskSet.copyInfo(inTomoSet)
        counter = 1
        for inTomo in inTomoSet.iterItems():
            tomoMask = TomoMask()
            inTomoFile = inTomo.getVolName()
            tomoMask.copyInfo(inTomo)
            tomoMask.setLocation((counter, self._getCurrentTomoMaskFile(inTomoFile)))
            tomoMask.setVolName(inTomoFile)
            tomoMaskSet.append(tomoMask)
            counter += 1

        return tomoMaskSet
