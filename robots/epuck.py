from pypot.vrep.remoteApiBindings import vrep
from pypot.vrep.io import VrepIOErrors
from math import sqrt
from numpy import mean, array, argmax, argmin, ones
from random import sample
from time import sleep
from copy import copy
from threading import Event, Condition
from threading import Thread as ParralelClass
# from multiprocessing import Process as ParralelClass

class Epuck(object):
    def __init__(self, pypot_io, use_proximeters=range(8), suffix=""):
        # vrep.simxFinish(-1) # just in case, close all opened connections
        # self._clientID = vrep.simxStart('127.0.0.1',19997, True, True, 5000, 5) # Connect to V-REP
        self.suffix = suffix
        self.io = pypot_io
        self.used_proximeters = use_proximeters

        self._left_joint = self.io.get_object_handle('ePuck_leftJoint' + suffix)
        self._right_joint = self.io.get_object_handle('ePuck_rightJoint' + suffix)
        self._light_sensor = self.io.get_object_handle('ePuck_lightSensor' + suffix)
        self._camera = self.io.get_object_handle('ePuck_camera' + suffix)

        self._prox_handles = []
        self._all_prox_handles = []
        for i in range(8):
            p = self.io.get_object_handle('ePuck_proxSensor' + str(i + 1) + suffix)
            self._all_prox_handles .append(p)
            if i in use_proximeters:
                self._prox_handles.append(p)
            else:
                # hide proximeter ray
                self.hide_ray(i)

        # First calls with simx_opmode_streaming
        for h in self._prox_handles:
            self.io.call_remote_api("simxReadProximitySensor", h, streaming=True)

        self.camera_resolution, _ = self.io.call_remote_api("simxGetVisionSensorImage", self._camera, options=0, streaming=True)
        self.light_sensor_resolution, _ = self.io.call_remote_api("simxGetVisionSensorImage", self._light_sensor, options=0, streaming=True)

        self._body = self.io.get_object_handle("ePuck_bodyElements" + suffix)
        self.wheel_diameter = 4.25 * 10 ** -2
        self.base_lenght = 7 * 10 ** -2

        self._prox_aliases = {"all" : range(8),
                              "all-but-rear" : range(6),
                              "front" : [2, 3],
                              "rear" : [6, 7],
                              "front-left" : [0, 1, 2],
                              "front-right": [3, 4, 5]}

        self.no_detection_value = 2000.

        self._fwd_spd, self._rot_spd = 0., 0.
        self._left_spd, self._right_spd = 0., 0.

        self.fwd_spd, self.rot_spd = 0., 0.

        # vrep.simxGetFloatSignal(self._clientID, "CurrentTime", vrep.simx_opmode_streaming)

        self.freq = 100
        self._behaviors = {}
        self._runnings = {}
        self._to_detach = {}

        self._sensations = {}
        self._conditions = {}

        self._registered_objects = {}

        _, _ , _, _ = self.io.call_remote_api("simxGetObjectGroupData", vrep.sim_object_shape_type, 0, streaming=True)

        sleep(0.5)
        self.register_all_scene_objects()

        self.condition = Condition()

    def hide_ray(self, prox_id):
        self.io.call_remote_api("simxSetObjectIntParameter", self._all_prox_handles[prox_id], 4000, 1, sending=True)

    def display_ray(self, prox_id):
        self.io.call_remote_api("simxSetObjectIntParameter", self._all_prox_handles[prox_id], 4000, 0, sending=True)

    @property
    def left_spd(self):
        return self._left_spd

    @left_spd.setter
    def left_spd(self, value):
        self.io.call_remote_api("simxSetJointTargetVelocity", self._left_joint, value, sending=True)
        self._left_spd = copy(value)
        self._fwd_spd, self._rot_spd = self._lr_2_fwd_rot(self._left_spd, self._right_spd)
    
    @property
    def right_spd(self):
        return self._right_spd

    @right_spd.setter
    def right_spd(self, value):
        self.io.call_remote_api("simxSetJointTargetVelocity", self._right_joint, value, sending=True)
        self._right_spd = copy(value)
        self._fwd_spd, self._rot_spd = self._lr_2_fwd_rot(self._left_spd, self._right_spd)


    def left_vel(self, vel):
        "Deprecated, only for backward compatibility. Use self.left_spd = value instead"
        self.left_spd = vel
        
    def right_vel(self, vel):
        "Deprecated, only for backward compatibility. Use self.right_spd = value instead"
        self.right_spd = vel

    def _lr_2_fwd_rot(self, left_spd, right_spd):
        fwd = (self.wheel_diameter / 4.) * (left_spd + right_spd)
        rot = 0.5 * (self.wheel_diameter / self.base_lenght) * (right_spd - left_spd)
        return fwd, rot

    def _fwd_rot_2_lr(self, fwd, rot):
        left = ( (2.0 * fwd) - (rot * self.base_lenght) ) / (self.wheel_diameter)
        right = ( (2.0 * fwd) + (rot * self.base_lenght) ) / (self.wheel_diameter)
        return left, right

    @property
    def fwd_spd(self):
        return self._fwd_spd

    @fwd_spd.setter
    def fwd_spd(self, value):
        #with self.io.pause_communication():
        self.left_spd, self.right_spd = self._fwd_rot_2_lr(value, self._rot_spd)
        self._fwd_spd, self._rot_speed = self._lr_2_fwd_rot(self.left_spd, self.right_spd) 

    @property
    def rot_spd(self):
        return self._rot_spd

    @rot_spd.setter
    def rot_spd(self, value):
        # with self.io.pause_communication():
        self.left_spd, self.right_spd = self._fwd_rot_2_lr(self._fwd_spd, value)
        self._fwd_spd, self._rot_speed = self._lr_2_fwd_rot(self.left_spd, self.right_spd) 

    def move(self, forward, rotate=0.):
        #with self.io.pause_communication():
        self.fwd_spd, self.rot_spd = forward, rotate

    def stop(self):
        #with self.io.pause_communication():
        self.fwd_spd, self.rot_spd = 0., 0.

    def proximeters(self, tracked_objects=None, mode="no_object_id"):
        distances = []
        objects = []
        with self.io.pause_communication():
            for i in self.used_proximeters:
                detectionState, detectedPoint, detectedObjectHandle, detectedSurfaceNormalVector = self.io.call_remote_api("simxReadProximitySensor", self._all_prox_handles[i], buffer=True)
                # print detectedObjectHandle - 1
                if detectionState:
                    if (detectedObjectHandle - 1) in self._registered_objects:
                        obj_name = self._registered_objects[detectedObjectHandle - 1]
                        if tracked_objects is not None and not any([obj_name.startswith(o) for o in tracked_objects]):
                            objects.append("None")
                            distances.append(self.no_detection_value)
                            continue
                        objects.append(obj_name)
                    else:
                        objects.append("None")
                    distances.append(1000 * sqrt(sum([x ** 2 for x in detectedPoint])))
                else:
                    distances.append(self.no_detection_value)
                    objects.append("None")
        # if mode == "no_object_id":
        #     return array(distances)[self._prox_aliases[group]]
        # else:
        #     return array(distances)[self._prox_aliases[group]], array(objects)[self._prox_aliases[group]]
        return array(distances)

    def position(self):
        return self.io.get_object_position("ePuck" + self.suffix)

    def min_index(self, group="all"):
        proxs = self.no_detection_value * ones(len(use_proximeters))
        proxs[self._prox_aliases[group]] = self.proximeters(group)
        return argmin(proxs)

    def dir_prox(self, group="all"):
        proxs = self.no_detection_value * ones(len(use_proximeters))
        proxs[self._prox_aliases[group]] = self.proximeters(group)
        idx = argmin(proxs)
        return idx, proxs[idx]

    def min_distance(self, group='all'):
        proxs = self.proximeters(group=group)
        proxs = proxs[proxs != self.no_detection_value]
        if len(proxs):
            return min(proxs)
        else:
            return self.no_detection_value

    def is_min_distance(self, group, min_dist):
        proxs = self.proximeters(group=group)
        proxs = proxs[proxs != self.no_detection_value]
        if len(proxs):
            return any(proxs < min_dist)
        else:
            return False

    def camera_image(self):
        resolution, image = self.io.call_remote_api("simxGetVisionSensorImage", self._camera, options=0, buffer=True)
        image = array(image)
        image.resize(resolution[0], resolution[1], 3)
        return image

    def light_sensor_image(self):
        resolution, image = self.io.call_remote_api("simxGetVisionSensorImage", self._light_sensor, options=0, buffer=True)
        image = array(image)
        image.resize(resolution[0], resolution[1], 3)
        return image   

    def floor_sensor(self):
        tresh = 0.
        _, image = self.io.call_remote_api("simxGetVisionSensorImage", self._light_sensor, options=0, buffer=True)
        return image[0] > tresh, image[21] > tresh, image[93] > tresh

    def register_object(self, name):
        passed = False
        # need to wait that the object is actually reachable in VREP:
        while not passed:
            try:
                handle = self.io.get_object_handle(name)
                passed = True
            except VrepIOErrors:
                print "Not registered, retry ..."
        self._registered_objects[handle] = name

    def register_all_scene_objects(self):
        handles, _, _, names = self.io.call_remote_api("simxGetObjectGroupData", vrep.sim_object_shape_type, 0, streaming=True)
        for h, n in zip(handles, names):
            self._registered_objects[h] = n

    def min_distance_to_object(self, name, group="all"):
        dists = self.no_detection_value * ones(len(use_proximeters))
        objs = array(["None"] * 8, dtype='|S400')
        dists[self._prox_aliases[group]], objs[self._prox_aliases[group]] = self.proximeters(group=group, mode="obj")
        min_dist = 1e10
        for i, d, o in sample(zip(range(len(use_proximeters)), dists, objs), len(use_proximeters)):
            if o.startswith(name) and d < min_dist:
                min_dist = copy(d)
        if min_dist < 1e10:
            return min_dist
        else:
            return self.no_detection_value

    def detect_object(self, name, dist=2000, group="all"):
        dists = self.no_detection_value * ones(len(use_proximeters))
        objs = array(["None"] * 8, dtype='|S400')
        dists[self._prox_aliases[group]], objs[self._prox_aliases[group]] = self.proximeters(group=group, mode="obj")
        for i, d, o in sample(zip(range(len(use_proximeters)), dists, objs), len(use_proximeters)):
            if o.startswith(name) and d < dist:
                return True
        return False

    def wait(self, seconds):
        start = self.io.get_simulation_current_time()
        while self.io.get_simulation_current_time() - start < seconds:
            sleep(0.005)

    def attach_behavior(self, callback, freq=None):
        self._behaviors[callback.__name__] = Behavior(self, callback, self.condition, freq)
        self._behaviors[callback.__name__].start()
        # return self._behaviors[callback.__name__]

    def detach_behavior(self, callback_name):
        if callback_name not in self._behaviors:
            print("Warning: " + callback_name + " was not attached")
        else:
            self._behaviors[callback_name].stop()  # just in case
            del self._behaviors[callback_name]

    def detach_all_behaviors(self):
        beh_copy = dict(self._behaviors)  # because one can't modify the dict during the loop on itself
        for name, behavior in beh_copy.iteritems():
            self.detach_behavior(name)
            print "Behavior " + name + " detach"

    def start_behavior(self, callback_name):
        if not callback_name in self._behaviors:
            print("Warning: " + callback_name + " is not attached")
        else:
            self._behaviors[callback_name].execute()

    def start_all_behaviors(self):
        for name, behavior in self._behaviors.iteritems():
            self.start_behavior(name)
            print "Behavior " + name + " started"

    def stop_behavior(self, callback_name):
        if not callback_name in self._behaviors:
            print("Warning: " + callback_name + " is not attached")
        else:
            self._behaviors[callback_name].stop()

    def stop_all_behaviors(self):
        for b_name in self._behaviors:
            self.stop_behavior(b_name)



    def attach_sensation(self, callback, freq=None):
        self._sensations[callback.__name__] = Sensation(self, callback, Condition(), freq)
        self._sensations[callback.__name__].start()


class Sensation(ParralelClass):

    def __init__(self, robot, callback, condition, freq=None):
        ParralelClass.__init__(self)
        if freq is None:
            self.period = 1. / robot.freq
        else:
            self.period = 1. / freq        
        self.robot = robot
        self.callback = callback
        self.condition = condition
      
    
    def run(self):
        while True:
            self.condition.acquire()
            if self.callback(self.robot):
                self.condition.notify_all()
            self.condition.release()
            self.robot.wait(self.period)


class Behavior(ParralelClass):

    def __init__(self, robot, callback, condition, freq):
        ParralelClass.__init__(self)
        self.period = 1. / freq
        self.robot = robot
        self.callback = callback
        self.condition = condition
        self._running = Event()
        self._running.clear()

    def run(self):
        while True:
            start_time = self.robot.io.get_simulation_current_time()
            if self._running.is_set():
                self.condition.acquire()
                self.callback(self.robot)
                self.condition.release()
            self.robot.wait(self.period + start_time - self.robot.io.get_simulation_current_time())

    def execute(self):
        self._running.set()

    def stop(self):
        self._running.clear()
