from os.path import join

from pwem.protocols import EMProtocol
from pyworkflow import BETA
from pyworkflow.protocol import PointerParam, IntParam, GT, FloatParam, BooleanParam
from pyworkflow.utils import Message, removeBaseExt
from tomo.objects import SetOfTomoMasks, TomoMask

from tomosegmembtv import Plugin

MRC = '.mrc'
tstvDir = '/home/jjimenez/Jorge/Sync/TomoSegMemTV_Apr2020_linux/bin'


class ProtTomoSegmenTVTensorVoting(EMProtocol):
    """"""

    _label = 'tensor voting'
    _devStatus = BETA
    tomoMaskListVoted = []

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
        form.addParam('mbStrengthTh', FloatParam,
                      allowsNull=False,
                      default=0.3,
                      validators=[GT(0)],
                      label='Membrane-strength threshold',
                      help='Allow the user tune the amount of output membrane points and remove false positives. '
                           'Only voxels with values of membrane-strength threshold higher than this value '
                           'will be considered as potential membrane points, and planarity descriptors will '
                           'be calculated for them. Higher values will generate less membrane points, at the '
                           'risk of producing gaps in the membranes. Lower values will provide more membrane '
                           'points, at the risk of generating false positives.'
                      )

    def _insertAllSteps(self):
        for tomo in self.inTomograms.get():
            self._insertFunctionStep('runTomoSegmenTV', tomo.getFileName())

        self._insertFunctionStep('createOutputStep')

    def runTomoSegmenTV(self, tomoFile):
        tomoBaseName = removeBaseExt(tomoFile)

        # Scale space
        s2OutputFile = self._getExtraPath(tomoBaseName + '_s2' + MRC)
        Plugin.runPySeg(self, join(tstvDir, 'scale_space'), self._getScaleSpaceCmd(tomoFile, s2OutputFile))
        # Tensor voting
        tVOutputFile = self._getExtraPath(tomoBaseName + '_tv' + MRC)
        Plugin.runPySeg(self, join(tstvDir, 'dtvoting'), self._getTensorVotingCmd(s2OutputFile, tVOutputFile))
        # Surfaceness
        surfOutputFile = self._getExtraPath(tomoBaseName + '_surf' + MRC)
        Plugin.runPySeg(self, join(tstvDir, 'surfaceness'), self._getSurfCmd(tVOutputFile, surfOutputFile))
        # Tensor voting - second round (to fill potential gaps and increase the robustness of the surfaceness map)
        tV2OutputFile = self._getExtraPath(tomoBaseName + '_tv2' + MRC)
        Plugin.runPySeg(self, join(tstvDir, 'dtvoting'), self._getTensorVotingCmd(surfOutputFile, tV2OutputFile))
        self.tomoMaskListVoted.append(tV2OutputFile)

    def createOutputStep(self):
        labelledSet = self._genOutputSetOfTomoMasks(self.tomoMaskListVoted, 'tvoted')
        self._defineOutputs(outputTVotedSetofTomoMasks=labelledSet)

    def _genOutputSetOfTomoMasks(self, tomoMaskList, suffix):
        tomoMaskSet = SetOfTomoMasks.create(self._getPath(), template='tomomasks%s.sqlite', suffix=suffix)
        tomoMaskSet.copyInfo(self.inTomograms.get())
        counter = 1
        for file, inTomo in zip(tomoMaskList, self.inTomograms.get()):
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


