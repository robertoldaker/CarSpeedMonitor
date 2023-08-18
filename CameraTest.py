from picamera2 import Picamera2
from libcamera import Transform, controls
import time
from pprint import *

from picamera2 import Picamera2, MappedArray
import cv2

picam2 = Picamera2()
    
width=640
height=380
print(f'width={width}, height={height}')
config = picam2.create_preview_configuration(main={"size": (width, height)},
                                             raw=picam2.sensor_modes[1],
                                             lores={"size": (width,height)}
                                             )
pprint(config)

picam2.configure(config)
(w0, h0) = picam2.stream_configuration("main")["size"]
#(w1, h1) = picam2.stream_configuration("lores")["size"]
faces = []



frame_count = 0
frame_rate = 0
st=time.monotonic()
base_image=None
#
colour = (0, 255, 0)
origin = (0, 30)
font = cv2.FONT_HERSHEY_SIMPLEX
scale = 1
thickness = 2
x=y=w=h=0

def apply_timestamp(request):
    global frame_count, st, frame_rate
    global x,y,width,height
    frame_count+=1
    if (frame_count % 10) == 0:
        ft = time.monotonic()
        frame_rate = 10/(ft-st)
        st = time.monotonic()

    str=(f'Frame rate=[{frame_rate:4f}]')
    with MappedArray(request, "main") as m:
        cv2.putText(m.array, str, origin, font, scale, colour, thickness)
        cv2.rectangle(m.array,(x,y),(w+x,h+y),(0,255,0),2)

def process_image(image):
    global base_image, x, y, w, h
    gray = image[:]
    # capture colour for later when measuring light levels
    hsv = cv2.cvtColor(gray, cv2.COLOR_BGR2HSV)
    # convert the frame to grayscale, and blur it
    gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (15,15), 0)

    # if the base image has not been defined, initialize it
    if base_image is None:
        base_image = gray.copy().astype("float")
        
    # compute the absolute difference between the current image and
    # base image and then turn eveything lighter gray than THRESHOLD into
    # white
    frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(base_image))
    thresh = cv2.threshold(frameDelta, 15, 255, cv2.THRESH_BINARY)[1]
    
    # dilate the thresholded image to fill in any holes, then find contours
    # on thresholded image
    thresh = cv2.dilate(thresh, None, iterations=2)
    (cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    biggest_area=0
    # examine the contours, looking for the largest one
    for c in cnts:
        (x1, y1, w1, h1) = cv2.boundingRect(c)
        # get an approximate area of the contour
        found_area = w1*h1 
        # find the largest bounding rectangle
        if (found_area > 175) and (found_area > biggest_area):  
            biggest_area = found_area
            motion_found = True
            x = x1
            y = y1
            w = w1
            h = h1
    

#picam2.pre_callback = apply_timestamp
picam2.start(show_preview=False)

_st=time.monotonic()
_frame_count=0
while True:    
    yuv420 = picam2.capture_array("lores")
    image = cv2.cvtColor(yuv420, cv2.COLOR_YUV420p2RGB)
    process_image(image)
    _frame_count+=1
    if _frame_count % 100==0:
        _ft=time.monotonic()
        print(f'frame_rate={100/(_ft-_st):10.4f}\r')
        _st = time.monotonic()
