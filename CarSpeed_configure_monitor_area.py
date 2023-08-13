from picamera2 import Picamera2
from libcamera import Transform
import cv2
import time
import math
import datetime


IMAGEWIDTH=640
IMAGEHEIGHT=480

class MonitorArea(object):
    def __init__(self,ulx,uly,lrx,lry):
        self.upper_left_x = ulx
        self.upper_left_y = uly
        self.lower_right_x = lrx
        self.lower_right_y = lry

class ConfigureMonitorArea(object):
    def __init__(self):
        self.area = MonitorArea(0,0,0,0)

    def start(self):
        ix,iy,fx,fy = 0,0,0,0
        drawing = False
        prompt = ""
        setup_complete = False

        # place a prompt on the displayed image
        def prompt_on_image(txt):
            nonlocal prompt,image
            cv2.putText(image, txt, (10, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
            prompt = txt
        
        # mouse callback function for drawing capture area
        def draw_rectangle(event,x,y,flags,param):
            nonlocal ix,iy,fx,fy,drawing,image,prompt
            if event == cv2.EVENT_LBUTTONDOWN:
                drawing = True
                ix,iy = x,y
        
            elif event == cv2.EVENT_MOUSEMOVE:
                if drawing == True:
                    image = org_image.copy()
                    prompt_on_image(prompt)
                    cv2.rectangle(image,(ix,iy),(x,y),(0,255,0),2)
        
            elif event == cv2.EVENT_LBUTTONUP:
                drawing = False
                fx,fy = x,y
                image = org_image.copy()
                prompt_on_image(prompt)
                cv2.rectangle(image,(ix,iy),(fx,fy),(0,255,0),2)

        # initialize the camera. Adjust vflip and hflip to reflect your camera's orientation
        camera = Picamera2()
        config = camera.create_still_configuration({"size": (IMAGEWIDTH, IMAGEHEIGHT),"format": "RGB888"},transform = Transform(hflip=True,vflip=True))
        camera.configure(config)

        ## 
        camera.start()

        #rawCapture = PiRGBArray(camera, size=camera.resolution)
        # allow the camera to warm up
        time.sleep(0.9)

        # create an image window and place it in the upper left corner of the screen
        cv2.namedWindow("Speed Camera")
        cv2.moveWindow("Speed Camera", 10, 40)

        # call the draw_rectangle routines when the mouse is used
        cv2.setMouseCallback('Speed Camera',draw_rectangle)
        
        # grab a reference image to use for drawing the monitored area's boundry
        image = camera.capture_array("main")
        org_image = image.copy()
        prompt_on_image("Define the monitored area - press 'c' to continue")
        
        # wait while the user draws the monitored area's boundry
        while not setup_complete:
            cv2.imshow("Speed Camera",image)
        
            #wait for for c to be pressed  
            key = cv2.waitKey(1) & 0xFF
        
            # if the `c` key is pressed, break from the loop
            if key == ord("c"):
                break
        
        # since the monitored area's bounding box could be drawn starting 
        # from any corner, normalize the coordinates
        
        if fx > ix:
            self.area.upper_left_x = ix
            self.area.lower_right_x = fx
        else:
            self.area.upper_left_x = fx
            self.area.lower_right_x = ix
        
        if fy > iy:
            self.area.upper_left_y = iy
            self.area.lower_right_y = fy
        else:
            self.area.upper_left_y = fy
            self.area.lower_right_y = iy
                    
        # cleanup the camera and close any open windows
        cv2.destroyAllWindows()
