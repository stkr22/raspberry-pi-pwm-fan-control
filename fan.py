#!/usr/bin/python

import sys, getopt
import logging
import time
import lgpio
import psutil


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Configuration
PWM_GPIO_NR = 18        # PWM gpio number used to drive PWM fan (gpio18 = pin 12)
WAIT_TIME = -1       # script mode - for interval mode values > 0 are treated as seconds
PWM_FREQ = 50        # [Hz] 10kHz for Noctua PWM control

# Configurable temperature and fan speed
MIN_TEMP = 40
MAX_TEMP = 60
FAN_LOW = 20
FAN_HIGH = 100
FAN_OFF = 0
FAN_MAX = 100

# logging and metrics (enable = 1)
VERBOSE = 1
NODE_EXPORTER = 0

# parse input arguments
try:
   opts, args = getopt.getopt(sys.argv[1:],"hv",["min-temp=","max-temp=","fan-low=","fan-high=","wait-time=","help","pwm-gpio=","pwm-freq=","verbose","node-exporter"])
except getopt.GetoptError:
   print('fan.py [--min-temp=40] [--max-temp=70] [--fan-low=20] [--fan-high=100] [--wait-time=1] [--pwm-gpio=18] [--pwm-freq=10000] [--node-exporter] [-v|--verbose] [-h|--help]')
   sys.exit(2)
for opt, arg in opts:
   if opt in ("-h", "--help"):
      print('fan.py [--min-temp=40] [--max-temp=70] [--fan-low=20] [--fan-high=100] [--wait-time=1] [--pwm-gpio=18] [--pwm-freq=10000] [--node-exporter] [-v|--verbose] [-h|--help]')
      sys.exit()
   elif opt in ("-v", "--verbose"):
      VERBOSE = 1
   elif opt in ("--min-temp"):
      MIN_TEMP = int(arg)
   elif opt in ("--max-temp"):
      MAX_TEMP = int(arg)
   elif opt in ("--fan-low"):
      FAN_LOW = int(arg)
   elif opt in ("--fan-high"):
      FAN_HIGH = int(arg)
   elif opt in ("--wait-time"):
      WAIT_TIME = int(arg)
   elif opt in ("--pwm-gpio"):
      PWM_GPIO_NR = int(arg)
   elif opt in ("--pwm-freq"):
      PWM_FREQ = int(arg)
   elif opt in ("--node-exporter"):
      NODE_EXPORTER = 1

logger.info("Starting service with min_temp %s to max_temp %s. Set fan_low %s to fan_high %s. Waiting %s. Using GPIO_PIN %s with frequency %s", MIN_TEMP, MAX_TEMP, FAN_LOW, FAN_HIGH, WAIT_TIME, PWM_GPIO_NR, PWM_FREQ)


def get_cpu_temperature() -> int:
   """Get CPU temparature.

   Returns:
       int: _description_
   """
   sensors = psutil.sensors_temperatures()['cpu_thermal']
   return round(sensors[0].current)

def prometheus_exporter(speed: int, temp: int) -> None:
   # Save a reference to the original standard output
   original_stdout = sys.stdout 
   with open('/var/lib/node_exporter/fan-metrics.prom', 'w') as f:
      # Change the standard output to the file we created.
      sys.stdout = f 
      print('raspberry_fan_speed ',speed)
      print('raspberry_fan_temp ',temp)
      print('raspberry_fan_min_temp ',MIN_TEMP)
      print('raspberry_fan_max_temp ',MAX_TEMP)
      print('raspberry_fan_fan_low ',FAN_LOW)
      print('raspberry_fan_fan_high ',FAN_HIGH)
      print('raspberry_fan_wait_time ',WAIT_TIME)
      print('raspberry_fan_pwm_gpio ',PWM_GPIO_NR)
      print('raspberry_fan_freq ',PWM_FREQ)
      # Reset the standard output to its original value
      sys.stdout = original_stdout
      f.close()

def set_fan_speed(speed: int, temp: int) -> None:
   """Setting gpio fan speed.

   Args:
       speed (int): _description_
       temp (int): _description_
   """
   lgpio.tx_pwm(
      fan,
      PWM_GPIO_NR,
      PWM_FREQ,
      speed,
      pulse_offset=0,
      pulse_cycles=0
   )

   # print fan speed and temperature
   if VERBOSE == 1:
      logger.info("fan speed: %s\ntemp: %s", speed, temp)
   # write fan metrics to file for node-exporter/prometheus
   if NODE_EXPORTER == 1:
      prometheus_exporter(speed, temp)

def calculate_dynamic_speed(temp: int) -> int:
   """Calculate dynamic fan speed based on temperature.

   Args:
       temp (int): _description_

   Returns:
       int: _description_
   """
   step = (FAN_HIGH - FAN_LOW)/(MAX_TEMP - MIN_TEMP)   
   delta = temp - MIN_TEMP
   return FAN_LOW + ( round(delta) * step )

def handle_fan_speed() -> None:
   """Handle fan speed
   """
   temp = get_cpu_temperature()

   # Turn off the fan if temperature is below MIN_TEMP
   if temp < MIN_TEMP:
      set_fan_speed(FAN_OFF,temp)

   # Set fan speed to MAXIMUM if the temperature is above MAX_TEMP
   elif temp > MAX_TEMP:
      set_fan_speed(FAN_MAX,temp)

   # Caculate dynamic fan speed
   else:
      set_fan_speed(calculate_dynamic_speed(temp), temp)

def start_fan_control() -> None:
   fan = lgpio.gpiochip_open(0)
   lgpio.gpio_claim_output(fan, PWM_GPIO_NR)
   set_fan_speed(FAN_LOW,MIN_TEMP)

   # Handle fan speed every WAIT_TIME sec
   if WAIT_TIME < 1:
      handle_fan_speed()
   else:
      while True:
         handle_fan_speed()
         time.sleep(WAIT_TIME)

if __name__ == '__main__':
   start_fan_control()