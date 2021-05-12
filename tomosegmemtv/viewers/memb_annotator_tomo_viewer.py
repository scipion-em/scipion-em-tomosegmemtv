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

import threading
from os import symlink
from os.path import abspath, basename, join, exists
from pyworkflow.gui.dialog import ToolbarListDialog
from pyworkflow.utils.path import getParentFolder, removeBaseExt
from tomosegmemtv import Plugin


class MembAnnotatorDialog(ToolbarListDialog):
    """
    This class allows to  call a MembraneAnnotator subprocess from a list of Tomograms.
    """

    tomo = None
    proc = None

    def __init__(self, parent, path, **kwargs):
        self.path = path
        self.provider = kwargs.get("provider", None)
        self.prot = kwargs.get('prot', None)
        ToolbarListDialog.__init__(self, parent,
                                   "Membrane Annotator Object Manager",
                                   allowsEmptySelection=False,
                                   itemDoubleClick=self.doubleClickOnTomogram,
                                   allowSelect=False,
                                   **kwargs)

    def refresh_gui(self):
        if self.proc.is_alive():
            self.after(1000, self.refresh_gui)
        else:
            self.tree.update()

    def doubleClickOnTomogram(self, e=None):
        self.tomo = e
        self.proc = threading.Thread(target=self.launchMembAnnotatorForTomogram, args=(self.tomo,))
        self.proc.start()
        self.after(1000, self.refresh_gui)

    def launchMembAnnotatorForTomogram(self, tomoMask):
        # Tomo files come from one dir, while tomoMask files comes from another, because they were generated in
        # different protocols. MembraneAnnotator expects both to be in the same location, so a symbolic link is
        # is generated in the extra dir of the segmentation protocol pointing to the selected tomogram
        print("\n==> Running Membrane Annotator:")
        tomoNameSrc = abspath(tomoMask.getVolName())
        tomoName = abspath(join(getParentFolder(tomoMask.getFileName()), basename(tomoNameSrc)))
        if not exists(tomoName):
            symlink(tomoNameSrc, tomoName)
        arguments = "inTomoFile '%s' " % tomoName
        arguments += "outFilename '%s'" % abspath(join(self.path, removeBaseExt(tomoName)))
        Plugin.runMembraneAnnotator(self.prot, arguments, env=Plugin.getMembSegEnviron(), cwd=self.path)
