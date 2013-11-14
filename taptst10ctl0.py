#!/usr/bin/env python
# 
# Copyright (C) 2013 NONAKA Kimihiro <nonakap@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

#
# SANWA SUPPLY TAP-TST10 control tool
#
# require: pyusb, libusb
# tested on python-2.7.5nb3, pyusb-0.4.2nb1, libusb-0.1.12nb3
#
# My analysis result: http://d.hatena.ne.jp/nonakap/20130716#p2
#

__version__ = '20131114'
import usb
import datetime

VENDOR=0x040b
PRODUCT=0x2201

ENDPOINT=0x82

class TAPTST10Control:

    def __init__(self, idVendor = VENDOR, idProduct = PRODUCT):
        busses = usb.busses()
        for bus in busses:
            devices = bus.devices
            for device in devices:
                if (device.idVendor, device.idProduct) == (idVendor, idProduct):
                    self.device = device
                    self.configuration = self.device.configurations[0]
                    self.interface = self.configuration.interfaces[0][0]
                    self.endpoints = []
                    self.pipes = []
                    for ep in self.interface.endpoints:
                        self.endpoints.append(ep)
                        self.pipes.append(ep.address)
                    return
        raise RuntimeError, 'Device not found'

    def __del__(self):
        if hasattr(self, 'handle'):
            try:
                self.close()
            except RuntimeError:
                pass

    def open(self):
        if hasattr(self, 'handle'):
            raise RuntimeError, 'Device already opened'
        self.handle = self.device.open()
        self.handle.setConfiguration(self.configuration)
        self.handle.claimInterface(self.interface)
        self.handle.setAltInterface(self.interface)

    def close(self):
        if hasattr(self, 'handle'):
            self.handle.releaseInterface()
            del self.handle
        else:
            raise RuntimeError, 'Device not opened'

    def getData(self, msg):
        first = True
        count = 0
        size = 0
        minute = 0
        second = 0
        watts = []
        kWhs = []

        ret = self.handle.interruptWrite(1, msg)
        assert ret == 3
        while True:
            data = self.handle.interruptRead(2, 17, 1000)
            # dump raw data
            #print(" ".join("{:02x}".format(x) for x in data))

            if len(data) != 17:
                raise ValueError('response data length is invalid. (%d)' % (len(data)))
            assert data[0] == 0x01

            if first:
                assert data[16] == 0x0a
                minute = data[1]
                second = data[2]
                size = (data[3] << 8) | data[4]
                first = False
            else:
                for x in range(1, 16, 3):
                    watt = ((data[x] & 0x7f) << 8) | data[x+1]
                    if (data[x] & 0x80) == 0x80:
                        watt = watt / 10.0
                    watts.append(watt)
                    kWh = data[x+2] / 100.0
                    if len(kWhs) > 0:
                        kWh = kWh + kWhs[len(kWhs) - 1]
                    kWhs.append(kWh)
                    count = count + 1
                    size = size - 3
                    if size <= 0:
                        break

            if data[16] == 0xfe or size <= 0:
                break

        return count, size, minute, second, watts, kWhs;

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='TAP-TST10 control tool')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-a', '--all', action='store_true',
                       help='fetch all power consumption data')
    args = parser.parse_args()

    msg = '\x02\x18\x0a'

    inst = TAPTST10Control()
    inst.open()

    now = datetime.datetime.now()
    count, size, minute, second, watts, kWhs = inst.getData(msg);
    print "No.,DateTime,Watt,kWh"
    if count > 0:
        watt_unit = datetime.timedelta(minutes=10)
        start_time = now - watt_unit * (count - 1)
        for x in range(count):
            t = start_time.timetuple()
            print "%d,%d/%02d/%02d %02d:%02d,%.1f,%.2f" % (x + 1, t[0], t[1], t[2], t[3], (t[4] / 10) * 10, watts[x], kWhs[x])
            start_time = start_time + watt_unit
