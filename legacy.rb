# LEGACY 2019 code for Sonic Pi integration
# Author: Michael Hansen
# Date: 2019 June 12

require 'thread'
require 'json'

# -----------------------------------------------------------------------------

# Uses SDL to capture gamepad events.
# Calls provided callback functions from a separate thread.
module Gamepad
  @button_queue = Queue.new

  # Numbers and names for buttons on Logitech F310
  @button_map = {
    0 => :a,
    1 => :b,
    2 => :x,
    3 => :y,
    4 => :lb,
    5 => :rb,
    6 => :back,
    7 => :start,
    8 => :logitech,
    9 => :lstick,
    10 => :rstick
  }

  # True if game loop is running
  @running = false
  @thread = nil

  # Queue to add to when buttons are pressed
  def self.button_queue
    return @button_queue
  end

  # Map from index to button symbol name
  def self.button_map
    return @button_map
  end

  # Game loop
  def self.run
    if not @running then
      @running = true
      @thread = Thread.new do
        require 'sdl'
        SDL::init(SDL::INIT_JOYSTICK)
        joy = SDL::Joystick.open(0)

        # Index => true if button is down
        button_down = {}

        while @running do
          # Doing this manually because events don't work in Sonic Pi
          SDL::Joystick.update_all

          # Check all buttons, track state
          joy.num_buttons.times do |i|
            already_down = button_down.fetch(i, false)
            if joy.button(i) then
              if not already_down
                button_down[i] = true
                @button_queue.push i
              end
            else
              button_down[i] = false
            end
          end

          sleep 0.05
        end
      end
    end
  end

  # Stops game loop
  def self.stop
    @running = false
    if @thread then
      @thread.join
      @thread = nil
    end
  end

end

# -----------------------------------------------------------------------------

# Start gamepad thread and handle button presses by name
def use_gamepad(&block)
  Gamepad.run
  in_thread(name: :gamepad) do
    loop do
      if not Gamepad.button_queue.empty?
        button = Gamepad.button_queue.pop()
        button_sym = Gamepad.button_map.fetch(button, nil)
        block.call(button_sym)

        File.open("/home/hansenm/button_callback.txt", "w") do |f|
          f.write("#{button_sym}")
        end
      end
      sleep 0.05
    end
  end
end

# -----------------------------------------------------------------------------

# Communicates with WS2801 LED strip via SPI.
# Does blending animations in separate thread.
module Pixels
  # Queue with function calls to be made in animation thread
  @pixel_queue = Queue.new

  # Number of LEDs
  @pixel_count = 32

  # BGR values for each LED
  @pixels = [0] * 3 * @pixel_count

  # True if animation thread is running
  @running = false
  @thread = nil

  # SPI interface to WS2801
  @spi = nil

  # Synchronization for @pixels
  @semaphore = Mutex.new

  @colors_rgb = {
    :red => [255, 0, 0],
    :orange => [255, 128, 0],
    :yellow => [255, 255, 0],
    :green => [0, 255, 0],
    :blue => [0, 0, 255],
    :indigo => [255, 255, 0],
    :violet => [255, 0, 255],
    :pink => [255, 0, 128],
    :black => [0, 0, 0],
    :white => [255, 255, 255]
  }

  def self.colors_rgb
    return @colors_rgb
  end

  def self.colors
    return @colors_rgb.keys
  end

  # Connects to WS2801
  def self.use_spi
    require 'spi'
    @spi = SPI.new(device: '/dev/spidev0.0')
    @spi.speed = 1000000
  end

  # Shows colors values in @pixels
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

  # Sets RGB color of the ith LED
  def self.one!(i, r, g, b)
    i *= 3
    @semaphore.synchronize do
      @pixels[i] = b
      @pixels[i+1] = g
      @pixels[i+2] = r
    end
  end

  # Sets RGB color of all LEDs
  def self.all!(r, g, b)
    @semaphore.synchronize do
      @pixel_count.times do |i|
        @pixels[(i*3)] = b
        @pixels[(i*3)+1] = g
        @pixels[(i*3)+2] = r
      end
    end
  end

  # Gets RGB color if the ith LED
  def self.one(i)
    i *= 3
    return [@pixels[i+2], @pixels[i+1], @pixels[i]]
  end

  # Gets BGR colors of all LEDs
  def self.all
    return @pixels
  end

  # Blends from current to new RGB color for all LEDs
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

      # Blend each animation step
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

  # Blends from current to new RGB colors for all LEDs
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

      # Blend each animation step
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

      # Ensure final values match input color list
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

  # Blend from the current to new RGB color for the ith LED
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

      # Blend each animation step
      steps.times do |t|
        @semaphore.synchronize do
          @pixels[i3] = start[0] + (increment[0]*t).to_i
          @pixels[i3+1] = start[1] + (increment[1]*t).to_i
          @pixels[i3+2] = start[2] + (increment[2]*t).to_i
        end

        show
        sleep delay
      end

      # Ensure the final value matches input RGB
      one!(i, r, g, b)
      show
    end

    if wait then
      thread.join
    end
  end

  # ---------------------------------------------------------------------------

  # Cycle all LED colors up (first LED color goes to last, second to first, etc.)
  def self.spin(steps: 10, delay: 0.05, wait: true)
    thread = Thread.new do
      steps = steps.to_i

      # Do for specified number of steps
      steps.times do |t|
        @semaphore.synchronize do
          # Save first LED colors
          b1 = @pixels[0]
          g1 = @pixels[1]
          r1 = @pixels[2]

          # Shift all LEDs up
          (@pixel_count-1).times do |i|
            i3 = i*3
            j3 = (i+1)*3

            @pixels[i3] = @pixels[j3]
            @pixels[i3+1] = @pixels[j3+1]
            @pixels[i3+2] = @pixels[j3+2]
          end

          # Set last LED to saved first LED values
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

  # Get rainbow color from specific position in color wheel
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

  # Get blended rainbow RGB values for LEDs
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

  # Pause some number of seconds
  def self.doze(seconds, *args)
    sleep seconds
  end

  # Run animation thread
  def self.run
    if not @running
      @running = true
      @thread = Thread.new do
        while @running do
          # name, positional args, keyword args
          task = @pixel_queue.pop()
          if task then
            Pixels.send(task[0], *task[1], **task[2])
          end
        end
      end
    end
  end

  def self.enqueue(task)
    @pixel_queue.push(task)
  end

  # Stops the main animation thread
  def self.stop
    @running = false
    if @thread then
      @pixel_queue.push(nil)
      @thread.join
      @thread = nil
    end
  end

end

# -----------------------------------------------------------------------------

# Enable LEDs and animation
def use_leds(spi: true)
  Pixels.run
  if spi then
    Pixels.use_spi
  end
end

# Pause animation thread
def doze(seconds)
  Pixels.enqueue([:doze, [seconds], {}])
end

# Set RGB color(s) for all or ith LED
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

def pink (i: nil, time: 1)
  rgb 255, 0, 128, i: i, time: time
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

def blend (color_names, time: 1)
  steps = time / 0.05
  rgb = []
  color_names.each do |c|
    rgb += Pixels.colors_rgb[c]
  end
  Pixels.enqueue([:blend_rgb, [rgb], { steps: steps, wait: true }])
end

# Blend to rainbow colors
def rainbow (time: 1)
  steps = time / 0.05
  Pixels.enqueue([:blend_rgb, [Pixels.rainbow], { steps: steps, wait: true }])
end

# Cycle LED colors up
def spinner (time: 1)
  steps = time / 0.05
  Pixels.enqueue([:spin, [], { steps: steps, wait: true }])
end

# -----------------------------------------------------------------------------

def stop_legacy
  Gamepad.stop
  Pixels.stop
end
