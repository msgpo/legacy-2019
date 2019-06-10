# Welcome to Sonic Pi v3.0.1
require 'thread'

#require 'spi'
require 'httparty'
require 'json'

def doze(seconds)
  Kernel.sleep seconds
end


module Game
  @button_callback = lambda {|b|}
  @axis_callback = lambda {|a, v|}
  @hat_callback = lambda {|v|}

  def self.on_button(&block)
    @button_callback = block
  end

  def self.on_axis(&block)
    @axis_callback = block
  end

  def self.on_hat(&block)
    @hat_callback = block
  end

  def self.button_callback
    return @button_callback
  end

  def self.axis_callback
    return @axis_callback
  end

  def self.hat_callback
    return @hat_callback
  end
end

def start_game
  in_thread do
    require 'sdl'
    SDL::init(SDL::INIT_JOYSTICK)
    joy = SDL::Joystick.open(0)

    loop do
      while event = SDL::Event2::poll
        case event
        when SDL::Event2::JoyButtonDown
          Game.button_callback.call(event.button)
        when SDL::Event2::JoyAxis
          Game.axis_callback.call(event.axis, event.value)
        when SDL::Event2::JoyHat
          Game.hat_callback.call(event.value)
        end
      end

      sleep 0.05
    end
  end
end

Game.on_button do |button|
  button_name = case button
  when 0; "a"
  else; button.to_s
  end

  cue "button_#{button_name}".to_sym
end

start_game

module Pixels
  @pixel_count = 32
  @pixels = [0] * 3 * @pixel_count

  #@spi = SPI.new(device: '/dev/spidev0.0')
  #@spi.speed = 1000000

  @semaphore = Mutex.new

  def self.doze(seconds)
    Kernel.sleep seconds
  end

  def self.show
    @semaphore.synchronize do
      #@spi.xfer(txdata: @pixels)
      HTTParty.post("http://localhost:5000/pixels/raw",
                    body: @pixels.to_json,
                    headers: { "Content-Type": "application/json" })
    end
  end

  def self.one!(i, r, g, b)
    i *= 3
    @semaphore.synchronize do
      @pixels[i] = b
      @pixels[i+1] = g
      @pixels[i+2] = r
    end
  end

  def self.all!(r, g, b)
    @semaphore.synchronize do
      @pixel_count.times do |i|
        @pixels[(i*3)] = b
        @pixels[(i*3)+1] = g
        @pixels[(i*3)+2] = r
      end
    end
  end

  def self.one(i)
    i *= 3
    return [@pixels[i+2], @pixels[i+1], @pixels[i]]
  end

  def self.all
    return @pixels
  end

  def self.blend_all(r, g, b, steps: 10, delay: 0.05, wait: true)
    thread = Thread.new do
      start = Array.new(@pixels)
      increment = [0] * 3 * @pixel_count
      steps_f = steps.to_f
      @pixel_count.times do |i|
        i3 = i * 3
        increment[i3] = (b - @pixels[i3]) / steps_f
        increment[i3+1] = (g - @pixels[i3+1]) / steps_f
        increment[i3+2] = (r - @pixels[i3+2]) / steps_f
      end

      steps.times do |t|
        @semaphore.synchronize do
          @pixel_count.times do |i|
            i3 = i*3
            @pixels[i3] = start[i3] + (increment[i3]*t).to_i
            @pixels[i3+1] = start[i3+1] + (increment[i3+1]*t).to_i
            @pixels[i3+2] = start[i3+2] + (increment[i3+2]*t).to_i
          end
        end

        show
        doze delay
      end

      all!(r, g, b)
      show
    end

    if wait then
      thread.join
    end
  end

  def self.blend_rgb(rgb, steps: 10, delay: 0.05, wait: true)
    thread = Thread.new do
      start = Array.new(@pixels)
      increment = [0] * 3 * @pixel_count
      steps_f = steps.to_f
      @pixel_count.times do |i|
        i3 = i * 3
        increment[i3] = (rgb[i3] - @pixels[i3]) / steps_f
        increment[i3+1] = (rgb[i3+1] - @pixels[i3+1]) / steps_f
        increment[i3+2] = (rgb[i3+2] - @pixels[i3+2]) / steps_f
      end

      steps.times do |t|
        @semaphore.synchronize do
          @pixel_count.times do |i|
            i3 = i*3
            @pixels[i3] = start[i3] + (increment[i3]*t).to_i
            @pixels[i3+1] = start[i3+1] + (increment[i3+1]*t).to_i
            @pixels[i3+2] = start[i3+2] + (increment[i3+2]*t).to_i
          end
        end

        show
        doze delay
      end

      @semaphore.synchronize do
        @pixel_count.times do |i|
          i3 = i*3
          @pixels[i3] = rgb[i3+2]
          @pixels[i3+1] = rgb[i3+1]
          @pixels[i3+2] = rgb[i3]
        end
      end

      show
    end

    if wait then
      thread.join
    end
  end

  def self.blend_one(i, r, g, b, steps: 10, delay: 0.05, wait: true)
    thread = Thread.new do
      start = @pixels[i..(i+3)]
      steps_f = steps.to_f
      increment = [0] * 3

      i3 = i * 3
      increment[0] = (b - @pixels[i3]) / steps_f
      increment[1] = (g - @pixels[i3+1]) / steps_f
      increment[2] = (r - @pixels[i3+2]) / steps_f

      steps.times do |t|
        @semaphore.synchronize do
          @pixels[i3] = start[0] + (increment[0]*t).to_i
          @pixels[i3+1] = start[1] + (increment[1]*t).to_i
          @pixels[i3+2] = start[2] + (increment[2]*t).to_i
        end

        show
        doze delay
      end

      one!(i, r, g, b)
      show
    end

    if wait then
      thread.join
    end
  end

  def self.spin(steps: 10, delay: 0.05, wait: true)
    thread = Thread.new do
      steps.times do |t|
        @semaphore.synchronize do
          b1 = @pixels[0]
          g1 = @pixels[1]
          r1 = @pixels[2]
          (@pixel_count-1).times do |i|
            i3 = i*3
            j3 = (i+1)*3

            @pixels[i3] = @pixels[j3]
            @pixels[i3+1] = @pixels[j3+1]
            @pixels[i3+2] = @pixels[j3+2]
          end

          ilast = @pixels.length - 3
          @pixels[ilast] = b1
          @pixels[ilast+1] = g1
          @pixels[ilast+2] = r1
        end

        show
        doze delay
      end
    end

    if wait then
      thread.join
    end
  end

  def self.wheel(pos)
    if pos < 85
      return [pos * 3, 255 - pos * 3, 0]
    elsif pos < 170
      pos -= 85
      return [255 - pos * 3, 0, pos * 3]
    else
      pos -= 170
      return [0, pos * 3, 255 - pos * 3]
    end
  end

  def self.rainbow
    rgb = [0] * 3 * @pixel_count
    @pixel_count.times do |i|
      i3 = i * 3
      irgb = wheel(i * (256 / @pixel_count))
      rgb[i3] = irgb[0]
      rgb[i3+1] = irgb[1]
      rgb[i3+2] = irgb[2]
    end

    return rgb
  end

end

def rgb (r, g, b, i: nil, time: 1)
  steps = time / 0.05
  if i then
    Pixels.blend_one(i, r, g, b, steps: steps, wait: true)
  else
    Pixels.blend_all(r, g, b, steps: steps, wait: true)
  end
end

def red (i: nil, time: 1)
  rgb 255, 0, 0, i: i, time: time
end

def green (i: nil, time: 1)
  rgb 0, 255, 0, i: i, time: time
end

def blue (i: nil, time: 1)
  rgb 0, 0, 255, i: i, time: time
end

def orange (i: nil, time: 1)
  rgb 255, 128, 0, i: i, time: time
end

def yellow (i: nil, time: 1)
  rgb 255, 255, 0, i: i, time: time
end

def indigo (i: nil, time: 1)
  rgb 0, 255, 255, i: i, time: time
end

def violet (i: nil, time: 1)
  rgb 255, 0, 255, i: i, time: time
end

def black (i: nil, time: 1)
  rgb 0, 0, 0, i: i, time: time
end

def white (i: nil, time: 1)
  rgb 255, 255, 255, i: i, time: time
end

def strobe (cycles, time: 0.075, r: 255, g: 255, b: 255)
  cycles.times do
    rgb r, g, b, time: 0
    doze time
    black time: 0
    doze time
  end
end

def rainbow (time: 1)
  steps = time / 0.05
  Pixels.blend_rgb(Pixels.rainbow, steps: steps, wait: true)
end

def spinner (time: 1)
  steps = time / 0.05
  Pixels.spin(steps: steps, wait: true)
end

in_thread do
  sync :button_a
  rainbow
  spinner 10
end

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
    cue :other
  end
end

live_loop :drum do
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

live_loop :other1 do
  sync :other
  sync :other
  with_fx :gverb do
    sample :bass_drop_c
  end
end

rainbow
live_loop :lights do
  spinner time: 0.1
  sleep 0.1
end

#blue i: 0, time: 2
#spinner time: 5
#strobe 25

#with_fx :echo, mix: 0.3, phase: 0.25 do
#  synth :piano
#  play 50
#end
