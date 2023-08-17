from CarSpeedConfig import MonitorArea
from CarSpeedMonitor import CarSpeedCamera
from picamera2 import Picamera2
from libcamera import Transform
import cv2
import time
import math
import datetime


class ConfigureMonitorArea(object):
    def __init__(self, h_flip, v_flip):
        self.area = MonitorArea()
        self.h_flip = h_flip
        self.v_flip = v_flip

    def start(self):
        ix,iy,fx,fy = 0,0,0,0
        drawing = False
        prompt = ""
        setup_complete = False
        image: None
        org_image: None

        def update_prompt(image):
            txt = f"Press 'q' to quit, 'e' to exit and save configution, 'r' to refresh image"
            cv2.putText(image, txt, (10, 15),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            txt = f"Press 'h' to flip horizontal, 'v' to flip vertical"
            cv2.putText(image, txt, (10, 35),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            txt = f"h_flip=[{self.h_flip}], v_flip=[{self.v_flip}]"
            cv2.putText(image, txt, (10, 55),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        def refresh_image():
            nonlocal image,org_image
            image = camera.picam.capture_array("main")
            update_prompt(image)
            org_image = image.copy()
        
        # mouse callback function for drawing capture area
        def draw_rectangle(event,x,y,flags,param):
            nonlocal ix,iy,fx,fy,drawing,image,prompt
            if event == cv2.EVENT_LBUTTONDOWN:
                drawing = True
                ix,iy = x,y
        
            elif event == cv2.EVENT_MOUSEMOVE:
                if drawing == True:
                    image = org_image.copy()
                    cv2.rectangle(image,(ix,iy),(x,y),(0,255,0),2)
        
            elif event == cv2.EVENT_LBUTTONUP:
                drawing = False
                fx,fy = x,y
                image = org_image.copy()
                cv2.rectangle(image,(ix,iy),(fx,fy),(0,255,0),2)    
        
        def toggle_h_flip():
            nonlocal camera
            self.h_flip = not self.h_flip
            camera.update_h_flip(self.h_flip)
            refresh_image()

        def toggle_v_flip():
            nonlocal camera
            self.v_flip = not self.v_flip
            camera.update_v_flip(self.v_flip)
            refresh_image()

        camera = CarSpeedCamera(self.h_flip, self.v_flip)
        camera.start()

        # allow the camera to warm up
        time.sleep(0.9)

        # create an image window and place it in the upper left corner of the screen
        cv2.namedWindow("Speed Camera")
        cv2.moveWindow("Speed Camera", 10, 40)

        # call the draw_rectangle routines when the mouse is used
        cv2.setMouseCallback('Speed Camera',draw_rectangle)
        
        # grab a reference image to use for drawing the monitored area's boundry
        refresh_image()
        
        save = False
        # wait while the user draws the monitored area's boundry
        while not setup_complete:
            cv2.imshow("Speed Camera",image)
        
            #wait for for c to be pressed  
            key = cv2.waitKey(1) & 0xFF
        
            # horizontal flip
            if key == ord("h"):
                toggle_h_flip()

            # vertical flip
            if key == ord("v"):
                toggle_v_flip()

            # quit
            if key == ord("r"):
                refresh_image()

            # quit
            if key == ord("q"):
                save = False
                break
        
            # exit and save
            if key == ord("e"):
                save = True
                break
        # since the monitored area's bounding box could be drawn starting 
        # from any corner, normalize the coordinates
        if save:
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

        return save