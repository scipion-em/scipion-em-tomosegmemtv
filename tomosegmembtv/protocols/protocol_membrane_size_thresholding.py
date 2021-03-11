from os.path import join, exists

from pwem.protocols import EMProtocol
from pyworkflow import BETA
from pyworkflow.protocol import PointerParam, IntParam, GT
from pyworkflow.utils import Message, removeBaseExt
from tomo.objects import SetOfTomoMasks, TomoMask

from tomosegmembtv import Plugin

MRC = '.mrc'
tstvDir = '/home/jjimenez/Jorge/Sync/TomoSegMemTV_Apr2020_linux/bin'


class ProtTomoSegmenTVSizeTh(EMProtocol):
    """"""

    _label = 'membrane size thresholding'
    _devStatus = BETA
    tomoMaskLblList = []

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
                      label='Input density filtered tomomasks')
        form.addParam('connectionTh', IntParam,
                      allowsNull=False,
                      default=100,
                      validators=[GT(0)],
                      label='Number of connected voxels threshold',
                      help='It sets the minimal size for a component to be considered as membrane.'
                      )

    def _insertAllSteps(self):
        for tomoMask in self.inTomoMasks.get():
            self._insertFunctionStep('runTomoSegmenTV', tomoMask.getFileName(), tomoMask.getVolName())

        self._insertFunctionStep('createOutputStep')

    def runTomoSegmenTV(self, tomoMaskFile, tomoFile):
        tomoBaseName = removeBaseExt(tomoFile)

        # Global analysis
        gAOutputFile = self._getExtraPath(tomoBaseName + '_labels' + MRC)
        Plugin.runPySeg(self, join(tstvDir, 'global_analysis'), self._getGlobalAnalysisCmd(tomoMaskFile, gAOutputFile))
        self.tomoMaskLblList.append(gAOutputFile)

    def createOutputStep(self):
        labelledSet = self._genOutputSetOfTomoMasks(self.tomoMaskLblList, 'labelled')
        self._defineOutputs(outputLabelledSetofTomoMasks=labelledSet)

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
        globalAnalysisFile = self._getGlobalAnalysisFile()
        if exists(globalAnalysisFile):
            with open(globalAnalysisFile) as f:
                summary = f.read().splitlines()

        return summary

    # --------------------------- UTIL functions -----------------------------------

    def _getGlobalAnalysisCmd(self, inputFile, outputFile):
        outputCmd = '-v2 '
        outputCmd += '-3 %s ' % self.connectionTh.get()
        outputCmd += '%s ' % inputFile
        outputCmd += '%s ' % outputFile
        outputCmd += '> %s' % self._getGlobalAnalysisFile()
        return outputCmd

    def _getGlobalAnalysisFile(self):
        return self._getExtraPath('globalAnalysis')



