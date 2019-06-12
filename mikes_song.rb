# Author: Michael Hansen
# Date: 2019 June 12

require '/home/pi/Legacy/legacy.rb'
use_leds
black time: 0

count = 1
live_loop :piano do
  with_fx :reverb, room: 1 do
    sample :bd_boom, amp: 20, rate: 1
  end
  sleep 0.5
  with_fx :echo, mix: 0.3, phase: 0.25 do
    with_synth :piano do
      if count < 3 then
        play :C3
        sleep 0.25
        play :A4
        sleep 0.25
        play :B4
      else
        play :C3
        sleep 0.25
        play :C4
        sleep 0.25
        play :A4
      end
    end
  end

  sleep 2
  count += 1

  if count > 4 then
    count = 1
    cue :bass
  end
end

live_loop :drum1 do
  sample :drum_heavy_kick
  sleep 1
end

in_thread do
  4.times do |i|
    t = 1
    if i == 0 then
      t = 2
    end

    t.times do
      sync :bass
    end

    with_fx :gverb, amp: (i+1) do
      sample :bass_drop_c
    end

    case i
    when 0; red
    when 1; green
    when 2; blue
    when 3; rainbow
    end

    sleep 1
    black
    sleep 1
  end
end

6.times do
  sync :bass
end

live_loop :colors do
  5.times do
    colors = [:red, :orange, :green, :blue, :indigo, :violet, :pink]
    color_names = []
    32.times do |i|
      color_names.append(colors.choose)
    end

    blend color_names
    sleep 1
  end

  spinner time: 2
  sleep 3
end

use_synth :tb303

live_loop :wah do
  play choose(chord(:E3, :minor)), release: 0.3, cutoff: rrand(60, 120)
  sleep 0.25
end

live_loop :prophet do
  use_synth :prophet
  play 38
  sleep 0.25
  play 50
  sleep 0.25
  play 62
  sleep 3.75
end

blip_rate = 1
live_loop :drums2 do
  sample :drum_heavy_kick
  2.times do
    sample :elec_blip2, rate: blip_rate
    sleep 0.25
  end
  sample :elec_snare
  4.times do
    sample :drum_tom_mid_soft
    sleep 0.125
  end

  blip_rate += 1
  if blip_rate > 4 then
    blip_rate = 1
  end
end
