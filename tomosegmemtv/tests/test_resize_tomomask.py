# **************************************************************************
# *
# * Authors:     Scipion Team
# *
# * Unidad de  Bioinformatica of Centro Nacional de Biotecnologia , CSIC
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either version 3 of the License, or
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
from os import symlink
from os.path import join, exists

import pyworkflow.tests as pwtests
from imod.protocols import ProtImodTomoNormalization
from pwem.tests.workflows import TestWorkflow
from pyworkflow.utils import magentaStr, removeBaseExt
from tomo.protocols import ProtImportTomograms
from tomosegmemtv.protocols import ProtTomoSegmenTV, ProtResizeSegmentedVolume


class TestResizeTomoMask(TestWorkflow):
    origDim = (1024, 1440, 300)
    binning = 2

    @classmethod
    def setUpClass(cls):
        pwtests.setupTestProject(cls)
        ds = pwtests.DataSet.getDataSet('pyseg')
        cls.ds = ds
        cls.setSize = 2
        cls.samplingRate = 6.87
        cls.resizedDim = tuple([inDim / cls.binning for inDim in cls.origDim])
        # Because only one tomogram is contained in the used dataset, 2 links will be created pointing to the same
        # file, so they can be interpreted as a set of two tomograms, making the test complexity closer to the real
        # usage
        cls.virtualTomos = ['vTomo1', 'vTomo2']
        virtualTomos = [join(ds.getPath(), fpath + '.mrc') for fpath in cls.virtualTomos]
        [symlink(ds.getFile('presegTomo'), virtualTomo) for virtualTomo in virtualTomos if not exists(virtualTomo)]

    def _importTomograms(self):
        print(magentaStr("\n==> Importing the tomograms"))
        protImportTomo = self.newProtocol(
            ProtImportTomograms,
            filesPath=self.ds.getPath(),
            filesPattern='vTomo*.mrc',
            samplingRate=self.samplingRate
        )
        protImportTomo = self.launchProtocol(protImportTomo)
        tomoSet = getattr(protImportTomo, 'outputTomograms', None)

        # Validate output tomograms
        self.assertSetSize(tomoSet, size=self.setSize)
        self.assertEqual(tomoSet.getSamplingRate(), self.samplingRate)
        self.assertEqual(tomoSet.getDim(), self.origDim)

        return protImportTomo

    def _normalizeTomo(self, protImportTomo):
        print(magentaStr("\n==> Normalizing the tomograms to binning %i" % self.binning))
        protNormalizeTomo = self.newProtocol(ProtImodTomoNormalization,
                                             inputSetOfTomograms=getattr(protImportTomo, 'outputTomograms', None),
                                             binning=self.binning)

        protNormalizeTomo = self.launchProtocol(protNormalizeTomo)

        tomoSet = getattr(protNormalizeTomo, 'outputNormalizedSetOfTomograms')
        self.assertSetSize(tomoSet, size=self.setSize)
        self.assertTrue(abs(tomoSet.getSamplingRate() - self.binning * self.samplingRate) <= 0.001)
        self.assertEqual(tomoSet.getDim(), self.resizedDim)

        return protNormalizeTomo

    def _segmentMembranes(self, protNormalizeTomo):
        print(magentaStr("\n==> Segmenting the membranes"))
        protTomosegmemTV = self.newProtocol(
            ProtTomoSegmenTV,
            inTomograms=getattr(protNormalizeTomo, 'outputNormalizedSetOfTomograms', None),
            mbThkPix=6,
            mbScaleFactor=15,
            blackOverWhite=True,
            mbStrengthTh=0.0001,
            sigmaS=0.5
        )
        protTomosegmemTV = self.launchProtocol(protTomosegmemTV)
        tomoMaskSet = getattr(protTomosegmemTV, 'outputSetofTomoMasks', None)

        # Check output set
        self.assertSetSize(tomoMaskSet, size=self.setSize)
        self.assertEqual(tomoMaskSet.getSamplingRate(), self.samplingRate * self.binning)
        self.assertEqual(tomoMaskSet.getDim(), self.resizedDim)

        return protTomosegmemTV

    def _resizeTomoMask(self, protTomosegmemTV, protImportTomo):
        print(magentaStr("\n==> Resizing the tomomasks to the size of the imported tomograms"))
        protResizeTomoMask = self.newProtocol(
            ProtResizeSegmentedVolume,
            inTomoMasks=getattr(protTomosegmemTV, 'outputSetofTomoMasks', None),
            inTomos=getattr(protImportTomo, 'outputTomograms', None)
        )
        protResizeTomoMask = self.launchProtocol(protResizeTomoMask)
        tomoMaskSet = getattr(protResizeTomoMask, 'outputSetofTomoMasks', None)

        # Check output set
        self.assertSetSize(tomoMaskSet, size=self.setSize)
        self.assertEqual(tomoMaskSet.getSamplingRate(), self.samplingRate)
        self.assertEqual(tomoMaskSet.getDim(), self.origDim)

        # Check generated files
        for file in self.virtualTomos:
            self.assertTrue(exists(protResizeTomoMask._getExtraPath(removeBaseExt(file) + '_flt.mrc')))

    def testResizeTomoMask(self):
        protImportTomo = self._importTomograms()
        protNormalizeTomo = self._normalizeTomo(protImportTomo)
        protTomoSegmemTV = self._segmentMembranes(protNormalizeTomo)
        self._resizeTomoMask(protTomoSegmemTV, protImportTomo)
