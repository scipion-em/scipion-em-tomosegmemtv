from os.path import join

from pwem.protocols import EMProtocol
from pyworkflow import BETA
from pyworkflow.protocol import PointerParam, FloatParam
from pyworkflow.utils import Message, removeBaseExt
from tomo.objects import SetOfTomoMasks, TomoMask

from tomosegmembtv import Plugin

MRC = '.mrc'
tstvDir = '/home/jjimenez/Jorge/Sync/TomoSegMemTV_Apr2020_linux/bin'


class ProtTomoSegmenTVDelineation(EMProtocol):
    """"""

    _label = 'membrane delineation'
    _devStatus = BETA
    tomoMaskListDelineated = []

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
                      label='Input tensor voted tomomasks')
        form.addParam('sigmaS', FloatParam,
                      label='Sigma for the initial gaussian filtering',
                      default=1,
                      allowsNull=False,
                      help='The input tomogram is subjected to an initial Gaussian filtering aiming at '
                           'reducing the noise so as to determine the derivatives more robustly. By default, '
                           'a standard deviation of 1.0 voxel is considered. This option allows fine-tuning '
                           'of this parameter. If the membranes are very thin or are very close to each other, '
                           'use lower values (e.g. 0.5)')
        form.addParam('sigmaP', FloatParam,
                      label='Sigma for the post-processing gaussian filtering',
                      default=1,
                      allowsNull=False,
                      help='This option refers to the post-processing Gaussian filtering that is applied '
                           'to the output tomogram. If sigma were set to 0, no such filtering is applied and '
                           'the program will produce 1-voxel-thick membranes. However, this type of thin '
                           'membranes might give problems with the subsequent stages (thresholding+global '
                           'analysis, based on 6-connectivity). For that reason, the default value for '
                           'post-processing Gaussian filtering is 1.0. Use lower values (e.g 0.5) for membranes '
                           'that are very thin or are very close to each other.'
                      )

    def _insertAllSteps(self):
        for tomoMask in self.inTomoMasks.get():
            self._insertFunctionStep('runTomoSegmenTV', tomoMask.getFileName(), tomoMask.getVolName())

        self._insertFunctionStep('createOutputStep')

    def runTomoSegmenTV(self, tomoMaskFile, tomoFile):
        tomoBaseName = removeBaseExt(tomoFile)

        # Saliency - second round (apply again the surfaceness program, but this time to produce the saliency)
        salOutputFile = self._getExtraPath(tomoBaseName + '_sal' + MRC)
        Plugin.runPySeg(self, join(tstvDir, 'surfaceness'), self._getSalCmd(tomoMaskFile, salOutputFile))
        self.tomoMaskListDelineated.append(salOutputFile)

    def createOutputStep(self):
        labelledSet = self._genOutputSetOfTomoMasks(self.tomoMaskListDelineated, 'delineated')
        self._defineOutputs(outputDelineatedSetofTomoMasks=labelledSet)

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

    def _getSalCmd(self, inputFile, outputFile):
        outputCmd = '-S '
        outputCmd += '-s %s ' % self.sigmaS.get()
        outputCmd += '-p %s ' % self.sigmaP.get()
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        return outputCmd



