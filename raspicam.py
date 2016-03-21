#!/usr/bin/env python2
import sys
import io
import time
import picamera
import numpy as np
from PIL import Image
import threading
import copy
class PiCamera(threading.Thread):
    stream = None
    def __init__(self, thread_name):
        threading.Thread.__init__(self)
        self.thread_name = thread_name
        self.image_ready = False
        self.image_processed = True
        self.img = None
        self.tostop = False
        self.np_overlay=np.zeros((480, 640, 3), dtype=np.uint8)

    def set_overlay_image(self,np_array):
        self.np_overlay=np_array

    def stop(self):
        self.tostop = True
        print "stop"

    def run(self):
        print self.thread_name
        try:
            with picamera.PiCamera() as camera:
                camera.resolution = (640, 480)
                #camera.resolution = (400, 300)
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
                    
                    o = camera.add_overlay(np.getbuffer(self.np_overlay), layer=3, alpha=64)
                    #o = camera.add_overlay(np.getbuffer(a), layer=3, alpha=64)
                    time.sleep(0.1)
                    camera.remove_overlay(o)
        
                    # If we've been capturing for more than 30 seconds, quit
                    if time.time() - start > 30:
                        break
                    # Reset the stream for the next capture
                    self.stream.seek(0)
                    self.stream.truncate()
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

                    a = np.zeros((480, 640, 3), dtype=np.uint8)
                    a[240, :, :] = 0xff
                    a[:, vert, :] = 0xff
                    vert += 10
                    picam1.set_overlay_image(a)
                except IOError:
                    pass
                finally:
                    picam1.image_processed = True
            #print "in a loop"

      
    except (KeyboardInterrupt,SystemExit):
        picam1.stop()
        picam1.join()
