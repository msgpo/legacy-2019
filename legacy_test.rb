require './legacy.rb'

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
