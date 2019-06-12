require 'thread'
require './legacy.rb'

# Test gamepad
use_gamepad

m = Mutex.new
cv = ConditionVariable.new

on_button :a do
  m.synchronize do
    cv.signal
  end
end

# Wait until button press
puts "Press the A button"
m.synchronize do
  cv.wait(m)
end
puts "OK"

use_leds spi: false

# Test LEDS
black time: 0
rainbow
sleep 3
strobe 10
sleep 1
black time: 0
red i: 1, time: 0
spinner time: 5
sleep 5
black time: 0
sleep 2

puts "Done"
