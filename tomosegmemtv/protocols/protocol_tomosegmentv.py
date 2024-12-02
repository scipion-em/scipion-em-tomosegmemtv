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
import logging
import os
from enum import Enum
from os import remove
from os.path import abspath
from pwem.emlib.image import ImageHandler
from pyworkflow.protocol import IntParam, GT, FloatParam, BooleanParam, LEVEL_ADVANCED, STEPS_PARALLEL
from pyworkflow.utils import Message, removeBaseExt, createLink, cyanStr
from tomo.objects import SetOfTomoMasks
from tomosegmemtv import Plugin
from tomosegmemtv.protocols.protocol_base import ProtocolBase

logger = logging.getLogger(__name__)

# TomoSegmemTV programs
SCALE_SPACE = 'scale_space'
DT_VOTING = 'dtvoting'
SURFACENESS = 'surfaceness'

# Generated files suffixes
S2 = '_s2'
TV = '_tv'
SURF = '_surf'
TV2 = '_tv2'
FLT = '_flt'
SUFFiXES_2_REMOVE = [S2, TV, SURF, TV2]

MRC = '.mrc'


class outputObjects(Enum):
    tomoMasks = SetOfTomoMasks


class ProtTomoSegmenTV(ProtocolBase):
    """TomoSegMemTV is a software suite for segmenting membranes in tomograms. The method
    is based on (1) a Gaussian-like model of membrane profile, (2) a local differential structure
    approach and (3) anisotropic propagation of the local structural information using the tensor
    voting algorithm. In particular, it makes use of the next steps\n

    _1 Scale-space_: This stage allows isolation of the information according to the spatial
    scale by filtering out features with a size smaller than the given scale. It basically
    consists of a Gaussian filtering.\n
    _2 Dense Tensor voting_: In this stage, the voxels of the input tomogram communicate among
    themselves by propagating local structural information between each other. The local
    information is encoded in a second order tensor, called vote. The local properties at each
    voxel are then refined according to the information received from the neighbors.
    Voxels belonging to the same geometric feature will have strengthened each other and their
    tensors will have been modified to enhance the underlying global structure.\n

    _3 Surfaceness/Saliency_: This stage applies a local detector based on the
    Gaussian membrane model. The local detector relies on differential information,
    as it has to analyze local structure. In order to make it invariant to the membrane
    direction, the detector is established along the normal to the membrane at the local
    scale. An eigen-analysis of the Hessian tensor is well suited to determine such
    direction and provide the membrane-strength (M) for each voxel. Only voxels with
    membrane-strength higher than a threshold are considered and subjected to a non-maximum
    supression (NMS) operation so as to give a 1-voxel-thick surface. The final output map
    consists in planarity descriptors that represent the actual probability of
    belonging to a true surface (hence surfaceness).\n

    Once these protocols ends, it is neccesary to threshold the output map.

    """

    _label = 'tomogram segmentation'
    _possibleOutputs = outputObjects
    stepsExecutionMode = STEPS_PARALLEL

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tomoMaskListDelineated = []

    def _defineParams(self, form):
        """ Define the input parameters that will be used.
        Params:
            form: this is the form to be populated with sections and params.
        """
        # You need a params to belong to a section:
        form.addSection(label=Message.LABEL_INPUT)
        self.insertInTomosParam(form)

        form.addParam('mbThkPix', IntParam,
                      allowsNull=False,
                      default=1,
                      validators=[GT(0)],
                      label='Membrane thickness (voxels)',
                      help='It basically represents the standard deviation of a Gaussian filtering. '
                           'This parameter should represent the thickness (in pixels) of the membranes sought.'
                           'So, visual inspection of the tomogram helps the user to find out a proper value.'
                           'In general, any value in a range around that thickness works well. Too low '
                           'values may make spurious details produce false positives at the local membrane '
                           'detector while too high values may excessively smear out the membranes, which '
                           'in turn may produce discontinuities in the segmentation results. '
                           'This parameter is used in the scale-space step')

        form.addParam('mbScaleFactor', IntParam,
                      allowsNull=False,
                      default=10,
                      validators=[GT(0)],
                      label='Membrane scale factor (voxels)',
                      help='This parameter is used for tensor voting. This defines the effective neighborhood '
                           'involved in the voting process. Depending on the thickness of the membranes in '
                           'the tomogram, lower (for thinner membranes) or higher values (for thicker ones)'
                           ' may be more appropriate.'
                      )

        form.addParam('blackOverWhite', BooleanParam,
                      label='Is black over white?',
                      default=True,
                      help = 'By default, the program assumes that the features to detect (foreground/membranes) '
                             'are black (darker) over white (lighter) background. This is normally the case '
                             'in cryo-tomography.'
                      )
        group = form.addGroup('Membrane delineation',
                              expertLevel=LEVEL_ADVANCED)
        group.addParam('mbStrengthTh', FloatParam,
                       allowsNull=False,
                       default=0.3,
                       validators=[GT(0)],
                       expertLevel=LEVEL_ADVANCED,
                       label='Membrane-strength threshold',
                       help='Allows the user to specify a threshold for the membrane-strength. '
                            'Only voxels with values than the membrane-strength threshold '
                            'will be considered as potential membrane points, and planarity descriptors will '
                            'be calculated for them. Higher values will generate less membrane points, at the '
                            'risk of producing gaps in the membranes. Lower values will provide more membrane '
                            'points, at the risk of generating false positives.\n'
                            'Check the gray level of the membranes of the input images to introduce a proper '
                            'value.')
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
        form.addParam('binThreads', IntParam,
                      label='Tomosegmemtv threads',
                      default=4,
                      help='Number of threads used by Tomosegmemtv each time it is called in the protocol execution. For '
                           'example, if 2 Scipion threads and 3 Tomosegmemtv threads are set, the tomograms will be '
                           'processed in groups of 2 at the same time with a call of Tomosegmemtv with 3 threads each, so '
                           '6 threads will be used at the same time. Beware the memory of your machine has '
                           'memory enough to load together the number of tomograms specified by Scipion threads.')
        form.addParallelSection(threads=1, mpi=0)

    def _insertAllSteps(self):
        self._initialize()
        stepIds = []
        for tsId in self.inTomosDict.keys():
            cInId = self._insertFunctionStep(self.convertInputStep, tsId,
                                     prerequisites=[],
                                     needsGPU=False)
            runId = self._insertFunctionStep(self.runTomoSegmenTV, tsId,
                                     prerequisites=cInId,
                                     needsGPU=False)

            cOutId = self._insertFunctionStep(self.createOutputStep, tsId,
                                     prerequisites=runId,
                                     needsGPU=False)
            stepIds.append(cOutId)
        self._insertFunctionStep(self._closeOutputSet,
                                 prerequisites=stepIds,
                                 needsGPU=False)
        
    def _initialize(self):
        self.ih = ImageHandler()
        self.inTomosDict = {tomo.getTsId(): tomo.clone() for tomo in self.inTomos.get()}

    def convertInputStep(self, tsId: str):
        tomo = self.inTomosDict[tsId]
        fn = tomo.getFileName()
        newFn = self._getConvertedOrLinkedFn(tsId)
        logging.info(cyanStr(f'===> Converting or linking file {fn} into {newFn}'))
        if fn.endswith(MRC):
            createLink(fn, newFn)
        else:
            self.ih.convert(fn, newFn)

    def runTomoSegmenTV(self, tsId: str):
        logging.info(cyanStr(f'===> {tsId}: running TomoSegmemTV...'))
        tomoFile = self._getConvertedOrLinkedFn(tsId)
        Nthreads = self.binThreads.get()

        # Scale space
        logging.info(cyanStr(f'======> {tsId}: running program {SCALE_SPACE}...'))
        s2OutputFile = self._getExtraPath(tsId + S2 + MRC)
        cmd = self._getScaleSpaceCmd(tomoFile, Nthreads, s2OutputFile)
        Plugin.runTomoSegmenTV(self, SCALE_SPACE, cmd)
        # Tensor voting
        logging.info(cyanStr(f'======> {tsId}: running program {DT_VOTING} round 1...'))
        tVOutputFile = self._getExtraPath(tsId + TV + MRC)
        cmd = self._getTensorVotingCmd(s2OutputFile, tVOutputFile, Nthreads)
        Plugin.runTomoSegmenTV(self, DT_VOTING, cmd)
        # Surfaceness
        logging.info(cyanStr(f'======> {tsId}: running program {SURFACENESS} round 1...'))
        surfOutputFile = self._getExtraPath(tsId + SURF + MRC)
        cmd = self._getSurfCmd(tVOutputFile, surfOutputFile, Nthreads)
        Plugin.runTomoSegmenTV(self, SURFACENESS, cmd)
        # Tensor voting - second round (to fill potential gaps and increase the robustness of the surfaceness map)
        logging.info(cyanStr(f'======> {tsId}: running program {DT_VOTING} round 2...'))
        tV2OutputFile = self._getExtraPath(tsId + TV2 + MRC)
        cmd = self._getTensorVotingCmd(surfOutputFile, tV2OutputFile, Nthreads, isFirstRound=False)
        Plugin.runTomoSegmenTV(self, DT_VOTING, cmd)
        # Saliency - second round (apply again the surfaceness program, but this time to produce the saliency)
        logging.info(cyanStr(f'======> {tsId}: running program {SURFACENESS} round 2...'))
        salOutputFile = self._getExtraPath(tsId + FLT + MRC)
        cmd = self._getSalCmd(tV2OutputFile, salOutputFile, Nthreads)
        Plugin.runTomoSegmenTV(self, SURFACENESS, cmd)
        self.tomoMaskListDelineated.append(salOutputFile)
        # Remove intermediate files if requested
        if not self.keepAllFiles.get():
            self._removeIntermediateFiles(tomoFile)

    def createOutputStep(self, tsId: str):
        with self._lock:
            inTomo = self.inTomosDict[tsId]
            outFileName = self._getResultingFn(tsId)
            self.addTomoMask(inTomo, outFileName)

    # --------------------------- INFO functions -----------------------------------
    def _summary(self):
        summary = []
        return summary

    def _validate(self):
        if not os.path.exists(Plugin.getProgram(SCALE_SPACE)):
            return ["%s is not at %s. Review installation. Please go to %s for instructions." %
                    (SCALE_SPACE, Plugin.getProgram(SCALE_SPACE), Plugin.getUrl())]

    # --------------------------- UTIL functions -----------------------------------
    def _getConvertedOrLinkedFn(self, tsId: str) -> str:
        return self._getExtraPath(f'{tsId}{MRC}')

    def _getResultingFn(self, tsId: str) -> str:
        return self._getExtraPath(f'{tsId}_flt{MRC}')

    def _removeIntermediateFiles(self, tomoFile):
        tomoBaseName = removeBaseExt(tomoFile)
        for suffix in SUFFiXES_2_REMOVE:
            remove(abspath(self._getExtraPath(tomoBaseName + suffix + MRC)))

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
