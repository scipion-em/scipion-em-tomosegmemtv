# **************************************************************************
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
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************
from pyworkflow.gui.dialog import ToolbarListDialog
from tomo3D.viewers.viewer_mrc import MrcPlot
from tomo3D.viewers.viewer_triangulations import guiThread


class AnnotatedVesicleViewerDialog(ToolbarListDialog):
    """
    This class allows to  call a MembraneAnnotator subprocess from a list of Tomograms.
    """

    def __init__(self, parent, **kwargs):
        self.provider = kwargs.get("provider", None)
        ToolbarListDialog.__init__(self, parent,
                                   "Annotated Vesicle Object Manager",
                                   allowsEmptySelection=False,
                                   itemDoubleClick=self.launchAnnotationViewer,
                                   allowSelect=False,
                                   **kwargs)

    @staticmethod
    def launchAnnotationViewer(tomoMask):
        print("\n==> Running Annotated Vesicle Viewer:")
        materialsName = tomoMask.getFileName()
        tomoName = tomoMask.getVolName()
        args = {'tomo_mrc': tomoName, 'mask_mrc': materialsName}
        guiThread(MrcPlot, 'initializePlot', **args)
