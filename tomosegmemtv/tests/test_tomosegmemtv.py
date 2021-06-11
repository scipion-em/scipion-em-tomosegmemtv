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
from os import symlink, remove
from os.path import join, exists

import pyworkflow.tests as pwtests
from pwem.tests.workflows import TestWorkflow
from pyworkflow.utils import magentaStr, removeBaseExt
from tomo.protocols import ProtImportTomograms

from tomosegmemtv.protocols import ProtTomoSegmenTV


class TestTomosegmemTV(TestWorkflow):
    virtualTomo2 = None
    virtualTomo1 = None

    @classmethod
    def setUpClass(cls):
        pwtests.setupTestProject(cls)
        ds = pwtests.DataSet.getDataSet('tomosegmemtv')
        cls.ds = ds
        cls.samplingRate = 1
        # Because only one tomogram is provided in the tutorial, 2 links will be created pointing to the same file, so
        # they can be interpreted as a set of two tomograms, making the test complexity closer to the real usage
        cls.virtualTomos = ['vTomo1', 'vTomo2']
        virtualTomos = [join(ds.getPath(), fpath + '.mrc') for fpath in cls.virtualTomos]
        [symlink(ds.getFile('tomogram'), virtualTomo) for virtualTomo in virtualTomos if not exists(virtualTomo)]

    def _importTomograms(self):
        print(magentaStr("\n==> Importing data - tomograms:"))
        protImportTomo = self.newProtocol(
            ProtImportTomograms,
            filesPath=self.ds.getPath(),
            filesPattern='vTomo*.mrc',
            samplingRate=self.samplingRate
        )
        protImportTomo = self.launchProtocol(protImportTomo)
        tomoSet = getattr(protImportTomo, 'outputTomograms', None)

        # Validate output tomograms
        self.assertSetSize(tomoSet, size=2)
        self.assertEqual(tomoSet.getSamplingRate(), self.samplingRate)
        self.assertEqual(tomoSet.getDim(), (141, 281, 91))

        return protImportTomo

    def _runTomosegmemTV(self, protImportTomo):
        print(magentaStr("\n==> Segmenting the membranes:"))
        protTomosegmemTV = self.newProtocol(
            ProtTomoSegmenTV,
            inTomograms=getattr(protImportTomo, 'outputTomograms', None),
            mbThkPix=2,
            mbScaleFactor=10,
            blackOverWhite=False
        )
        protTomosegmemTV = self.launchProtocol(protTomosegmemTV)
        tomoMaskSet = getattr(protTomosegmemTV, 'outputSetofTomoMasks', None)

        # Check output set
        self.assertSetSize(tomoMaskSet, size=2)
        self.assertEqual(tomoMaskSet.getSamplingRate(), self.samplingRate)
        self.assertEqual(tomoMaskSet.getDim(), (141, 281, 91))

        # Check generated files
        for file in self.virtualTomos:
            self.assertTrue(exists(protTomosegmemTV._getExtraPath(removeBaseExt(file) + '_flt.mrc')))

    def test_tomosegmemtv(self):
        protImportTomo = self._importTomograms()
        self._runTomosegmemTV(protImportTomo)
