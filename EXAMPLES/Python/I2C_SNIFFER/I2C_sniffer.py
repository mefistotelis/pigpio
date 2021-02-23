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
      self.in_ack = False
      self.byte = 0
      self.bit = 0
      self.oldSCL = 1
      self.oldSDA = 1

      self.transact = ""
      self.last_sda_tick = 0
      self.last_start_tick = 0
      self.SCL_since_start = 0

      if set_as_inputs:
         self.pi.set_mode(SCL, pigpio.INPUT)
         self.pi.set_mode(SDA, pigpio.INPUT)

      self.cbA = self.pi.callback(SCL, pigpio.EITHER_EDGE, self._cbSCL)
      self.cbB = self.pi.callback(SDA, pigpio.EITHER_EDGE, self._cbSDA)


   def _cbSDA(self, gpio, level, tick):
      """
      Check which line has altered state (ignoring watchdogs) and
      call the parser with the new state.
      """
      #tick = int(time.time() * 1000000)
      SCL = self.oldSCL

      if level == 0:
         SDA = 0
      elif level == 1:
         SDA = 1
      else:
         return

      if True:
         if (self.in_data) and (tick - self.last_sda_tick > 4000):
             if self.bit > 0:
                 self.transact += "{:02X}".format(self.byte << (8-self.bit))
                 self.bit = 0
                 self.byte = 0
             self.transact += " !to" # TIMEOUT
             print (self.transact)
             self.transact = ""
         self.last_sda_tick = tick

      if SDA != self.oldSDA:
         self.oldSDA = SDA
         if SDA: # rising edge of SDA
             if SCL:
                 if self.in_data: # Proper STOP bit
                     if self.in_ack: # ACK should be before STOP; but if we failed to get it, do it now
                         self.transact += '-'
                         self.in_ack = False
                     self.in_data = False
                     if self.bit > 1: # On STOP, SCL goes up first, so we should've counted one bit
                         self.transact += "{:02X}".format(self.byte)
                         self.transact += " !{:d}tr".format(self.bit) # TRUNCATED DATA
                     self.bit = 0
                     self.byte = 0
                 else: # Misplaced STOP bit
                     pass
                 self.transact += "]" # STOP
                 # estimate baud rate
                 self.transact += " baud={:d}".format(1000000 * (self.SCL_since_start/2) / (tick - self.last_start_tick + 1))
                 print(self.transact)
                 self.transact = ""
         else: # falling edge of SDA
             if SCL:
                 if self.in_ack: # This is not START, but misinterpreted ACK
                     pass # Ignore it, next SCL change will handle this
                 elif not self.in_data: # Packet begin START bit
                     self.last_start_tick = tick
                     self.SCL_since_start = 0
                     self.in_data = True
                     self.in_ack = False
                     self.byte = 0
                     self.bit = 0
                     if self.transact == "":
                         self.transact = "{:7.03f}: ".format(float(tick)/1000000)
                     self.transact += "[" # START
                 else:
                     if self.bit <= 1: # READ begin START bit
                         self.byte = 0
                         self.bit = 0
                         self.transact += "[" # START
                     else: # unexpected START inside of data - misinterpreted data
                         self.transact += " !{:d}md".format(self.bit) # MISINTERPRETED DATA
                         pass


   def _cbSCL(self, gpio, level, tick):
        """
        Add data on rising clock edge, or check ACK on falling one.
        """
        SDA = self.oldSDA

        if level == 0:
            SCL = 0
        elif level == 1:
            SCL = 1
        else:
            return

        self.oldSCL = SCL
        if SCL: # rising edge of SCL - read data bytes on this edge
            if self.in_data:
                if self.bit < 8:
                    self.byte = (self.byte << 1) | SDA
                    self.bit += 1
                else:
                    self.in_ack = True
                    self.bit = 0
                    self.transact += '{:02X}'.format(self.byte)
                    self.byte = 0
        else: # falling edge of SCL - read ACK on this edge
            if self.in_ack:
                if SDA:
                    self.transact += '-'
                else:
                    self.transact += '+'
                self.in_ack = False
        self.SCL_since_start += 1


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
