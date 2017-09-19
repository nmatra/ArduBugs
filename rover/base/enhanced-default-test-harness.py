#!/usr/bin/env python
import sys
import os
import pexpect
import time
import shutil

from pymavlink import mavutil, mavwp

# import autotest modules
testdir = os.path.abspath("source/Tools/autotest")
sys.path.append(testdir)

from common import *
from pysim import util, vehicleinfo

HOME = mavutil.location(40.071374969556928, -105.22978898137808, 1583.702759, 246)
homeloc = None

def wait_ready_to_arm(mavproxy):
    # wait for EKF and GPS checks to pass
    mavproxy.expect('IMU0 is using GPS')


def arm_rover(mavproxy, mav):
    wait_ready_to_arm(mavproxy);

    mavproxy.send('arm throttle\n')
    mavproxy.expect('ARMED')

    print("ROVER ARMED")
    return True


def drive_left_circuit(mavproxy, mav):
    """Drive a left circuit, 50m on a side."""
    mavproxy.send('switch 6\n')
    wait_mode(mav, 'MANUAL')
    mavproxy.send('rc 3 2000\n')

    print("Driving left circuit")
    # do 4 turns
    for i in range(0, 4):
        # hard left
        print("Starting turn %u" % i)
        mavproxy.send('rc 1 1000\n')
        if not wait_heading(mav, 270 - (90*i), accuracy=10):
            return False
        mavproxy.send('rc 1 1500\n')
        print("Starting leg %u" % i)
        if not wait_distance(mav, 50, accuracy=7):
            return False
    mavproxy.send('rc 3 1500\n')
    print("Circuit complete")
    return True


def drive_RTL(mavproxy, mav):
    """Drive to home."""
    print("Driving home in RTL")
    mavproxy.send('switch 3\n')
    if not wait_location(mav, homeloc, accuracy=22, timeout=90):
        return False
    print("RTL Complete")
    return True


def setup_rc(mavproxy):
    """Setup RC override control."""
    for chan in [1, 2, 3, 4, 5, 6, 7]:
        mavproxy.send('rc %u 1500\n' % chan)
    mavproxy.send('rc 8 1800\n')


def drive_mission(mavproxy, mav, filename):
    """Drive a mission from a file."""
    global homeloc
    print("Driving mission %s" % filename)
    mavproxy.send('wp load %s\n' % filename)
    mavproxy.expect('Flight plan received')
    mavproxy.send('wp list\n')
    mavproxy.expect('Requesting [0-9]+ waypoints')
    mavproxy.send('switch 4\n')  # auto mode
    mavproxy.send('rc 3 1500\n')
    wait_mode(mav, 'AUTO')
    if not wait_waypoint(mav, 1, 4, max_dist=5):
        return False
    wait_mode(mav, 'HOLD')
    print("Mission OK")
    return True


def test_arm(mavproxy, mav):
    return arm_rover(mavproxy, mav)


def test_mission_rover1(mavproxy, mav):
    return  arm_rover(mavproxy, mav) and \
            drive_mission(mavproxy, mav, os.path.join(testdir, "rover1.txt"))


def test_left_circuit(mavproxy, mav):
     return arm_rover(mavproxy, mav) and \
            drive_left_circuit(mavproxy, mav) and \
            drive_RTL(mavproxy, mav)


def test(mission):
    global homeloc

    missions = {
        'arm':
            lambda mavproxy, mav: test_arm(mavproxy, mav),
        'mission_rover1':
            lambda mavproxy, mav: test_mission_rover1(mavproxy, mav),
        'left_circuit':
            lambda mavproxy, mav: test_left_circuit(mavproxy, mav)
    }
    mission = missions[mission]

    binary = '/experiment/source/build/sitl/bin/ardurover'
    options = '--sitl=127.0.0.1:5501 --out=127.0.0.1:19550 --streamrate=10'
    home = "%f,%f,%u,%u" % (HOME.lat, HOME.lng, HOME.alt, HOME.heading)
    sitl = util.start_SITL(binary, wipe=True, model='rover', home=home, speedup=10)
    mavproxy = util.start_MAVProxy_SITL('APMrover2', options=options)

    print("WAITING FOR PARAMETERS")
    mavproxy.expect('Received [0-9]+ parameters')

    # setup test parameters
    mavproxy.send("param load %s/default_params/rover.parm\n" % testdir)
    mavproxy.expect('Loaded [0-9]+ parameters')
    mavproxy.send("param set LOG_REPLAY 1\n")
    mavproxy.send("param set LOG_DISARMED 1\n")
    time.sleep(2)

    # restart with new parms
    util.pexpect_close(mavproxy)
    util.pexpect_close(sitl)

    sitl = util.start_SITL(binary, model='rover', home=home, speedup=10, gdb=False)
    mavproxy = util.start_MAVProxy_SITL('APMrover2', options=options)
    mavproxy.expect('Telemetry log: (\S+)')
    logfile = mavproxy.match.group(1)
    print("LOGFILE %s" % logfile)

    mavproxy.expect('Received [0-9]+ parameters')

    util.expect_setup_callback(mavproxy, expect_callback)

    expect_list_clear()
    expect_list_extend([sitl, mavproxy])

    # get a mavlink connection going
    try:
        mav = mavutil.mavlink_connection('127.0.0.1:19550', robust_parsing=True)
    except Exception as msg:
        print("Failed to start mavlink connection on 127.0.0.1:19550" % msg)
        raise
    mav.message_hooks.append(message_hook)
    mav.idle_hooks.append(idle_hook)

    try:
        print("Waiting for a heartbeat with mavlink protocol %s" % mav.WIRE_PROTOCOL_VERSION)
        mav.wait_heartbeat()

        print("Setting up RC parameters")
        setup_rc(mavproxy)

        print("Waiting for GPS fix")
        mav.wait_gps_fix()
        homeloc = mav.location()
        print("Home location: %s" % homeloc)

        # Perform mission
        return mission(mavproxy, mav)

    # enforce a time limit
    except pexpect.TIMEOUT:
        print("Failed: time out")
        return False

    finally:
        mav.close()
        util.pexpect_close(mavproxy)
        util.pexpect_close(sitl)


if __name__ == "__main__":
    test(sys.argv[1])
