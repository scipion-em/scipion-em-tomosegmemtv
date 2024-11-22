# *
# * Authors:     Scipion Team (scipion@cnb.csic.es)
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
from pwem.protocols import EMProtocol
from pyworkflow.object import Set
from pyworkflow.protocol import PointerParam
from tomo.objects import SetOfTomoMasks, TomoMask, Tomogram


class ProtocolBase(EMProtocol):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @staticmethod
    def insertInTomosParam(form):
        form.addParam('inTomos', PointerParam,
                      pointerClass='SetOfTomograms',
                      allowsNull=False,
                      label='Input tomograms',
                      help='These tomograms will be used to be the ones to which the resized TomoMasks '
                           'will be referred to. Thus, the resized segmentations will be of the same size '
                           'of those tomograms.')

    def getInTomos(self, isPointer=True):
        return self.inTomos.get() if isPointer else self.inTomos

    def getOutputSetOfTomomasks(self):
        outTomosAttrib = self._possibleOutputs.tomoMasks.name
        outTomoMasks = getattr(self, outTomosAttrib, None)
        if outTomoMasks:
            outTomoMasks.enableAppend()
        else:
            outTomoMasks = SetOfTomoMasks.create(self._getPath(), template='tomomaskss%s.sqlite')
            outTomoMasks.copyInfo(self.getInTomos())
            outTomoMasks.setStreamState(Set.STREAM_OPEN)
            setattr(self, outTomosAttrib, outTomoMasks)
            self._defineOutputs(**{outTomosAttrib: outTomoMasks})
            self._defineSourceRelation(self.getInTomos(isPointer=False), outTomoMasks)

        return outTomoMasks

    def addTomoMask(self,inTomo: Tomogram, outFileName: str):
        outputTomoMasks = self.getOutputSetOfTomomasks()
        tomoMask = TomoMask()
        tomoMask.copyInfo(inTomo)
        tomoMask.setFileName(outFileName)
        tomoMask.setVolName(inTomo.getFileName())

        outputTomoMasks.append(tomoMask)
        outputTomoMasks.update(tomoMask)
        outputTomoMasks.write()
        self._store(outputTomoMasks)