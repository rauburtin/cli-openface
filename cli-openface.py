#!/usr/bin/env python2
###############################################################################
#
# The MIT License (MIT)
#
# Copyright (c) Tavendo GmbH
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
###############################################################################

from autobahn.twisted.websocket import WebSocketClientProtocol, \
    WebSocketClientFactory
import json
import time
from datetime import datetime
from PIL import Image
import base64
import StringIO
import urllib
import sys
import os
import random

from twisted.python import log,util
from twisted.internet import reactor
import numpy as np

def myFLOemit(self,eventDict):
    """Custom emit for FileLogObserver"""
    max_text=256
    text = log.textFromEventDict(eventDict)

    if text is None:
      return
    if len(text)>max_text:
        text=text[:max_text]

    self.timeFormat='[%Y-%m-%d %H:%M:%S]'
    timeStr = self.formatTime(eventDict['time'])
    fmtDict = {'text': text.replace("\n", "\n\t")}
    msgStr = log._safeFormat("%(text)s\n", fmtDict)
    util.untilConcludes(self.write, timeStr + " " + msgStr)
    util.untilConcludes(self.flush)

class MyClientProtocol(WebSocketClientProtocol):
    default_tok=1
    default_num_nulls=20
    def update_rtt(self):
        pass
    def send_state1(self):
        msg = {
                'type': 'ALL_STATE',
                'images': self.images,
                'people': self.people,
                'training': self.training
                }
        payload = json.dumps(msg, ensure_ascii = False).encode('utf8')
        self.sendMessage(payload, isBinary = True)

    def send_frame_loop(self):
        print "start send_frame_loop"
        def cb_send_frame_loop():
            print "cb_send_frame_loop", self.tok
            if self.tok > 0:
                #TODO
                #img_bytes = open("Photos/IMG_0080.JPG","r").read()

                photo = os.path.join("Photos",
                        random.choice(os.listdir('Photos')))

                #img = Image.open("Photos/IMG_0080.JPG")
                img = Image.open(photo)
                img.thumbnail((400,300))
                imgF = StringIO.StringIO()

                img.save(imgF,"JPEG")
                imgF.seek(0)

                img_bytes=imgF.read()
                head = "data:image/jpeg;base64,"
                data_url = head + base64.b64encode(img_bytes)

                msg = {
                        'type': 'FRAME',
                        'dataURL': data_url,
                        'identity': self.default_person
                        }
                payload = json.dumps(msg, ensure_ascii = False).encode('utf8')
                self.sendMessage(payload, isBinary = True)

                self.tok -= 1

            self.factory.reactor.callLater(1,cb_send_frame_loop)


        print "callLater cb_send_frame_loop"
        self.factory.reactor.callLater(1,cb_send_frame_loop)
        #Call send_frame_loop after 250 ms

    def onConnect(self, response):
        print("Server connected: {0}".format(response.peer))

    def onOpen(self):
        print("WebSocket connection open.")
        self.sent_times=[]
        self.received_times=[]
        self.tok = self.default_tok
        self.num_nulls=0
        self.images=[]
        self.people=[]
        self.training=False
        self.default_person = -1

        def deactivate_training():
            print "deactivate_training"
            self.set_training_mode(False)

        def add_roch():
            print "add_roch"
            self.add_person("Roch")
            self.factory.reactor.callLater(10,deactivate_training)

        def activate_training():
            print "activate_training"
            self.set_training_mode(True)
            self.factory.reactor.callLater(1,add_roch)


        def hello():
            payload = json.dumps({'type': 'NULL'}, ensure_ascii = False).encode('utf8')
            self.sendMessage(payload, isBinary = True)
            #self.sendMessage(b"\x00\x01\x03\x04", isBinary=True)
            #self.factory.reactor.callLater(2, hello)
            self.sent_times.append(datetime.now())

            self.factory.reactor.callLater(0,activate_training)



        # start sending messages every second ..
        hello()


    def transform_image_from_rgb(self,rgb_content):
            dlen=len(rgb_content)
            rgb = [int(x) for x in rgb_content]
            print "dlen",dlen
            data=""
            t=0
            for i in range(0,dlen,4):
                data += chr(rgb[t+2])
                data += chr(rgb[t+1])
                data += chr(rgb[t])
                data += chr(255)
                t += 3

            print "data len",len(data)
            img=Image.frombytes("RGBA",(96,72),data)
            #imgF = StringIO.StringIO()
            #imgF.write(data)
            #imgF.seek(0)
            #img = Image.open(imgF)

            img.save("transform_image_from_rgb.jpg","JPEG")
            return data


    def set_training_mode(self,training):
        self.training = training
        msg = {
                'type': 'TRAINING',
                'val': self.training
                }
        payload = json.dumps(msg, ensure_ascii = False).encode('utf8')
        self.sendMessage(payload, isBinary = True)

    def add_person(self,name):
        self.default_person = len(self.people)
        self.people.append(name)

        msg = {
                'type': 'ADD_PERSON',
                'val': name
                }
        payload = json.dumps(msg, ensure_ascii = False).encode('utf8')
        self.sendMessage(payload, isBinary = True)


    def onMessage(self, payload, isBinary):
        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
        else:
            print("Text message received: {0}".format(payload.decode('utf8')))
        j = json.loads(payload)
        if j.get('type') == "NULL":
            self.received_times.append(datetime.now())
            self.num_nulls += 1
            if self.num_nulls == self.default_num_nulls:
                self.update_rtt()
                self.send_state1()
                print "before send_frame_loop"
                self.send_frame_loop()
                print "after send_frame_loop"
            else:
                payload = json.dumps({'type': 'NULL'}, ensure_ascii = False).encode('utf8')
                self.sendMessage(payload, isBinary = True)
                self.sent_times.append(datetime.now())
        elif j.get('type') == "PROCESSED":
            self.tok +=1
        elif j.get('type') == "NEW_IMAGE":
            self.images.append({
                'hash':j.get('hash'),
                'identity': j.get('identity'),
                'image': self.transform_image_from_rgb(j.get('content')),
                'representation': j.get('representation')
                })

        elif j.get('type') == "IDENTITIES":
            identities = j.get('identities')
            print 'identities',identities
            speople=""
            len_id = len(identities)
            if len_id > 0:
                for id_idx in identities:
                    identity = "Unknown"
                    if id_idx != -1:
                        identity=self.people[id_idx]
                        speople += identity+","
            else:
                speople="Nobody detected."
            print "speople %s" %(speople)
        elif j.get('type') == "ANNOTATED":
            data_url=j.get('content')
            head = "data:image/png;base64,"
            url_quoted=data_url[len(head):]
            url_unquoted=urllib.unquote(url_quoted)
            imgdata = base64.b64decode(url_unquoted)
            imgF = StringIO.StringIO()
            imgF.write(imgdata)
            imgF.seek(0)
            img = Image.open(imgF)
            img.save("annotated_img.jpg","JPEG")
        else:
            print "Unrecognized message type: %s" % (j.get("type"))


    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))


if __name__ == '__main__':


    #f=open("cli-open.log","w")

    #log.FileLogObserver.emit=myFLOemit
    log.startLogging(sys.stdout)

    factory = WebSocketClientFactory(u"ws://127.0.0.1:9000", debug=False)
    factory.protocol = MyClientProtocol

    reactor.connectTCP("127.0.0.1", 9000, factory)
    reactor.run()
