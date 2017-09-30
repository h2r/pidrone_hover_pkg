#!/usr/bin/env python
from __future__ import division
import rospy 
from pidrone_pkg.msg import RC, ERR, axes_err
from geometry_msgs.msg import Pose, PoseStamped
import time
import tf
import math
import numpy as np
from copy import deepcopy
import sys


#####################################################
#						PID							#
#####################################################
class PIDaxis():
    def __init__(self, kp, ki, kd, kp_upper = None, kpi = None, kpi_max = None, i_range = None, d_range = None, control_range = (1000,2000), midpoint = 1500, smoothing = True):
        # tuning
        self.kp = kp
        self.ki = ki
        self.kd = kd
        # config
        self.kp_upper = kp_upper
        self.i_range = i_range
        self.d_range = d_range
        self.control_range = control_range
        self.midpoint = midpoint
        self.smoothing = True
        # internal
        self._old_err = None
        self._p = 0
        self._i = 0
        self._d = 0
        self._dd = 0
        self._ddd = 0
        
        # XXX TODO implement
        self.kpi = kpi
        self.kpi_max = kpi_max
        if self.kpi_max is None:
            self.kpi_max = 0.1


    def step(self, err, time_elapsed, error = None, cmd_velocity=0, cmd_yaw_velocity=0):

        if self._old_err is None: self._old_err = err # first time around prevent d term spike	
        # find the p,i,d components
        if self.kp_upper is not None and err < 0:
            self._p = err * self.kp_upper
        else: 
            self._p = err * self.kp


        if self.kpi is not None:
            kpi_term = np.sign(err) * err * err * self.kpi * time_elapsed
            if abs(kpi_term) < self.kpi_max:
                self._i += kpi_term
            else:
                self._i += self.kpi_max * np.sign(err)

        self._i += err * self.ki * time_elapsed
        if self.i_range is not None:
            self._i = max(self.i_range[0], min(self._i, self.i_range[1]))

        self._d = (err - self._old_err) * self.kd / time_elapsed
        if self.d_range is not None:
            self._d = max(self.d_range[0], min(self._d, self.d_range[1]))
        self._old_err = err
 
        # smooth over the last three d terms
        if self.smoothing:
            self._d = (self._d * 8.0 + self._dd * 5.0 + self._ddd * 2.0)/15.0
            self._ddd = self._dd
            self._dd = self._d

        if error is not None:
            error.p = self._p
            error.i = self._i
            error.d = self._d

        #print 1
        #raw_output = self._p + self._i + self.ki * cmd_velocity + self._d
        raw_output = self._p + self._i + self._d
        output = min(max(raw_output + self.midpoint, self.control_range[0]),
                self.control_range[1])

        return output

height_factor = 1.238
battery_factor = 0.75

class PID:
    def __init__(self, 
#               P   I   D
#       roll = PIDaxis(8.0, 0.0, 0.4, control_range=(1400, 1600)),
#       pitch = PIDaxis(8.0, 0.0, 0.4, control_range=(1400,
#       1600)),
#       yaw = PIDaxis(0.0, 0.0, 0.0),
#       throttle = PIDaxis(2.0, 2.0, 2.0, kp_upper = 0, i_range=(0, 400),\
#           control_range=(1200,2000), d_range=(-400, 400), midpoint =
#           1300), smoothing=False):
        #roll = PIDaxis(4., 2., 0.3, control_range=(1400, 1600)),
        #pitch = PIDaxis(4., 2., 0.3, control_range=(1400,

        roll = PIDaxis(4., 4.0, 0.0, kpi = 0.00, kpi_max =
        0.5,control_range=(1400, 1600), midpoint = 1500), # D term 0.1 or 0.01
        pitch = PIDaxis(4., 4.0, 0.0, kpi = 0.00, kpi_max = 0.5,control_range=(1400,
        1600), midpoint = 1500),

        roll_low = PIDaxis(4., 0.2, 0.0, kpi = 0.00, kpi_max =
        0.5,control_range=(1400, 1600), midpoint = 1500), # D term 0.1 or 0.01
        pitch_low = PIDaxis(4., 0.2, 0.0, kpi = 0.00, kpi_max = 0.5,control_range=(1400,
        1600), midpoint = 1500),

#       roll = PIDaxis(2., 2., 0.15, control_range=(1400, 1600)),
#       pitch = PIDaxis(2., 2., 0.15, control_range=(1400,
#       1600)),
        yaw = PIDaxis(0.0, 0.0, 0.0),
        # jgo XXX throttle = PIDaxis(1.2, 2., 2.0, kp_upper = 0, i_range=(0, 400),\
        #throttle = PIDaxis(1.0, 0.75, 3.0, kp_upper = 0, i_range=(0, 400),\
        #throttle = PIDaxis(2.0, 0.75, 6.0, i_range=(0, 400),\
        #gthrottle = PIDaxis(0.50, 0.75, 3.0, kp_upper = 4.0, i_range=(0, 400),\
        #throttle = PIDaxis(3.0, 0.2, 3.0, kp_upper = 8.0, i_range=(0, 400),\
        #throttle = PIDaxis(1.0, 0.3, 3.0, kp_upper = 1, i_range=(0, 400),\

        #throttle = PIDaxis(1.0, 0.05, 2.0, kp_upper = 0.0, kpi = 0.01, kpi_max
        #= 100000000000.0, i_range=(0, 400),\
        ##= 0.04, i_range=(0, 400),\
            #control_range=(1200,2000), d_range=(-40, 40), midpoint =
            #1400), smoothing=False):
            ##1250), smoothing=False):

        throttle = PIDaxis(1.0/height_factor * battery_factor, 0.5/height_factor * battery_factor, 2.0/height_factor * battery_factor, kp_upper = 1.0/height_factor * battery_factor, kpi = 0.00, kpi_max
        = 0.0, i_range=(-400, 400),
        control_range=(1200,2000), d_range=(-40, 40), midpoint =
        1250),
        # kV 2300 motors
        #1300),
        # kV 2550 motors
        #1250),

        throttle_low = PIDaxis(1.0/height_factor * battery_factor, 0.05/height_factor * battery_factor, 2.0/height_factor * battery_factor, kp_upper = 1.0/height_factor * battery_factor, kpi = 0.00, kpi_max
        = 0.0, i_range=(0, 400),
        control_range=(1200,2000), d_range=(-40, 40), midpoint =
        1250), 
        # kV 2300 motors
        #1300), 
        # kV 2550 motors
        #1250),
        
        smoothing=False):
        # roll = PIDaxis(1.2, 05, 1.2),
        # pitch = PIDaxis(1.2, 0.5, 1.2),
        # yaw = PIDaxis(-1000.0, 0,0),
        # throttle = PIDaxis(7.5, 4.0, 2.0, kp_upper = 0, i_range=(0, 400),\
        #     control_range=(1150,2000), d_range=(-400, 400), midpoint =
        #     1200), smoothing=False):
        self.trim_controller_cap_plane = 5.0
        self.trim_controller_thresh_plane = 0.01 #5.0
        self.roll = roll
        self.pitch = pitch
        self.roll_low = roll_low
        self.pitch_low = pitch_low
        self.yaw = yaw
        self.trim_controller_cap_throttle = 5.0
        self.trim_controller_thresh_throttle = 5.0 #5.0
        self.throttle = throttle
        self.throttle_low = throttle_low
        self.sp = None
        self._t = None
        # steve005 presets
        self.roll_low._i = -10.0
        self.pitch_low._i = 0.0
        #self.throttle_low._i = 220.0
        # safer presets
        #self.roll_low._i = 0.0
        #self.pitch_low._i = 0.0
        self.throttle_low.init_i = 100
        self.throttle.init_i = 0.0
        self.reset()

        self.throttle.mw_angle_alt_scale = 1.0


    def reset(self):
        self._t = None
        self.throttle_low._i = self.throttle_low.init_i
        self.throttle._i = self.throttle.init_i        

    def get_is(self):
        return [self.roll._i, self.pitch._i, self.yaw._i, self.throttle._i]
    
    def set_is(self, i):
        self.roll._i = i[0]
        self.pitch._i = i[1]
        self.yaw._i = i[2]
        self.throttle._i = i[3]

    def update_setpoint(self, data):
        self.sp = data

    def step(self, error, cmd_velocity, cmd_yaw_velocity=0):
        if self._t is None: time_elapsed = 1 # first time around prevent time spike
        else: time_elapsed = rospy.get_time() - self._t
        self._t = rospy.get_time()
        #print cmd_velocity

        # single mode step
        #cmd_r = self.roll.step(error.x.err, time_elapsed, error.x, cmd_velocity=cmd_velocity[1])
        #cmd_p = self.pitch.step(error.y.err, time_elapsed, error.y, cmd_velocity=cmd_velocity[0])
        #trim mode step
        cmd_r = 0
        cmd_p = 0
        cmd_p = 0
        if abs(error.x.err) < self.trim_controller_thresh_plane:
            cmd_r = self.roll_low.step(error.x.err, time_elapsed, error.x, cmd_velocity=cmd_velocity[1])
            self.roll._i = 0
        else:
            #self.roll_low.step(error.x.err, time_elapsed, error.x, cmd_velocity=cmd_velocity[1])
            if error.x.err > self.trim_controller_cap_plane:
                self.roll_low.step(self.trim_controller_cap_plane, time_elapsed, error.x, cmd_velocity=cmd_velocity[1])
            elif error.x.err < -self.trim_controller_cap_plane:
                self.roll_low.step(-self.trim_controller_cap_plane, time_elapsed, error.x, cmd_velocity=cmd_velocity[1])
            else:
                self.roll_low.step(error.x.err, time_elapsed, error.x, cmd_velocity=cmd_velocity[1])

            cmd_r = self.roll_low._i + self.roll.step(error.x.err, time_elapsed, error.x, cmd_velocity=cmd_velocity[1])

        if abs(error.y.err) < self.trim_controller_thresh_plane:
            cmd_p = self.pitch_low.step(error.y.err, time_elapsed, error.y, cmd_velocity=cmd_velocity[0])
            self.pitch._i = 0
        else:
            #cmd_p = self.pitch_low.step(error.y.err, time_elapsed, error.y, cmd_velocity=cmd_velocity[0])
            if error.y.err > self.trim_controller_cap_plane:
                self.pitch_low.step(self.trim_controller_cap_plane, time_elapsed, error.y, cmd_velocity=cmd_velocity[0])
            elif error.y.err < -self.trim_controller_cap_plane:
                self.pitch_low.step(-self.trim_controller_cap_plane, time_elapsed, error.y, cmd_velocity=cmd_velocity[0])
            else:
                self.pitch_low.step(error.y.err, time_elapsed, error.y, cmd_velocity=cmd_velocity[0])

            cmd_p = self.pitch_low._i + self.pitch.step(error.y.err, time_elapsed, error.y, cmd_velocity=cmd_velocity[0])


        #print self.roll._i, self.pitch._i
        #print "Roll  low, hi:", self.roll_low._i, self.roll._i
        #print "Pitch low, hi:", self.pitch_low._i, self.pitch._i
        #print "Throttle low, hi:", self.throttle_low._i, self.throttle._i

        cmd_y = 1500 + cmd_yaw_velocity
        #print cmd_y, cmd_yaw_velocity, "HELLO"

        #cmd_t = self.throttle.step(error.z.err, time_elapsed, error.z)

        #print "zerr: ", abs(error.z.err), self.trim_controller_thresh_throttle
        if abs(error.z.err) < self.trim_controller_thresh_throttle:
            cmd_t = self.throttle_low.step(error.z.err, time_elapsed, error.z)
            self.throttle_low._i += self.throttle._i
            self.throttle._i = 0
        else:
            if error.z.err > self.trim_controller_cap_throttle:
                self.throttle_low.step(self.trim_controller_cap_throttle, time_elapsed, error.z)
            elif error.z.err < -self.trim_controller_cap_throttle:
                self.throttle_low.step(-self.trim_controller_cap_throttle, time_elapsed, error.z)
            else:
                self.throttle_low.step(error.z.err, time_elapsed, error.z)

            cmd_t = self.throttle_low._i + self.throttle.step(error.z.err, time_elapsed, error.z)
            # jgo: this seems to mostly make a difference before the I term has
            # built enough to be stable, but it really seems better with it. To
            # see the real difference, compare cmd_t / mw_angle_alt_scale to
            # cmd_t * mw_angle_alt_scale and see how it sinks. That happens to
            # a less noticeable degree with no modification.
            cmd_t = cmd_t / max(0.5, self.throttle.mw_angle_alt_scale)
            #print "mw factor: ", self.throttle.mw_angle_alt_scale

        return [cmd_r, cmd_p, cmd_y, cmd_t]

    # def step(self, pos, error):
    #     if self._t is None: time_elapsed = 1 # first time around prevent time spike
    #     else: time_elapsed = time.time() - self._t
    #     self._t = time.time()
    #     if self.sp is None:
    #         return [1500, 1500, 1500, 1000]
    #     else:
    #         cmd_r = self.roll.step(error[0], time_elapsed, error.x)
    #         cmd_p = self.pitch.step(error[1], time_elapsed, error.y)
    #         # cmd_y = self.yaw.step(err[2], time_elapsed, None)
    #         cmd_y = 0
    #         cmd_t = self.throttle.step(error[3], time_elapsed, error.z)
    #         # err = self.calc_err(pos)
    #         # error.x.err = err[0]
    #         # error.y.err = err[1]
    #         # error.z.err = err[3]
    #         # cmd_r = self.roll.step(err[0], time_elapsed, error.x)
    #         # cmd_p = self.pitch.step(err[1], time_elapsed, error.y)
    #         # cmd_y = self.yaw.step(err[2], time_elapsed, None)
    #         # cmd_t = self.throttle.step(err[3], time_elapsed, error.z)

    #         return [cmd_r, cmd_p, cmd_y, cmd_t]
    
    def get_roll_matrix(self, data):
        y = data['heading']/180.0*np.pi
        r = data['angx']/180.0*np.pi
        p = data['angy']/180.0*np.pi
        q = np.array(tf.transformations.quaternion_from_euler(-p, r, -y))
        return Quaternion(q).rotation_matrix


    def quat_to_rpy(self, q):
        """ takes in a quaternion (like from a pose message) and returns (roll, pitch, yaw) """
        return tf.transformations.euler_from_quaternion([q.x, q.y, q.z, q.w])

    def calc_err(self, pos):
        """ given a position and a set point (in global coordinates), this calculates the error
        in the drone's coordinate system (r,p,y,t) """
        _, _, pos_yaw = self.quat_to_rpy(pos.pose.orientation)
        _, _, sp_yaw  = self.quat_to_rpy(self.sp.pose.orientation)
        
        err_x = self.sp.pose.position.x - pos.pose.position.x
        err_y = self.sp.pose.position.y - pos.pose.position.y
        err_z = self.sp.pose.position.z - pos.pose.position.z
        err_yaw = sp_yaw - pos_yaw
        sp_angle = -np.arctan2(err_x, err_y) # the angle of the drone's pos relative to the setpoint
        sp_norm = np.sqrt(err_x**2 + err_y**2) # the distance from the drone to the setpoint (in the plane) 
        diff_angle = pos_yaw - sp_angle # the difference between the drone's yaw and its sp_angle

        err_fb = np.cos(diff_angle) * sp_norm
        err_lr = np.sin(diff_angle) * sp_norm
        return (err_lr, err_fb, err_yaw, err_z)

