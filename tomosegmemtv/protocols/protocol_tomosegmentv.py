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
import os
from enum import Enum
from os import remove
from os.path import abspath
from pwem.protocols import EMProtocol
from pyworkflow import BETA
from pyworkflow.protocol import PointerParam, IntParam, GT, FloatParam, BooleanParam, LEVEL_ADVANCED
from pyworkflow.utils import Message, removeBaseExt, replaceBaseExt, createLink
from tomo.objects import SetOfTomoMasks, TomoMask

from tomosegmemtv import Plugin

SCALE_SPACE = 'scale_space'

MRC = '.mrc'

# Generated files suffixes
S2 = '_s2'
TV = '_tv'
SURF = '_surf'
TV2 = '_tv2'
FLT = '_flt'
SUFFiXES_2_REMOVE = [S2, TV, SURF, TV2]


class outputObjects(Enum):
    tomoMasks = SetOfTomoMasks


class ProtTomoSegmenTV(EMProtocol):
    """Segment membranes in tomograms"""

    _label = 'tomogram segmentation'
    _devStatus = BETA
    _possibleOutputs = outputObjects
    tomoMaskListDelineated = []

    def _defineParams(self, form):
        """ Define the input parameters that will be used.
        Params:
            form: this is the form to be populated with sections and params.
        """
        # You need a params to belong to a section:
        form.addSection(label=Message.LABEL_INPUT)
        form.addParam('inTomograms', PointerParam,
                      pointerClass='SetOfTomograms',
                      allowsNull=False,
                      label='Input tomograms')

        form.addParam('mbThkPix', IntParam,
                      allowsNull=False,
                      default=1,
                      validators=[GT(0)],
                      label='Membrane thickness (voxels)',
                      help='It basically represents the standard deviation of a Gaussian filtering. '
                           'In general, any value in a range around that thickness works well. Too low '
                           'values may make spurious details produce false positives at the local membrane '
                           'detector while too high values may excessively smear out the membranes, which '
                           'in turn may produce discontinuities in the segmentation results.'
                      )
        form.addParam('mbScaleFactor', IntParam,
                      allowsNull=False,
                      default=10,
                      validators=[GT(0)],
                      label='Membrane scale factor (voxels)',
                      help='This defines the effective neighborhood involved in the voting process. '
                           'Depending on the thickness of the membranes in the tomogram, lower (for '
                           'thinner membranes) or higher values (for thicker ones) may be more appropriate.'
                      )
        form.addParam('blackOverWhite', BooleanParam,
                      label='Is black over white?',
                      default=True
                      )
        group = form.addGroup('Membrane delineation',
                              expertLevel=LEVEL_ADVANCED)
        group.addParam('mbStrengthTh', FloatParam,
                       allowsNull=False,
                       default=0.3,
                       validators=[GT(0)],
                       expertLevel=LEVEL_ADVANCED,
                       label='Membrane-strength threshold',
                       help='Allow the user tune the amount of output membrane points and remove false positives. '
                            'Only voxels with values of membrane-strength threshold higher than this value '
                            'will be considered as potential membrane points, and planarity descriptors will '
                            'be calculated for them. Higher values will generate less membrane points, at the '
                            'risk of producing gaps in the membranes. Lower values will provide more membrane '
                            'points, at the risk of generating false positives.'
                      )
        group.addParam('sigmaS', FloatParam,
                       label='Sigma for the initial gaussian filtering',
                       default=1,
                       allowsNull=False,
                       expertLevel=LEVEL_ADVANCED,
                       help='The input tomogram is subjected to an initial Gaussian filtering aiming at '
                            'reducing the noise so as to determine the derivatives more robustly. By default, '
                            'a standard deviation of 1.0 voxel is considered. This option allows fine-tuning '
                            'of this parameter. If the membranes are very thin or are very close to each other, '
                            'use lower values (e.g. 0.5)')
        group.addParam('sigmaP', FloatParam,
                       label='Sigma for the post-processing gaussian filtering',
                       default=0,
                       expertLevel=LEVEL_ADVANCED,
                       allowsNull=False,
                       help='This option refers to the post-processing Gaussian filtering that is applied '
                            'to the output tomogram. If sigma is set to 0, no such filtering will be applied and '
                            'the program will produce 1-voxel-thick membranes. If the filter is desired to be applied, '
                            'use lower values (e.g 0.5) for membranes that are very thin or are very close to each '
                            'other.'
                       )
        form.addParam('keepAllFiles', BooleanParam,
                      label='Keep all the generated files?',
                      default=False,
                      expertLevel=LEVEL_ADVANCED,
                      help='If set to Yes, a file will be kept for each step carried out in the protocol. If set to '
                           'No, only the file corresponding to the last step will be kept. Steps followed and the '
                           'corresponding generated files are listed below:\n\n'
                           '   - Scale-space --> *filename%s.mrc*\n'
                           '   - First tensor voting --> *filename%s.mrc*\n'
                           '   - Surfaceness --> *filename%s.mrc*\n'
                           '   - Second tensor voting --> *filename%s.mrc*\n'
                           '   - Saliency --> *filename%s.mrc*' % (S2, TV, SURF, TV2, FLT)
                      )

        form.addParallelSection(threads=8, mpi =1)

    def _insertAllSteps(self):
        self._insertFunctionStep(self.convertInputStep)
        for tomo in self.inTomograms.get():
            self._insertFunctionStep(self.runTomoSegmenTV, tomo.getFileName())

        self._insertFunctionStep(self.createOutputStep)

    def convertInputStep(self):
        # Convert the tomomask files if they are not .mrc
        for tomo in self.inTomograms.get():
            fn = tomo.getFileName()
            newFn = self._getExtraPath(replaceBaseExt(fn, 'mrc'))
            createLink(fn, newFn)

    def runTomoSegmenTV(self, tomoFile):
        tomoBaseName = removeBaseExt(tomoFile)
        tomoFile = self._getExtraPath(tomoBaseName + '.mrc')

        Nthreads = self.numberOfThreads.get()

        # Scale space
        s2OutputFile = self._getExtraPath(tomoBaseName + S2 + MRC)
        Plugin.runTomoSegmenTV(self, SCALE_SPACE, self._getScaleSpaceCmd(tomoFile, Nthreads, s2OutputFile))
        # Tensor voting
        tVOutputFile = self._getExtraPath(tomoBaseName + TV + MRC)
        Plugin.runTomoSegmenTV(self, 'dtvoting', self._getTensorVotingCmd(s2OutputFile, tVOutputFile, Nthreads))
        # Surfaceness
        surfOutputFile = self._getExtraPath(tomoBaseName + SURF + MRC)
        Plugin.runTomoSegmenTV(self, 'surfaceness', self._getSurfCmd(tVOutputFile, surfOutputFile, Nthreads))
        # Tensor voting - second round (to fill potential gaps and increase the robustness of the surfaceness map)
        tV2OutputFile = self._getExtraPath(tomoBaseName + TV2 + MRC)
        Plugin.runTomoSegmenTV(self, 'dtvoting',
                               self._getTensorVotingCmd(surfOutputFile, tV2OutputFile, Nthreads, isFirstRound=False))
        # Saliency - second round (apply again the surfaceness program, but this time to produce the saliency)
        salOutputFile = self._getExtraPath(tomoBaseName + FLT + MRC)
        Plugin.runTomoSegmenTV(self, 'surfaceness', self._getSalCmd(tV2OutputFile, salOutputFile, Nthreads))
        self.tomoMaskListDelineated.append(salOutputFile)
        # Remove intermediate files if requested
        if not self.keepAllFiles.get():
            self._removeIntermediateFiles(tomoFile)

    def createOutputStep(self):
        labelledSet = self._genOutputSetOfTomoMasks(self.tomoMaskListDelineated, 'segmented')
        self._defineOutputs(**{outputObjects.tomoMasks.name: labelledSet})
        self._defineSourceRelation(self.inTomograms.get(), labelledSet)

    def _genOutputSetOfTomoMasks(self, tomoMaskList, suffix):
        tomoMaskSet = SetOfTomoMasks.create(self._getPath(), template='tomomasks%s.sqlite', suffix=suffix)
        inTomoSet = self.inTomograms.get()
        tomoMaskSet.copyInfo(inTomoSet)
        counter = 1
        for file, inTomo in zip(tomoMaskList, inTomoSet):
            tomoMask = TomoMask()
            fn = inTomo.getFileName()
            tomoMask.copyInfo(inTomo)
            tomoMask.setLocation((counter, file))
            tomoMask.setVolName(self._getExtraPath(replaceBaseExt(fn, 'mrc')))
            tomoMaskSet.append(tomoMask)
            counter += 1

        return tomoMaskSet

    def _removeIntermediateFiles(self, tomoFile):
        tomoBaseName = removeBaseExt(tomoFile)
        for suffix in SUFFiXES_2_REMOVE:
            remove(abspath(self._getExtraPath(tomoBaseName + suffix + MRC)))

    # --------------------------- INFO functions -----------------------------------
    def _summary(self):
        summary = []
        return summary

    def _validate(self):
        if not os.path.exists(Plugin.getProgram(SCALE_SPACE)):
            return ["%s is not at %s. Review installation. Please go to %s for instructions." %
                    (SCALE_SPACE, Plugin.getProgram(SCALE_SPACE),Plugin.getUrl())]

    # --------------------------- UTIL functions -----------------------------------

    def _getScaleSpaceCmd(self, inputFile, Nthreads, outputFile):
        outputCmd = '-s %s ' % self.mbThkPix.get()
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        outputCmd += ' -t %i' % Nthreads
        return outputCmd

    def _getTensorVotingCmd(self, inputFile, outputFile, Nthreads, isFirstRound=True):
        outputCmd = '-s %s ' % self.mbScaleFactor.get()
        if isFirstRound and not self.blackOverWhite.get():
            outputCmd += '-w '
        elif not isFirstRound:
            outputCmd += '-w '  # After the first tensor voting, the image will be always white over black
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        outputCmd += ' -t %i' % Nthreads
        return outputCmd

    def _getSurfCmd(self, inputFile, outputFile, Nthreads):
        outputCmd = '-m %s ' % self.mbStrengthTh.get()
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        outputCmd += ' -t %i' % Nthreads
        return outputCmd

    def _getSalCmd(self, inputFile, outputFile, Nthreads):
        outputCmd = '-S '
        outputCmd += '-s %s ' % self.sigmaS.get()
        outputCmd += '-p %s ' % self.sigmaP.get()
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        outputCmd += ' -t %i' % Nthreads
        return outputCmd

