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

live_loop :rain do
  with_fx :level, amp: 0.25 do
    with_fx :distortion do
      with_fx :echo, mix: rand(), phase: rand() do
        sample :ambi_swoosh
      end
    end
  end

  sleep 0.25 + rand()
end

live_loop :bass do
  2.times do
    sync :bass
  end

  with_fx :gverb do
    sample :bass_drop_c
  end
end

6.times do
  sync :bass
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
