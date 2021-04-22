from os.path import join

from pwem.protocols import EMProtocol
from pyworkflow import BETA
from pyworkflow.protocol import PointerParam, IntParam, GT, FloatParam, BooleanParam, LEVEL_ADVANCED
from pyworkflow.utils import Message, removeBaseExt
from tomo.objects import SetOfTomoMasks, TomoMask

from tomosegmemtv import Plugin

MRC = '.mrc'


class ProtTomoSegmenTV(EMProtocol):
    """"""

    _label = 'tomogram segmentation'
    _devStatus = BETA
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
        # form.addParam('')
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

    def _insertAllSteps(self):
        for tomo in self.inTomograms.get():
            self._insertFunctionStep('runTomoSegmenTV', tomo.getFileName())

        self._insertFunctionStep('createOutputStep')

    def runTomoSegmenTV(self, tomoFile):
        tomoBaseName = removeBaseExt(tomoFile)
        # Scale space
        s2OutputFile = self._getExtraPath(tomoBaseName + '_s2' + MRC)
        Plugin.runTomoSegmenTV(self, 'scale_space', self._getScaleSpaceCmd(tomoFile, s2OutputFile))
        # Tensor voting
        tVOutputFile = self._getExtraPath(tomoBaseName + '_tv' + MRC)
        Plugin.runTomoSegmenTV(self, 'dtvoting', self._getTensorVotingCmd(s2OutputFile, tVOutputFile))
        # Surfaceness
        surfOutputFile = self._getExtraPath(tomoBaseName + '_surf' + MRC)
        Plugin.runTomoSegmenTV(self, 'surfaceness', self._getSurfCmd(tVOutputFile, surfOutputFile))
        # Tensor voting - second round (to fill potential gaps and increase the robustness of the surfaceness map)
        tV2OutputFile = self._getExtraPath(tomoBaseName + '_tv2' + MRC)
        Plugin.runTomoSegmenTV(self, 'dtvoting', self._getTensorVotingCmd(surfOutputFile, tV2OutputFile))
        # Saliency - second round (apply again the surfaceness program, but this time to produce the saliency)
        salOutputFile = self._getExtraPath(tomoBaseName + '_sal' + MRC)
        Plugin.runTomoSegmenTV(self, 'surfaceness', self._getSalCmd(tV2OutputFile, salOutputFile))
        self.tomoMaskListDelineated.append(salOutputFile)

    def createOutputStep(self):
        labelledSet = self._genOutputSetOfTomoMasks(self.tomoMaskListDelineated, 'delineated')
        self._defineOutputs(outputDelineatedSetofTomoMasks=labelledSet)

    def _genOutputSetOfTomoMasks(self, tomoMaskList, suffix):
        tomoMaskSet = SetOfTomoMasks.create(self._getPath(), template='tomomasks%s.sqlite', suffix=suffix)
        inTomoSet = self.inTomograms.get()
        tomoMaskSet.copyInfo(inTomoSet)
        counter = 1
        for file, inTomo in zip(tomoMaskList, inTomoSet):
            tomoMask = TomoMask()
            tomoMask.copyInfo(inTomo)
            tomoMask.setLocation((counter, file))
            tomoMask.setVolName(inTomo.getFileName())
            tomoMaskSet.append(tomoMask)
            counter += 1

        return tomoMaskSet

    # --------------------------- INFO functions -----------------------------------
    def _summary(self):
        summary = []
        return summary

    # --------------------------- UTIL functions -----------------------------------

    def _getScaleSpaceCmd(self, inputFile, outputFile):
        outputCmd = '-s %s ' % self.mbThkPix.get()
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        return outputCmd

    def _getTensorVotingCmd(self, inputFile, outputFile):
        outputCmd = '-s %s ' % self.mbScaleFactor.get()
        if not self.blackOverWhite.get():
            outputCmd += '-w '
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        return outputCmd

    def _getSurfCmd(self, inputFile, outputFile):
        outputCmd = '-m %s ' % self.mbStrengthTh.get()
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        return outputCmd

    def _getSalCmd(self, inputFile, outputFile):
        outputCmd = '-S '
        outputCmd += '-s %s ' % self.sigmaS.get()
        outputCmd += '-p %s ' % self.sigmaP.get()
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        return outputCmd

