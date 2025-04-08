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
import pyworkflow.tests as pwtests
from pyworkflow.utils import magentaStr, createLink
from tomo.objects import SetOfTomoMasks, SetOfTomograms
from tomo.protocols import ProtImportTomograms
from tomo.protocols.protocol_import_tomograms import OUTPUT_NAME
from tomo.tests import TOMOSEGMEMTV_TEST_DATASET, DataSet_Tomosegmemtv
from tomo.tests.test_base_centralized_layer import TestBaseCentralizedLayer
from tomosegmemtv.protocols import ProtTomoSegmenTV
from tomosegmemtv.protocols.protocol_tomosegmentv import outputObjects


class TestTomosegmemTV(TestBaseCentralizedLayer):
    virtualTomo2 = None
    virtualTomo1 = None
    samplingRate = DataSet_Tomosegmemtv.sRate.value
    tomoDims = DataSet_Tomosegmemtv.tomoDims.value

    @classmethod
    def setUpClass(cls):
        pwtests.setupTestProject(cls)
        ds = pwtests.DataSet.getDataSet(TOMOSEGMEMTV_TEST_DATASET)
        cls.ds = ds
        # Because only one tomogram is provided in the tutorial, 2 links will be created pointing to the same file, so
        # they can be interpreted as a set of two tomograms, making the test complexity closer to the real usage
        cls.virtualTomos = ['vTomo1', 'vTomo2']
        virtualTomos = [cls.getOutputPath( fpath + '.mrc') for fpath in cls.virtualTomos]
        [createLink(ds.getFile('tomogram'), virtualTomo) for virtualTomo in virtualTomos]

    def _importTomograms(self) -> SetOfTomograms:
        print(magentaStr("\n==> Importing data - tomograms:"))
        protImportTomo = self.newProtocol(
            ProtImportTomograms,
            filesPath=self.getOutputPath(),
            filesPattern='vTomo*.mrc',
            samplingRate=self.samplingRate
        )
        protImportTomo = self.launchProtocol(protImportTomo)
        return getattr(protImportTomo, OUTPUT_NAME, None)

    def _runTomosegmemTV(self, inTomograms: SetOfTomograms) -> SetOfTomoMasks:
        print(magentaStr("\n==> Segmenting the membranes:"))
        protTomosegmemTV = self.newProtocol(
            ProtTomoSegmenTV,
            inTomos=inTomograms,
            mbThkPix=2,
            mbScaleFactor=10,
            blackOverWhite=False
        )
        protTomosegmemTV = self.launchProtocol(protTomosegmemTV)
        return getattr(protTomosegmemTV, outputObjects.tomoMasks.name, None)

    def test_tomosegmemtv(self):
        importedTomos = self._importTomograms()
        tomoMasks = self._runTomosegmemTV(importedTomos)
        # Check output set
        self.checkTomoMasks(tomoMasks,
                            expectedSetSize=2,
                            expectedSRate=self.samplingRate,
                            expectedDimensions=self.tomoDims,
                            isHeterogeneousSet=False)