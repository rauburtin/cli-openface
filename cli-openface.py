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
from PIL import ImageOps
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
                #img_bytes = open("TrainPhotos/IMG_0080.JPG","r").read()


                #If there are images to load, we send it
                if self.images_to_train:
                    if self.images_to_train.keys():
                        self.person = self.images_to_train.keys()[0]
                        if not self.person in self.people:
                            self.add_person(self.person)
                        if self.images_to_train[self.person]:
                            if not self.training:
                                self.set_training_mode(True)

                            self.photo =  self.images_to_train[self.person][0]
                            del self.images_to_train[self.person][0]
                            if not  self.images_to_train[self.person]:
                                del self.images_to_train[self.person]

                if not self.images_to_train:
                    if self.training:
                        self.set_training_mode(False)
                    person = random.choice(os.listdir('TestPhotos'))
                    self.photo=os.path.join('TestPhotos',person,random.choice(os.listdir(os.path.join('TestPhotos',person))))

                #this one is not detected as a visage
                #photo = "TrainPhotos/IMG_0077.JPG"
                #OK
                #photo = "TrainPhotos/IMG_0085.JPG"

                #img = Image.open("TrainPhotos/IMG_0080.JPG")
                print 'self.images_to_train',self.images_to_train
                print 'photo',self.photo
                print 'self.training',self.training
                if self.photo:
                    img = Image.open(self.photo)
                    #img = img.resize((400,300))  
                    #img.thumbnail((400,300))
                    img = ImageOps.fit(img,(400,300))
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

            self.factory.reactor.callLater(0.250,cb_send_frame_loop)


        print "callLater cb_send_frame_loop"
        self.factory.reactor.callLater(0,cb_send_frame_loop)
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
        self.i_aligned=0 #just a counter for the image aligned
        self.i_annotated=0 #just a counter for the  annotated image
        self.images_to_train={} #The list of people and images to load first 
        self.person=""
        self.photo=""
        self.speople="" #string of people


        def load_images():
            for di in os.listdir('TrainPhotos'):
                for fi in os.listdir(os.path.join('TrainPhotos',di)):
                    if not self.images_to_train.get(di):
                        self.images_to_train[di]=[]
                    self.images_to_train[di].append(os.path.join('TrainPhotos',di,fi))
            print 'self.images_to_train',self.images_to_train
        def hello():
            payload = json.dumps({'type': 'NULL'}, ensure_ascii = False).encode('utf8')
            self.sendMessage(payload, isBinary = True)
            #self.sendMessage(b"\x00\x01\x03\x04", isBinary=True)
            #self.factory.reactor.callLater(2, hello)
            self.sent_times.append(datetime.now())

            self.factory.reactor.callLater(0,load_images)



        # start sending messages every second ..
        hello()


    def transform_image_from_rgb_v0(self,rgb_content):
            #Not very fast on raspberry
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
            self.i_aligned += 1

            img.save("Returns/transform_image_from_rgb%04d.jpg" %(self.i_aligned) ,"JPEG")
            return data

    def transform_image_from_rgb_v1(self,rgb_content):
            #Try with numpy
            # import numpy as np
            # eventually set frpom rgb_content and chenge the type after
            # a1=np.array[rgb]
            # a2=np.reshape(a1,(dlen/4,4))
            # eventually swap column 0,1,2
            # a2[:,-1:]=255
            dlen=len(rgb_content)
            rgb1=np.array(rgb_content).astype(np.uint8)
            rgb=np.reshape(rgb1,(dlen/4/96,96,4))
            rgb[:,:,3]=255
            buf=np.zeros(rgb.shape, dtype=np.uint8)
            buf[:,:,2]=rgb[:,:,0]
            buf[:,:,1]=rgb[:,:,1]
            buf[:,:,0]=rgb[:,:,2]
            #buf=np.fliplr(buf)


            data=buf.tobytes()
            img=Image.frombytes("RGBA",(96,72),data)
            #img=Image.fromarray(buf)
            #img = Image.open(imgF)
            self.i_aligned += 1
            print "data len",len(data)

            img.save("Returns/transform_image_from_rgb%04d.jpg" %(self.i_aligned) ,"JPEG")
            return data
    def transform_image_from_rgb(self,rgb_content):
            #Try with numpy
            #TODO fix color and width x height
            dlen=len(rgb_content)
            rgb1=np.array(rgb_content).astype(np.uint8)
            rgb=np.reshape(rgb1,(96,dlen/4/96,4))
            rgb[:,:,3]=255
            buf=np.zeros(rgb.shape, dtype=np.uint8)
            buf[:,:,2]=rgb[:,:,0]
            buf[:,:,1]=rgb[:,:,1]
            buf[:,:,0]=rgb[:,:,2]
            buf[:,:,3]=rgb[:,:,3]


            data=buf.tobytes()
            #img=Image.frombytes("RGBA",(96,72),data)
            img=Image.fromarray(buf,"RGBA")
            #img = Image.open(imgF)
            self.i_aligned += 1
            print "data len",len(data)

            img.save("Returns/transform_image_from_rgb%04d.jpg" %(self.i_aligned) ,"JPEG")
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
            print "new_image_ident", j.get('identity')

        elif j.get('type') == "IDENTITIES":
            identities = j.get('identities')
            print 'identities',identities
            self.speople=""
            len_id = len(identities)
            if len_id > 0:
                for id_idx in identities:
                    identity = "Unknown"
                    if id_idx != -1:
                        identity=self.people[id_idx]
                        if not self.speople:
                            self.speople += identity
                        else:
                            self.speople += "_" + identity
            else:
                self.speople="Nobody"
            print "speople %s" %(self.speople)
        elif j.get('type') == "ANNOTATED":
            self.i_annotated += 1
            data_url=j.get('content')
            head = "data:image/png;base64,"
            url_quoted=data_url[len(head):]
            url_unquoted=urllib.unquote(url_quoted)
            imgdata = base64.b64decode(url_unquoted)
            imgF = StringIO.StringIO()
            imgF.write(imgdata)
            imgF.seek(0)
            img = Image.open(imgF)
            img.save("Returns/annotated_img_%s_%04d.jpg" %(self.speople,
                self.i_annotated),"JPEG")
        else:
            print "Unrecognized message type: %s" % (j.get("type"))


    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))


if __name__ == '__main__':


    openface_server = os.getenv("OPENFACE_SERVER")
    if not openface_server:
        openface_server = "127.0.0.1"

    #f=open("cli-open.log","w")

    #TODO: Do not show the erreor if there is one
    #log.FileLogObserver.emit=myFLOemit
    log.startLogging(sys.stdout)

    factory = WebSocketClientFactory(u"ws://%s:9000" % (openface_server))
    factory.protocol = MyClientProtocol

    reactor.connectTCP(openface_server, 9000, factory)
    reactor.run()
