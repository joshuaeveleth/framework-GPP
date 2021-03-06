#!/usr/bin/env python
#
# This file is protected by Copyright. Please refer to the COPYRIGHT file 
# distributed with this source distribution.
# 
# This file is part of REDHAWK core.
# 
# REDHAWK core is free software: you can redistribute it and/or modify it under 
# the terms of the GNU Lesser General Public License as published by the Free 
# Software Foundation, either version 3 of the License, or (at your option) any 
# later version.
# 
# REDHAWK core is distributed in the hope that it will be useful, but WITHOUT 
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
# 
# You should have received a copy of the GNU Lesser General Public License 
# along with this program.  If not, see http://www.gnu.org/licenses/.
#

import os, sys, commands, logging, platform, shutil, socket
from ossie import parsers
from ossie.utils.model import _uuidgen as uuidgen

class ConfigurationError(StandardError):
    pass

class DevConfig(object):
    def __init__(self, options):
        # Basic setup
        self._log = logging.getLogger('DevConfig')
        self.hostname = socket.gethostname()
        self.options = options
        self.location = options.location
        
        # Verify the base GPP profile exists
        self.gpp_templates = {"spd": os.path.join(self.location,"GPP.spd.xml"),
                              "prf": os.path.join(self.location,"GPP.prf.xml"),
                              "scd": os.path.join(self.location,"GPP.scd.xml")}

        for template in self.gpp_templates.values():
            if not os.path.exists(template):
                raise ConfigurationError("%s missing" % template)
            
        # Figure out where we are going to write the GPP profile
        self.gpp_path = os.path.join(self.location)
        
        self.props = {}

    def register(self):
        if not self.options.silent:
            self._log.debug("Registering...")
        self._gather_system_information()
        self._updateGppPrf()

    def _gather_system_information(self):
        # get some platform information
        self.props['os_name']    = platform.system()
        self.props['os_version'] = platform.release()
        tmp_uname_p    = platform.processor()
        tmp_proc_map   = {'i386':'x86', 
                          'i686':'x86', 
                          'x86_64':'x86_64', 
                          'armv7l':'armv7l'}
        self.props['processor_name']  = tmp_proc_map.get(tmp_uname_p, 'x86')

        self._gather_java_information()
        self._gather_python_information()
        self._gather_xmidas_information()
        self._gather_nextmidas_information()
        self._gather_mcastnic_information()
        self._gather_diskrate_information()
        
        # Output some debug information
        if not self.options.silent:
            self._log.debug("System Information for: <" + self.hostname + ">")
            self._log.debug("  %-30s %s", "Node", self.location)
            k = self.props.keys()
            k.sort()
            for n in k:
                self._log.debug("  %-30s %s ", n, self.props[n])
        
    def _gather_java_information(self):
        # Get some information about the Java version, this is a bit tricky since it is not
        # uncommon for bad versions of Java to be installed. The most common issues are:
        #  1. Using a non-standard Java version            -+
        #  2. Using an ancient Java version                 +- The default version of Java on RHEL 4
        #  3. Using a 32-bit version on a 64-bit platform  -+  violates these
        #
        # For example, if the Java version is listed as 1.x.y_zz, you will get:
        #    self.java_version = '1.x.y'
        #    self.java_release =    x.y000zz   # all Java version begin with "1." so we drop that here
        self.java_version = "0.0.0"
        self.java_release = 0.0
        try:
            version_output = commands.getoutput("java -version").strip().split('\n')
            version_start  = version_output[0]
            version        = "0.0.0"
            update         = 0
          
            if (version_output[0].startswith('java version "') and version_output[0].endswith('"')):
                version = version_output[0][14:-1]  # may be in the form '1.6.0' or '1.6.0_13' (or '1.6.0u13')
                if (version.find('_') > 0):
                    update  = version[version.find('_')+1:]
                    version = version[0:version.find('_')]
                elif (version.find('u') > 0): # historically some versions have used 'u' rather than '_'
                    update  = version[version.find('u')+1:]
                    version = version[0:version.find('u')]
          
            if (version_output[2].lower().find("64-bit") > 0):
                bits = 64
            elif (version_output[2].lower().find("32-bit") > 0):
                bits = 32 # extremely uncommon
            else:
                bits = 32 # extremely common
          
            if ((bits == self.procbits) and (len(version) == 5) and version.startswith("1.")):
                self.java_version = version
                self.java_release = float(version[2:]) + float(update)*0.000001
        except:
            self.java_version = "0.0.0"
            self.java_release = 0.0
       
    def _gather_python_information(self): 
        # Get some information about the Python version. For example, if the version is
        # listed as x.y.z, you will get:
        #    self.python_version = 'x.y.z'
        #    self.python_release =  x.y0000z
        self.python_version = "0.0.0"
        self.python_release = 0.0
        try:
            version_output = sys.version.strip().split('\n')
            version_start  = version_output[0]
          
            if ((version_start[1] == '.') and (version_start[3] == '.') and (version_start[5] == ' ')):
                self.python_version = version_start[:5]  # should may be in the form '2.3.4'
                self.python_release = self.ver2rel(self.python_version)
        except:
            self.python_version = "0.0.0"
            self.python_release = 0.0
        
    def _gather_xmidas_information(self):
        # Get some information about the X-Midas version. For example, if the version is
        # listed as x.y.z, you will get:
        #    self.xmidas_version = 'x.y.z'
        #    self.xmidas_release =  x.y0000z
        self.xmidas_version = "0.0.0"
        self.xmidas_release = 0.0
        try:
            version_output = commands.getoutput("cat $XMDISK/xm/version.txt").strip().split('\n')
            version_start  = version_output[0].strip()
          
            if (version_start.startswith('X-Midas ')):
                version = version_start[8:].strip()
                if ((version[1] == '.') and (version[3] == '.') and (version[5] == ' ')):
                    self.xmidas_version = version[:5]  # should may be in the form '4.6.2'
                    self.xmidas_release = self._ver2rel(self.xmidas_version)
        except:
            self.xmidas_version = "0.0.0"
            self.xmidas_release = 0.0
        
    def _gather_nextmidas_information(self):
        # Get some information about the NeXtMidas version. For example, if the version is
        # listed as x.y.z, you will get:
        #    self.nextmidas_release =  x.y0000z
        self.nextmidas_version = "0.0.0"
        self.nextmidas_release = 0.0
        try:
            version_output = commands.getoutput("cat $NMROOT/nxm/sys/version.txt").strip().split('\n')
            version_start  = version_output[1].strip()
          
            if (version_start.startswith('** NeXtMidas Version: ')):
                version = version_start[22:].strip()
                if ((version[1] == '.') and (version[3] == '.') and (version[5] == ' ')):
                    self.nextmidas_version = version[:5]  # should may be in the form '2.8.0'
                    self.nextmidas_release = self._ver2rel(self.nextmidas_version)
        except:
            self.nextmidas_version = "0.0.0"
            self.nextmidas_release = 0.0
        
    def _ver2rel(self, ver):
        return float(ver[0:1]) + float(ver[2:3])*0.1 + float(ver[4:5])*0.000001

    def _gather_mcastnic_information(self):
        if not self.options.silent:
            self._log.debug("Checking nic capacity...")
        
        # If the multicast NIC isn't specified, attempt to locate using the default route 
        if not self.options.mcastnic:
            text = commands.getoutput("/sbin/route -n").split("\n")
            for line in text[2:]:
                fields = [x.strip() for x in line.split()]
                if fields[0] == "224.0.0.0":
                    self.options.mcastnic = fields[7]
                    if self.options.mcastnic.find(".") != -1:
                        self.options.mcastnic = self.options.mcastnic.split(".")[0]
                    if not self.options.silent:
                        self._log.info("Auto-detected %s as multicast nic", self.options.mcastnic)
                    break
            
        if not self.options.mcastnic:
            if not self.options.silent:
                #self._log.warn("You must provide a multicast NIC port in order to have NIC capacity managment")
                return
        self.props["mcastnicInterface"] = self.options.mcastnic
        testInterface = self.options.mcastnic

        # Check if the interface is bonded and adjust accordingly by getting the active enslaved interface
        bondpath = '/sys/class/net/%s/bonding/active_slave' % testInterface
        if os.path.exists(bondpath):
            try:
                bondfile = open(bondpath, 'r')
                bondintf = bondfile.readline(100)
                testInterface = bondintf.strip()
                if not self.options.silent:
                    self._log.debug("Ingress/egress will be calculated using the active slave interface '%s' of bonded interface '%s'" % (testInterface, self.options.mcastnic))
                bondfile.close()
            except:
                if not self.options.silent:
                    self._log.warn("Unable to read information for bonded multicast interface")
                return
        
        # Must be root to query the interface
        if os.getuid() != 0:
            if not self.options.silent:
                self._log.warn("You must run nodeconfig.py as root in order to get a calculated nic capacity for devices")
            self.props["mcastnicIngressTotal"] = 0
            self.props["mcastnicEgressTotal"] = 0
            return
        
        (exitstatus, ethtool_info) = commands.getstatusoutput("/sbin/ethtool " + testInterface)
        if exitstatus != 0:
            if not self.options.silent:
                self._log.debug("Invalid multicast NIC provided.")
            return

        speed = ''
        link = ''
        duplex = 'Full'
        for i in ethtool_info.splitlines():
            if 'Speed:' in i:
                speed = i.strip().lstrip('Speed: ').strip()
            elif 'Link detected:' in i:
                link = i.strip().lstrip('Link detected: ').strip()
            elif 'Duplex:' in i:
                duplex = i.strip().lstrip('Duplex: ').strip()

        # check link status
        link = link.upper()
        if link == 'YES':
            link = True
        elif link == 'NO':
            link = False
            if not self.options.silent:
                self._log.warn("Multicast NIC not up.")
        else:
            link = False
            if not self.options.silent:
                self._log.warn("Unable to determine if multicast NIC is up")

        # get speed
        speed = speed.rstrip('Mb/s')
        if speed.isdigit():
            speed = int(speed)
        else:
            speed = 0

        self.props["mcastnicIngressTotal"] = speed
        self.props["mcastnicEgressTotal"] = speed
        if duplex != "Full":
            if not self.options.silent:
                self._log.debug("Interface is half-duplex.")
            self.props["mcastnicIngressTotal"] = speed / 2
            self.props["mcastnicEgressTotal"] = speed / 2

    def _gather_diskrate_information(self):
        if os.getuid() != 0:
            if not self.options.silent:
                self._log.debug("You must run dynamicnode.py as root in order to get a calculated disk rate for devices")
            return
        
        # find the right disk
        fileSystems = self._get_fileSystems()
        self.props['diskrateTotal'] = []
        for fileSystem in fileSystems:
            dev = fileSystem[0]
            # Ignore certian device types
            if dev in ("tmpfs",):
                continue
            if not os.path.exists(dev):
                if not self.options.silent:
                    self._log.debug("Skipping filesystem '%s' which does not appear to be a physical disk" % dev)
                continue
            
            if not self.options.silent:
                self._log.debug("Checking disk rate for %s ...", dev)
            hdparminfo = commands.getoutput("/sbin/hdparm -t " + dev).splitlines()
            dataline = None
            for i in hdparminfo:
                if (' = ' in i) and ('MB/sec' in i):
                    dataline = i
                    break
            if dataline == None:
                if not self.options.silent:
                    self._log.debug("problems running hdparm for disk rate test")
                return 0
    
            data = dataline.split()
            eidx = data.index('=')
            midx = data.index('MB/sec')
            if midx <= eidx:
                if not self.options.silent:
                    self._log.debug("problems running hdparm for disk rate test")
                return 0
            rate = data[eidx+1]
            self.props['diskrateTotal'].append({"diskrateTotalDevice": dev, "diskrateTotal": rate})
    
    def _get_fileSystems(self):
        """Use df to provide the current status for all file systems on this machine."""
        status, output = commands.getstatusoutput("/bin/df -P -k") # Use the POSIX definition of df for maximum portability
        output = output.split("\n")
        # Validate the first line looks as expected
        fields = output[0].split()
        if fields != ["Filesystem", "1024-blocks", "Used", "Available", "Capacity", "Mounted", "on"]:
            raise OSError, "Unexpected output from /bin/df...check for POSIX compatibility"
        
        result = []
        for line in output[1:]:
            fields = line.split()
            filesystem = fields[0]
            mounted_on = fields[-1]
            total_mbytes = int(fields[1]) / 1024
            used_mbytes = int(fields[2]) / 1024
            available_mbytes = int(fields[3]) / 1024
            result.append((filesystem, mounted_on, total_mbytes, used_mbytes, available_mbytes))
        return result
        
    def _updateGppPrf(self):
        # generate the prf file
        prfpath = os.path.join(self.gpp_path, 'GPP.prf.xml')
        _prf = parsers.PRFParser.parse(prfpath)
        
        # For simple properties, we allow adding in a value either:
        #   1) By command-line param
        #   2) By values we've determined from our nodeconfig tests
        for simple in _prf.get_simple():
            if simple.get_name() in self.props:
                simple.set_value(str(self.props[simple.get_name()]))

        for structseq in _prf.get_structsequence():
            if structseq.get_name() in self.props:
                for values in self.props[structseq.get_name()]:
                    sv = parsers.PRFParser.structValue()
                    for field_id, field_val in values.items():
                        sv.add_simpleref(parsers.PRFParser.simpleRef(refid=field_id, value=str(field_val))) 
                    structseq.add_structvalue(sv)
                               
        prf_out = open(prfpath, 'w')
        prf_out.write(parsers.parserconfig.getVersionXML())
        _prf.export(prf_out,0)
        prf_out.close()

###########################
# Run from command line
###########################
if __name__ == "__main__":

    ##################
    # setup arg parser
    ##################
    from optparse import OptionParser
    parser = OptionParser()
    parser.usage = "%s [options] [simple_prop1 simple_value1]..."
    parser.add_option("--location", dest="location", default=None,
                      help="must give a location for the XML files")
    parser.add_option("--mcastnic", dest="mcastnic", default='',
                      help="Specify the default mcastnic interfaces (i.e. 'eth1'); if none is given the route associated with default multicast is used")
    parser.add_option("--silent", dest="silent", default=False, action="store_true",
                      help="Suppress all logging except errors")
    parser.add_option("-v", "--verbose", dest="verbose", default=False, action="store_true",
                      help="enable verbose logging")

    (options, args) = parser.parse_args()    

    ## Configure logging
    logging.basicConfig(format='%(name)-12s:%(levelname)-8s: %(message)s', level=logging.INFO)
    if options.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    ## grab tmp logger until class is created
    _log = logging.getLogger('DevConfig')

    dev = DevConfig(options)
    try:
        dev.register()
    except ConfigurationError, e:
        _log.error("%s", e)
        sys.exit(1)
