#!/usr/bin/env python2

import time

import pigpio

class sniffer:
   """
   A class to passively monitor activity on an I2C bus.  This should
   work for an I2C bus running at 100kbps or less.  You are unlikely
   to get any usable results for a bus running any faster.

   It needs the pigpio daemon to be running.
   See `ps -A -o pid,user,args | grep pigpio` to be sure it is.

   See __init__() documentation for output format.
   """

   def __init__(self, pi, SCL, SDA, set_as_inputs=True):
      """
      Instantiate with the Pi and the gpios for the I2C clock
      and data lines.

      If you are monitoring one of the Raspberry Pi buses you
      must set set_as_inputs to False so that they remain in
      I2C mode.

      The pigpio daemon should have been started with a higher
      than default sample rate.

      For an I2C bus rate of 100Kbps, `sudo pigpiod -s 2` should work.

      A message is printed for each I2C transaction formatted with
      "[" for the START
      "XX" two hex characters for each data byte
      "+" if the data is ACKd, "-" if the data is NACKd
      "]" for the STOP

      E.g. Reading the X, Y, Z values from an ADXL345 gives:

      [A6+32+]
      [A7+01+FF+F2+FF+06+00-]
      """

      self.pi = pi
      self.gSCL = SCL
      self.gSDA = SDA

      self.FALLING = 0
      self.RISING = 1
      self.STEADY = 2

      self.in_data = False
      self.byte = 0
      self.bit = 0
      self.oldSCL = 1
      self.oldSDA = 1

      self.transact = ""

      if set_as_inputs:
         self.pi.set_mode(SCL, pigpio.INPUT)
         self.pi.set_mode(SDA, pigpio.INPUT)

      self.cbA = self.pi.callback(SCL, pigpio.EITHER_EDGE, self._cb)
      self.cbB = self.pi.callback(SDA, pigpio.EITHER_EDGE, self._cb)

   def _parse(self, SCL, SDA):
      """
      Accumulate all the data between START and STOP conditions
      into a string and output when STOP is detected.
      """

      if SCL != self.oldSCL:
         self.oldSCL = SCL
         if SCL:
            xSCL = self.RISING
         else:
            xSCL = self.FALLING
      else:
            xSCL = self.STEADY

      if SDA != self.oldSDA:
         self.oldSDA = SDA
         if SDA:
            xSDA = self.RISING
         else:
            xSDA = self.FALLING
      else:
            xSDA = self.STEADY

      if xSCL == self.RISING:
         if self.in_data:
            if self.bit < 8:
               self.byte = (self.byte << 1) | SDA
               self.bit += 1
            else:
               self.transact += '{:02X}'.format(self.byte)
               if SDA:
                  self.transact += '-'
               else:
                  self.transact += '+'
               self.bit = 0
               self.byte = 0

      elif xSCL == self.STEADY:

         if xSDA == self.RISING:
            if SCL:
               self.in_data = False
               self.byte = 0
               self.bit = 0
               self.transact += ']' # STOP
               print (self.transact)
               self.transact = ""

         if xSDA == self.FALLING:
            if SCL:
               self.in_data = True
               self.byte = 0
               self.bit = 0
               self.transact += '[' # START

   def _cb(self, gpio, level, tick):
      """
      Check which line has altered state (ignoring watchdogs) and
      call the parser with the new state.
      """
      SCL = self.oldSCL
      SDA = self.oldSDA

      if gpio == self.gSCL:
         if level == 0:
            SCL = 0
         elif level == 1:
            SCL = 1

      if gpio == self.gSDA:
         if level == 0:
            SDA = 0
         elif level == 1:
            SDA = 1

      self._parse(SCL, SDA)

   def cancel(self):
      """Cancel the I2C callbacks."""
      self.cbA.cancel()
      self.cbB.cancel()

def main():
   import I2C_sniffer

   pi = pigpio.pi()

   # The 2nd parameter needs to be the gpio for SCL
   # The 3rd parameter needs to be the gpio for SDA
   # The 4th parameter needs to be False if you are using the I2C gpios, True otherwise.
   s = I2C_sniffer.sniffer(pi, 3, 2, False) # leave gpios 3/2 in I2C mode

   try:
      time.sleep(60000)
   except KeyboardInterrupt:
       pass

   print()

   s.cancel()

   pi.stop()


if __name__ == "__main__":
    main()
