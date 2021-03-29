# **************************************************************************
# *
# * Authors:     Scipion Team
# *
# * your institution
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
# *  e-mail address 'scipion@cnb.csic.es'
# *
# **************************************************************************

from os.path import join
import pwem
import os

from pyworkflow.utils import Environ

from tomosegmemtv.constants import TOMOSEGMEMTV_HOME, TOMOSEGMEMTV, TOMOSEGMEMTV_DEFAULT_VERSION, MEMBANNOTATOR, \
    MEMBANNOTATOR_DEFAULT_VERSION, TOMOSEGMENTV

_references = ['MartinezSanchez2014']
__version__ = '3.0.0'


class Plugin(pwem.Plugin):

    _homeVar = TOMOSEGMEMTV_HOME
    _pathVars = [TOMOSEGMEMTV_HOME]

    @classmethod
    def _defineVariables(cls):
        cls._defineEmVar(TOMOSEGMEMTV_HOME, TOMOSEGMEMTV + '-' + TOMOSEGMEMTV_DEFAULT_VERSION)

    @classmethod
    def getMembSegEnviron(cls):
        """ Setup the environment variables needed to launch pyseg. """
        environ = Environ(os.environ)
        runtimePath = cls.getMCRPath()

        # Add required disperse path to PATH and pyto path to PYTHONPATH
        environ.update({'LD_LIBRARY_PATH': os.pathsep.join([join(runtimePath, 'runtime', 'glnxa64'),
                                                            join(runtimePath, 'bin', 'glnxa64'),
                                                            join(runtimePath, 'sys', 'os', 'glnxa64'),
                                                            join(runtimePath, 'sys', 'opengl', 'lib', 'glnxa64')])
                        })
        return environ

    @classmethod
    def defineBinaries(cls, env):
        # At this point of the installation execution cls.getHome() is None, so the em path should be provided
        pluginHome = join(pwem.Config.EM_ROOT, TOMOSEGMEMTV + '-' + TOMOSEGMEMTV_DEFAULT_VERSION)
        tomoSegmenTVHome = join(pluginHome, TOMOSEGMENTV)
        membraneAnnotatorHome = join(pluginHome, MEMBANNOTATOR)

        TOMOSEGMEMTV_INSTALLED = '%s_installed' % TOMOSEGMEMTV
        # TomosegmenTV: only the directory will be generated, because the binaries must be downloaded manually from José
        # Jesús website, filling a form
        tomosegmemtvInstallcmd = 'mkdir %s && ' % tomoSegmenTVHome
        # Membrane annotator
        # membAnnInstallationCmd = cls._genMembAnnCmd(membraneAnnotatorHome)

        # installationCmd = ' && '.join([tomosegmemtvInstallcmd, membAnnInstallationCmd])
        installationCmd = tomosegmemtvInstallcmd
        installationCmd += 'touch %s' % TOMOSEGMEMTV_INSTALLED  # Flag installation finished

        env.addPackage(TOMOSEGMEMTV,
                       version=TOMOSEGMEMTV_DEFAULT_VERSION,
                       tar='void.tgz',
                       commands=[(installationCmd, TOMOSEGMEMTV_INSTALLED)],
                       neededProgs=["wget", "tar"],
                       default=True)

    @classmethod
    def runMembraneAnnotator(cls, protocol):
        """ Run membraneAnnotator command from a given protocol. """
        protocol.runJob(cls.getHome(MEMBANNOTATOR, 'application', MEMBANNOTATOR))

    @classmethod
    def runTomoSegmenTV(cls, protocol, program, args, cwd=None):
        """ Run tomoSegmenTV command from a given protocol. """
        protocol.runJob(join(cls.getHome(TOMOSEGMENTV, 'bin', program)), args, cwd=cwd)

    @classmethod
    def getMCRPath(cls):
        return cls.getHome(MEMBANNOTATOR, 'v99')

    @classmethod
    def _genMembAnnCmd(cls, membraneAnnotatorHome):
        installationCmd = 'wget %s && ' % cls._getMembraneAnnotatorDownloadUrl(TOMOSEGMEMTV_DEFAULT_VERSION)
        installationCmd += 'mkdir %s && ' % membraneAnnotatorHome
        installationCmd += 'tar zxf %s && ' % (cls._getMembraneAnnotatorTGZ(TOMOSEGMEMTV_DEFAULT_VERSION))
        installationCmd += './%s.install -mode silent -agreeToLicense yes -destinationFolder %s && ' % \
                           (MEMBANNOTATOR, membraneAnnotatorHome)
        return installationCmd

    @staticmethod
    def _getMembraneAnnotatorTGZ(version):
        return MEMBANNOTATOR + '_v' + version + '.tgz'

    @classmethod
    def _getMembraneAnnotatorDownloadUrl(cls, version):
        return 'http://scipion.cnb.csic.es/downloads/scipion/software/em/' + cls._getMembraneAnnotatorTGZ(version)