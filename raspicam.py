#!/usr/bin/env python2
import sys
import io
import time
import picamera
import numpy as np
from PIL import Image
from PIL import ImageOps
import threading
import copy
class PiCamera(threading.Thread):
    stream = None
    height=800
    width=600
    def __init__(self, thread_name):
        threading.Thread.__init__(self)
        self.thread_name = thread_name
        self.image_ready = False
        self.image_processed = True
        self.img = None
        self.tostop = False
        self.image_overlay =  None
        self.ovs=[]

    def set_overlay_image(self,image):
        self.image_overlay = image
        print "in set_overlay_image", image.size

    def stop(self):
        self.tostop = True
        print "stop"

    def run(self):
        print self.thread_name
        try:
            with picamera.PiCamera() as camera:
                camera.resolution = (self.height, self.width)
                #camera.resolution = (800, 600)
                # Start a preview and let the camera warm up for 2 seconds
                camera.start_preview()
                time.sleep(2)
        
                # Note the start time and construct a stream to hold image data
                # temporarily (we could write it directly to connection but in this
                # case we want to find out the size of each capture first to keep
                # our protocol simple)
                start = time.time()
                self.stream = io.BytesIO()
                for foo in camera.capture_continuous(self.stream, 'jpeg'):
                    if self.tostop:
                        print "before break"
                        break
                    #delete overlays
                    for o in self.ovs:
                        camera.remove_overlay(o)

                    self.ovs=[]


                    # Write the length of the capture to the stream and flush to
                    # ensure it actually gets sent
                    # Rewind the stream and send the image data over the wire
                    self.stream.seek(0)
                    self.image_ready = False
                    t1=time.time()
                    #wait to the image to be processed
                    while (not self.image_processed) and (time.time() - t1) < 1:
                        time.sleep(0.1)
                    self.img=copy.deepcopy(Image.open(self.stream))
                    self.image_ready = True
                    
                    if self.image_overlay:
                        print "before create pad"
                        pad = Image.new('RGB', (
                                    ((self.image_overlay.size[0] + 31) // 32) * 32,
                                    ((self.image_overlay.size[1] + 15) // 16) * 16,
                                     ))
                        print "before pad paste"
                        pad.paste(self.image_overlay, (0, 0)) 
                        print "before add overlay", pad.size
                        o = camera.add_overlay(pad.tobytes(),
                                size=self.image_overlay.size)
                        print "after add overlay", pad.size
                        o.alpha = 128
                        o.layer = 3
                        self.ovs.append(o)
                        #o = camera.add_overlay(np.getbuffer(self.np_overlay), layer=3, alpha=64)
                        #o = camera.add_overlay(np.getbuffer(a), layer=3, alpha=64)
                        time.sleep(0.1)
        
                    # Reset the stream for the next capture
                    self.stream.seek(0)
                    self.stream.truncate()
        except:
            raise
        finally:
            pass


if __name__ == '__main__':

    # Create two threads as follows
    picam1 = PiCamera("Thread-1")
    vert = 0
    try: 
        picam1.start()
        
        img=None
        i=0
        while 1:
            time.sleep(0.250)
            picam1.image_processed = False
            t1=time.time()
            #wait for the image to be ready
            while (not picam1.image_ready) and (time.time() - t1) < 1:
                time.sleep(0.1)
            img=picam1.img
            if img:
                try:
                    i += 1
                    img.save('Images/test%04d.jpg' % (i) ,'JPEG')
                    time.sleep(.1)

                    #a = np.zeros((480, 640, 3), dtype=np.uint8)
                    #a[150, :, :] = 0xff
                    #a[:, vert, :] = 0xff
                    #vert += 10
                    image_path='Returns/annotated_img_Roch_0002.jpg'
                    img1 = Image.open(image_path)

                    picam1.set_overlay_image(img1)
                except IOError:
                    pass
                finally:
                    picam1.image_processed = True
            #print "in a loop"

      
    except (KeyboardInterrupt,SystemExit):
        picam1.stop()
        picam1.join()
