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
import platform
import string
import tempfile
from os.path import join
from random import choices
import pwem
import os
from pyworkflow.utils import Environ
from tomosegmemtv.constants import *

_references = ['MartinezSanchez2014']
__version__ = '3.1.1'
_logo = "icon.png"


class Plugin(pwem.Plugin):

    _homeVar = TOMOSEGMEMTV_HOME_VAR
    _pathVars = [TOMOSEGMEMTV_HOME_VAR]
    _url = "https://github.com/scipion-em/scipion-em-tomosegmemtv"

    @classmethod
    def _defineVariables(cls):
        cls._defineEmVar(TOMOSEGMEMTV_HOME_VAR, TOMOSEGMEMTV_DEFAULT_HOME)

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
        # centOS distro requires an additional environment variable. However, the platform module does not contain the
        # word or rhel or similar, but ubuntu does. Thus, for the moment, this will be simplified checking only if the
        # distro is ubuntu or not
        if 'ubuntu' not in platform.version().lower():
            environ.update({'LD_PRELOAD': join(runtimePath, 'bin', 'glnxa64', 'glibc-2.17_shim.so')})
        return environ

    @classmethod
    def defineBinaries(cls, env):
        TOMOSEGMEMTV_INSTALLED = '%s_installed' % TOMOSEGMEMTV
        # At this point of the installation execution cls.getHome() is None, so the em path should be provided
        binaryHome = join(pwem.Config.EM_ROOT, TOMOSEGMEMTV_DEFAULT_HOME)
        tomosegmemtvHome =  os.path.join(binaryHome, TOMOSEGMEMTV)
        membraneAnnotatorHome = os.path.join(binaryHome, MEMBANNOTATOR_EM_DIR)
        dlZipFile = TOMOSEGMEMTV + '.zip'
        # TomoSegMemTV
        commands = []

        # First part downloading and extracting tomoSegmemTV
        installationCmd = 'wget %s -O %s && ' % (TOMOSEGMEMTV_DL_URL, dlZipFile)
        installationCmd += 'mkdir %s && ' % tomosegmemtvHome
        installationCmd += 'unzip %s -d %s && ' % (os.path.join(binaryHome, dlZipFile), tomosegmemtvHome)
        installationCmd += 'touch %s' % TOMOSEGMEMTV_INSTALLED  # Flag installation finished
        commands.append((installationCmd, TOMOSEGMEMTV_INSTALLED ))

        # Membrane Annotator
        cls._genMembAnnCmd(membraneAnnotatorHome, commands)

        env.addPackage(TOMOSEGMEMTV,
                       version=TOMOSEGMEMTV_VERSION,
                       tar='void.tgz',
                       commands=commands,
                       neededProgs=["wget", "tar"],
                       default=True)

    @classmethod
    def runMembraneAnnotator(cls, protocol, arguments, env=None, cwd=None):
        """ Run membraneAnnotator command from a given protocol. """
        protocol.runJob(cls.getHome(MEMBANNOTATOR_EM_DIR, 'application', MEMBANNOTATOR_BIN), arguments, env=env, cwd=cwd)
    @classmethod
    def getProgram(cls, program):
        return join(cls.getHome(TOMOSEGMEMTV, 'bin', program))

    @classmethod
    def runTomoSegmenTV(cls, protocol, program, args, cwd=None):
        """ Run tomoSegmenTV command from a given protocol. """
        protocol.runJob(cls.getProgram(program), args, cwd=cwd)

    @classmethod
    def getMCRPath(cls):
        return cls.getHome(MEMBANNOTATOR_EM_DIR, 'v99')

    @classmethod
    def _genMembAnnCmd(cls, membraneAnnotatorHome, commands):

        tmpDir = tempfile.gettempdir()
        tgzPath = join(tmpDir, Plugin._getMembraneAnnotatorTGZ())
        tgzExtractionPath= join(tmpDir, Plugin._getDefaultMembAnn())

        commands.append(('wget %s -P %s' % (cls._getMembraneAnnotatorDownloadUrl(), tmpDir),
                                                tgzPath))
        commands.append(('tar zxf %s -C %s' % (tgzPath, tmpDir), tgzExtractionPath))
        commands.append(('%s.install -mode silent -agreeToLicense yes -destinationFolder %s' % \
                           (join(tgzExtractionPath, Plugin._getDefaultMembAnn()), membraneAnnotatorHome),membraneAnnotatorHome))

    @staticmethod
    def _getMembraneAnnotatorTGZ():
        return Plugin._getDefaultMembAnn() + '.tar.gz'

    @classmethod
    def _getMembraneAnnotatorDownloadUrl(cls):
        return 'http://scipion.cnb.csic.es/downloads/scipion/software/em/' + cls._getMembraneAnnotatorTGZ()

    @staticmethod
    def _getDefaultMembAnn():
        return MEMBANNOTATOR + '-' + MEMBANNOTATOR_DEFAULT_VERSION

    @staticmethod
    def _genTmpDest():
        return join('/tmp', Plugin._getDefaultMembAnn() + '_' + ''.join(choices(string.ascii_lowercase, k=4)))

