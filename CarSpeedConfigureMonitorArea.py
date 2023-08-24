from CarSpeedConfig import MonitorArea
from CarSpeedMonitor import CarSpeedCamera
from picamera2 import Picamera2
from libcamera import Transform
import cv2
import time
import math
import datetime
import numpy as np
from pynput import keyboard


class ConfigureMonitorArea(object):
    WINDOW_NAME="Car Speed Monitor Configuration"
    def __init__(self, h_flip: bool, v_flip: bool):
        self.area = MonitorArea()
        self.h_flip = h_flip
        self.v_flip = v_flip

    def start(self):
        ix,iy,fx,fy = 0,0,0,0
        drawing = False
        prompt = ""
        image: np.ndarray

        def annotate_image(image):
            line_height=17
            line_pos=line_height
            bottom_line=camera.image_height-line_height
            txt = f"Use mouse buttons to define monitor area"
            cv2.putText(image, txt, (10, line_pos),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            line_pos+=line_height
            txt = f"Press 'q' to quit, 'e' to exit and save configution"
            cv2.putText(image, txt, (10, line_pos),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            line_pos+=line_height
            txt = f"Press 'h' to flip horizontal, 'v' to flip vertical"
            cv2.putText(image, txt, (10, line_pos),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            line_pos+=line_height
            txt = f"h_flip=[{self.h_flip}], v_flip=[{self.v_flip}]"
            cv2.putText(image, txt, (10, bottom_line),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            txt = f"area=[{ix:3d},{iy:3d},{fx:3d},{fy:3d}]"
            (txt_size,baseline)=cv2.getTextSize(txt,cv2.FONT_HERSHEY_SIMPLEX,0.5,1)            
            (txt_width,txt_height)=txt_size
            cv2.putText(image, txt, (camera.image_width-txt_width-10, bottom_line),cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        def refresh_image():
            nonlocal image
            image = camera.picam.capture_array("main")
            annotate_image(image)
            cv2.rectangle(image,(ix,iy),(fx,fy),(0,255,0),2)    
        
        # mouse callback function for drawing capture area
        def draw_rectangle(event,x:int,y:int,flags,param):
            nonlocal ix,iy,fx,fy,drawing,image,prompt
            if event == cv2.EVENT_LBUTTONDOWN:
                drawing = True
                ix,iy = x,y
                fx,fy = ix,iy
        
            elif event == cv2.EVENT_MOUSEMOVE:
                if drawing == True:
                    fx, fy = x, y
        
            elif event == cv2.EVENT_LBUTTONUP:
                drawing = False
                fx,fy = x,y
        
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
        
        def on_key_press(key):
            process_key(key.char)

        def process_key(key):
            nonlocal save, cont
            if key == 'h':
                toggle_h_flip()
            if key == 'v':
                toggle_v_flip()
            if key == 'e':
                if ix==0 and iy==0 and fy==0 and fx==0:
                    print("Please enter a detection area using the mouse")
                else:
                    save=True
                    cont = False
            if key == 'q':
                save=False
                cont = False


        camera = CarSpeedCamera(self.h_flip, self.v_flip)
        camera.start()

        # allow the camera to warm up
        time.sleep(0.9)

        # create an image window and place it in the upper left corner of the screen
        cv2.namedWindow(ConfigureMonitorArea.WINDOW_NAME)
        cv2.moveWindow(ConfigureMonitorArea.WINDOW_NAME, 10, 40)

        # call the draw_rectangle routines when the mouse is used
        cv2.setMouseCallback(ConfigureMonitorArea.WINDOW_NAME,draw_rectangle)

        listener = keyboard.Listener(
            on_press=on_key_press)
        listener.start()

        
        # grab a reference image to use for drawing the monitored area's boundry
        refresh_image()
        
        save = False
        cont = True
        # wait while the user draws the monitored area's boundry
        while cont:

            refresh_image()
            cv2.imshow(ConfigureMonitorArea.WINDOW_NAME,image)
        
            #wait for for c to be pressed  
            key = cv2.waitKey(1) & 0xFF
        
            #process_key(str(key))

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
            print("Exiting ...")
        else:
            print("Quitting ...")
                    
        # cleanup the camera and close any open windows
        cv2.destroyAllWindows()

        return save