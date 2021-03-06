#!/usr/bin/env python
# coding:utf-8



# ------------------------------------------------------------------------------
#  Copyright  2020. NAVER Corp.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ------------------------------------------------------------------------------
import json
import os
import struct

from gevent import socket as gsocket

from Common.Logger import TCLogger
from Events import StreamServerLayer
from PHPAgent.Type import RESPONSE_AGENT_INFO


class FrontAgent(object):
    HEADERSIZE = 8
    def __init__(self, ac, msgCallback):
        self.address =ac.Address
        self.listen_socket = self._bindSocket(self.address)
        self.server = StreamServerLayer(self.listen_socket, self._recvData, self._phpClientSayHello)
        self.msgHandleCallback = msgCallback
        self.hello_callback = []

    def _bindSocket(self,address):
        if address[0] =='/': # treat as unix socket
            if os.path.exists(address):
                os.remove(address)
            listen_socket = gsocket.socket(gsocket.AF_UNIX, gsocket.SOCK_STREAM)
            listen_socket.bind(address)
            listen_socket.listen(256)
            return listen_socket
        elif '@' in address: # treat as tcp port
            ip,port = address.split('@')
            listen_socket = gsocket.socket(gsocket.AF_INET, gsocket.SOCK_STREAM)
            listen_socket.setsockopt(gsocket.SOL_SOCKET, gsocket.SO_REUSEADDR, 1)
            listen_socket.bind((ip,int(port)))
            listen_socket.listen(256)
            return listen_socket

    def _recvData(self, client, buf, buf_sz):
        used = 0

        while used < buf_sz:
            # needs a whole header
            if used + FrontAgent.HEADERSIZE > buf_sz:
                return buf_sz - used

            # needs a whole body
            type, body_len = struct.unpack('!ii', buf[used:used + FrontAgent.HEADERSIZE].tobytes())
            if used + body_len + FrontAgent.HEADERSIZE > buf_sz:
                return buf_sz - used

            used += FrontAgent.HEADERSIZE
            body = buf[used:used + body_len].tobytes()
            self.msgHandleCallback(client, type, body)
            used += body_len

        return 0

    def registerPHPAgentHello(self,hello_cb):
        self.hello_callback.append(hello_cb)

    def _phpClientSayHello(self, client):
        response = {}
        for cb in self.hello_callback:
            data = cb()
            for key in data:
                response[key] = data[key]

        data = json.dumps(response)
        buf  = struct.pack('!ii',RESPONSE_AGENT_INFO,len(data)) + data.encode()
        client.sendData(buf)
        TCLogger.debug("send hello:%d len:%d",client.socket.fileno(),len(buf))


    def start(self):
        self.server.start()

    def stop(self):
        self.server.stop()
        TCLogger.debug("close listen_socket:%d[%s]",self.listen_socket.fileno(),self.address)
        self.listen_socket.close()


