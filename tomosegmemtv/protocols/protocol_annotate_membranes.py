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
from pyworkflow import BETA
from pyworkflow.gui.dialog import askYesNo
from pyworkflow.utils import Message
from tomo.protocols import ProtTomoPicking
from tomo.viewers.views_tkinter_tree import TomogramsTreeProvider

from tomosegmemtv.viewers.memb_annotator_tomo_viewer import MembAnnotatorDialog


class ProtAnnotateMembranes(ProtTomoPicking):
    """ Manual annotation tool for segmented membranes
    """
    _label = 'Annotate segmented membranes'
    _devStatus = BETA

    def __init__(self, **kwargs):
        ProtTomoPicking.__init__(self, **kwargs)

    # --------------------------- DEFINE param functions ----------------------

    # --------------------------- INSERT steps functions ----------------------
    def _insertAllSteps(self):
        self._insertFunctionStep('runMembraneAnnotator', interactive=True)
        self._insertFunctionStep('createOutputStep')

    # --------------------------- STEPS functions -----------------------------

    def runMembraneAnnotator(self):

        tomoList = [tomo.clone() for tomo in self.inputTomograms.get().iterItems()]
        tomoProvider = TomogramsTreeProvider(tomoList, self._getExtraPath(), 'mrc')
        self.dlg = MembAnnotatorDialog(None, self._getExtraPath(), provider=tomoProvider, prot=self)

        # # Open dialog to request confirmation to create output
        # import tkinter as tk
        # frame = tk.Frame()
        # if askYesNo(Message.TITLE_SAVE_OUTPUT, Message.LABEL_SAVE_OUTPUT, frame):
        #     self._createOutput()

    def createOutputStep(self):
        pass

    # def getMethods(self, output):
    #     msg = 'User picked %d particles ' % output.getSize()
    #     msg += 'with a particle size of %s.' % output.getBoxSize()
    #     return msg
    #
    # def _methods(self):
    #     methodsMsgs = []
    #     if self.inputTomograms is None:
    #         return ['Input tomogram not available yet.']
    #
    #     methodsMsgs.append("Input tomograms imported of dims %s." %(
    #                           str(self.inputTomograms.get().getDim())))
    #
    #     if self.getOutputsSize() >= 1:
    #         for key, output in self.iterOutputAttributes():
    #             msg = self.getMethods(output)
    #             methodsMsgs.append("%s: %s" % (self.getObjectTag(output), msg))
    #     else:
    #         methodsMsgs.append(Message.TEXT_NO_OUTPUT_CO)
    #
    #     return methodsMsgs
