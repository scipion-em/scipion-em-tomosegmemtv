from os.path import join

from pwem.protocols import EMProtocol
from pyworkflow import BETA
from pyworkflow.protocol import PointerParam, GT, FloatParam
from pyworkflow.utils import Message, removeBaseExt
from tomo.objects import SetOfTomoMasks, TomoMask

from tomosegmembtv import Plugin

MRC = '.mrc'
tstvDir = '/home/jjimenez/Jorge/Sync/TomoSegMemTV_Apr2020_linux/bin'


class ProtTomoSegmenTVDensityTh(EMProtocol):
    """"""

    _label = 'membrane density thresholding'
    _devStatus = BETA
    tomoMaskThList = []

    def _defineParams(self, form):
        """ Define the input parameters that will be used.
        Params:
            form: this is the form to be populated with sections and params.
        """
        # You need a params to belong to a section:
        form.addSection(label=Message.LABEL_INPUT)
        form.addParam('inTomoMasks', PointerParam,
                      pointerClass='SetOfTomoMasks',
                      allowsNull=False,
                      label='Input tensor voted or delineated tomomasks')
        form.addParam('densityTh', FloatParam,
                      allowsNull=False,
                      default=0.05,
                      validators=[GT(0)],
                      label='Density threshold',
                      help='All the voxels with density equal to or higher than the threshold are set to 1. '
                           'The remaining voxels are set to 0.'
                      )

    def _insertAllSteps(self):
        for tomoMask in self.inTomoMasks.get():
            self._insertFunctionStep('runTomoSegmenTV', tomoMask.getFileName(), tomoMask.getVolName())

        self._insertFunctionStep('createOutputStep')

    def runTomoSegmenTV(self, tomoMaskFile, tomoFile):
        tomoBaseName = removeBaseExt(tomoFile)

        # Thresholding
        thOutputFile = self._getExtraPath(tomoBaseName + '_th' + MRC)
        Plugin.runPySeg(self, join(tstvDir, 'thresholding'), self._getThresholdingCmd(tomoMaskFile, thOutputFile))
        self.tomoMaskThList.append(thOutputFile)

    def createOutputStep(self):
        thSet = self._genOutputSetOfTomoMasks(self.tomoMaskThList, 'thresholded')
        self._defineOutputs(outputThresholdedSetofTomoMasks=thSet)

    def _genOutputSetOfTomoMasks(self, tomoMaskList, suffix):
        tomoMaskSet = SetOfTomoMasks.create(self._getPath(), template='tomomasks%s.sqlite', suffix=suffix)
        tomoMaskSet.copyInfo(self.inTomoMasks.get())
        counter = 1
        for file, inTomo in zip(tomoMaskList, self.inTomoMasks.get()):
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

    def _getThresholdingCmd(self, inputFile, outputFile):
        outputCmd = '-l %s ' % self.densityTh.get()
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        return outputCmd



