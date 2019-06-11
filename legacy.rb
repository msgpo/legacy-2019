# Welcome to Sonic Pi v3.0.1
require 'thread'
require 'json'

module Gamepad
  @button_callback = lambda {|b|}
  @axis_callback = lambda {|a, v|}
  @hat_callback = lambda {|v|}

  @running = false

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

  def self.run
    if not @running
      @running = true
      Thread.new do
        require 'sdl'
        SDL::init(SDL::INIT_EVERYTHING)
        joy = SDL::Joystick.open(0)

        loop do
          event = SDL::Event2.poll
          case event
          when SDL::Event2::JoyButtonDown
            Gamepad.button_callback.call(event.button)
          when SDL::Event2::JoyAxis
            Gamepad.axis_callback.call(event.axis, event.value)
          when SDL::Event2::JoyHat
            Gamepad.hat_callback.call(event.value)
          end

          sleep 0.05
        end
      end
    end
  end
end

def use_gamepad
  Gamepad.run
end

module Pixels
  @pixel_queue = Queue.new
  @pixel_count = 32
  @pixels = [0] * 3 * @pixel_count
  @running = false

  @spi = nil

  @semaphore = Mutex.new

  def self.use_spi
    require 'spi'
    @spi = SPI.new(device: '/dev/spidev0.0')
    @spi.speed = 1000000
  end

  def self.show
    @semaphore.synchronize do
      if @spi
        @spi.xfer(txdata: @pixels)
      else
        require 'httparty'
        HTTParty.post("http://localhost:5000/pixels/raw?bgr=true",
                      body: @pixels.to_json,
                      headers: { "Content-Type": "application/json" })
      end
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
      steps = steps.to_i
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
        sleep delay
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
      steps = steps.to_i
      steps_f = steps.to_f
      @pixel_count.times do |i|
        i3 = i * 3
        increment[i3] = (rgb[i3+2] - @pixels[i3]) / steps_f
        increment[i3+1] = (rgb[i3+1] - @pixels[i3+1]) / steps_f
        increment[i3+2] = (rgb[i3] - @pixels[i3+2]) / steps_f
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
        sleep delay
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
      steps = steps.to_i
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
        sleep delay
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
      steps = steps.to_i
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
        sleep delay
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

  def self.doze(seconds, *args)
    sleep seconds
  end

  def self.run
    if not @running
      @running = true
      Thread.new do
        loop do
          # name, positional args, keyword args
          task = @pixel_queue.pop()
          Pixels.send(task[0], *task[1], **task[2])
        end
      end
    end
  end

  def self.enqueue(task)
    @pixel_queue.push(task)
  end

end

def use_leds
  Pixels.run
  Pixels.use_spi
end

def doze(seconds)
  Pixels.enqueue([:doze, [seconds], {}])
end

def rgb (r, g, b, i: nil, time: 1)
  steps = time / 0.05
  if i then
    Pixels.enqueue([:blend_one, [i, r, g, b], { steps: steps, wait: true }])
  else
    Pixels.enqueue([:blend_all, [r, g, b], { steps: steps, wait: true }])
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
  Pixels.enqueue([:blend_rgb, [Pixels.rainbow], { steps: steps, wait: true }])
end

def spinner (time: 1)
  steps = time / 0.05
  Pixels.enqueue([:spin, [], { steps: steps, wait: true }])
end
