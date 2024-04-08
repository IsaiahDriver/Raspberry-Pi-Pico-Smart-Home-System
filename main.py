# This is a sample code that demonstrates wireless communication.
# You are expected to use this code and modify it to suit your project needs.

# ------------------------------------------------------------------------
# In this project, a red LED is connected to GP14.
# The red LED is controlled based on the value of a light sensor's output.
# The light sensor output is connected to GP26 (ADC pin).
# The red LED status and the value of the red LED pin (GP14) are communicated wirelessly to a server.
# The status and value are displayed on the webpage. In addition, the user interface has
# a circle indicating the LED turns color depending upon the status of the physical LED. 
# ------------------------------------------------------------------------


# -----------------------------------------------------------------------
# The following list of libraries are required. Do not remove any. 
import machine
from machine import Pin
import network
import usocket as socket
import utime as time
import _thread
import json
# -------------------------------------------------------------------------
# Initialize system variables
are_systems_active = False
is_terminal_active = True
is_system_terminated = False

# Define target temperature and related variables
target_temp = 980 
target_temp_range = 100
temp_samples = []
current_temp = 0
temp_sample_size = 50

# Define variables for controlling lights
are_lights_on = False
target_brightness = 19000
light_samples = []
current_light = 0
light_sample_size = 50

# Define variables for motion detection
is_motion_detected = False
is_motion_displayed = False
detect_time = 0
is_ir_sensor_init = False
ir_ref_val = 0.
ir_thresh = 900 # lower = more sensitive
ir_init_sample_size = 25
ir_sample_size = 1
ir_samples = []
current_ir = 0
has_displayed = False

is_timer_reset = False
is_timer_set = False

timer_start_time = 0
deactivation_delay = 5 #(seconds)

# Initialize GPIO pins for LEDs, IR emitter, light sensor, temperature sensor, and IR sensor
led_pico = Pin("LED", Pin.OUT)
led_red = machine.Pin(15, machine.Pin.OUT)
led_green = machine.Pin(14, machine.Pin.OUT)
ir_emitter = machine.Pin(22, machine.Pin.OUT)  
light_sensor = machine.ADC(26)
temp_sensor = machine.ADC(27)
ir_sensor = machine.ADC(28)

server: socket.socket
# -------------------------------------------------------------------------

# The below portion of the code is to be tweaked based on your needs. 

# Configure GP14 as output and define it as redLED_pin 

# Function to calculate running average
def running_average(new_sample, num_samples, all_samples):
    """
    Calculate the running average of a set of samples.

    Args:
        new_sample (int): New sample value to be added.
        num_samples (int): Number of samples to consider for the average.
        all_samples (list): List containing all previous samples.

    Returns:
        float: The running average of the samples.
    """
    all_samples.append(new_sample)
    if len(all_samples) > num_samples:
        all_samples.pop(0)
    total = sum(all_samples)
    average = total / len(all_samples)

    return average

# Function to control temperature
def control_temp(active_state):
    """
    Control temperature based on the active state.

    Args:
        active_state (bool): Indicates whether temperature control is active or not.
    """
    global current_temp, target_temp, target_temp_range

    if (not active_state):
        update_terminal_once("Temp control: [INACTIVE] - temperature control inactive", 1)
        return

    if (current_temp > (target_temp + target_temp_range)):
        update_terminal_once("Temp control: [HEATING] - temperature too low", 1)
    elif (current_temp < (target_temp - target_temp_range)):
        update_terminal_once("Temp control: [COOLING] - temperature too high", 1)
    else:
        update_terminal_once("Temp control: [OFF] - target temperature met", 1)

# Function to control lights
def control_light(active_state): 
    """
    Control lights based on the active state.

    Args:
        active_state (bool): Indicates whether light control is active or not.
    """
    global are_lights_on, current_light, target_brightness

    if (not active_state):
        update_terminal_once("Light control: [LIGHTS OFF] - lighting control inactive", 2)
        are_lights_on = False
        return

    if (not are_lights_on and current_light > target_brightness):
        update_terminal_once("Light control: [LIGHTS ON] - brightness too low", 2)
        are_lights_on = True

def init_new_motion_ref():
    global ir_sensor 
    for x in range(2 * ir_init_sample_size):
        ir_average_val = running_average(ir_sensor.read_u16(), ir_init_sample_size, ir_samples)
    #print ("NEW IR REF: ", ir_average_val)
    return ir_average_val
            #print(ir_average_val)

def detect_motion():
    global current_ir, ir_sample_size, is_ir_sensor_init, ir_ref_val, ir_thresh
    if (not is_ir_sensor_init):
        ir_ref_val = init_new_motion_ref()
        is_ir_sensor_init = True
        #print("Motion sensor: [INITIALIZED] - motion sensor calibrated to ", ir_ref_val)               
    current_ir = ir_sensor.read_u16()
    if ((current_ir < (ir_ref_val - ir_thresh)) or (current_ir > (ir_ref_val + ir_thresh))):
        ir_ref_val = init_new_motion_ref()
        #print("MOTION DETECTED!")
        return True
    else:
        return False
    
def get_system_GUI_status():
    global are_systems_active
    if are_systems_active:
        return "Home"
    else:
        return "Away"
    
def get_motion_GUI_status():
    global is_motion_detected, detect_time, is_motion_displayed, has_displayed
    """
    if is_motion_detected:
      return "DETECTED!"
    else:
      return "..."
    
    """
    if is_motion_displayed and not has_displayed:
        detect_time = time.time()
        has_displayed = True
        return "DETECTED!"
    elif ((time.time() - detect_time > 3) and is_motion_displayed):
        is_motion_displayed = False
        has_displayed = False
        return "..."
    elif is_motion_displayed and has_displayed:
        return "DETECTED!"
    else:
        return "..."
   
def get_light_GUI_status():
   global are_lights_on
   if are_lights_on:
      return "ON"
   else:
      return "OFF"

def update_deactivation_timer():
    global is_timer_set, are_systems_active
    if ((time.time() - timer_start_time) > deactivation_delay):
        are_systems_active = False
        is_timer_set = False
        print("main: [SYSTEMS OFF] - no motion detected ")

def reset_deactivation_timer():
  global is_timer_set, timer_start_time
  is_timer_set = True
  timer_start_time = time.time()

# Dictionary to store previous terminal messages
prior_terminal_messages = {}
def update_terminal_once(message, source_id):
    """
    Update the terminal with a new message if it differs from the previous message.

    Args:
        message (str): The new message to be displayed.
        source_id (int): Identifier of the message source.

    Returns:
        None
    """
    global prior_terminal_messages
    if (not is_terminal_active):
        return

    if(not source_id in prior_terminal_messages):
        prior_terminal_messages[source_id] = message
        print(message)    
    elif (message != prior_terminal_messages[source_id]):
        print(message)
        prior_terminal_messages.update({source_id: message})
    else:
        return


def update_GUI_sensor_status():
    pass

# Define a function to periodically check the ADC pin and control the red LED pin.
def update_system():
  global are_systems_active
  global current_ir, current_light, current_temp
  global timer_start_time
  global light_samples, ir_samples, temp_samples
  global is_timer_set
  global is_motion_displayed
  global detect_time

  while True:
    if is_system_terminated:
        return
    # Read light sensor data
    light_raw_val = light_sensor.read_u16()
    light_average_val = running_average(light_raw_val, light_sample_size, light_samples)
    current_light = light_average_val # (PLACEHOLDER)
    # Read temperature sensor data
    temp_raw_val = temp_sensor.read_u16()
    temp_average_val = running_average(temp_raw_val, temp_sample_size, temp_samples)
    current_temp = temp_average_val # (PLACEHOLDER)
    # Wait for a short interval
    time.sleep(0.1)

    is_motion_detected = detect_motion()
    if is_motion_detected:
      is_motion_displayed = True
      detect_time = time.time()
      reset_deactivation_timer()
      are_systems_active = True
      print("main: [SYSTEMS ON] - motion sensed")
    elif is_timer_set:
      update_deactivation_timer()
    # Control LEDs based on system activity
    led_green.value(are_systems_active)
    led_red.value(not are_systems_active)   

    # Control temperature and light based on system activity
    control_temp(are_systems_active)
    control_light(are_systems_active)




    # Uncomment below print statement for debugging purposes
    #print("Light: ", int(current_light), " Temp: ", int(current_temp), " IR: ", int(current_ir))
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Below given code should not be modified (except for the name of ssid and password). 
# Create a network connection
ssid = 'RPI_PICO_AP'       #Set access point name 
password = '12345678'      #Set your access point password
ap = network.WLAN(network.AP_IF)
ap.config(essid=ssid, password=password)
ap.active(True)            #activating

while ap.active() == False:
  pass
print('Connection is successful')
print(ap.ifconfig())

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Below given code defines the web page response. Your html code must be used in this section.
# 
# Define HTTP response
def web_page():
    
# Modify the html portion appropriately.
# Style section below can be changed.
# In the Script section some changes would be needed (mostly updating variable names and adding lines for extra elements). 

    html = """<html>
  <head>
    <script>
      // Script to display current time
      function displayTime() {
        var currentTime = new Date();

        var hours = currentTime.getHours();
        var minutes = currentTime.getMinutes();

        var am_pm = hours < 12 ? "AM" : "PM";

        hours = hours > 12 ? hours - 12 : hours;
        hours = hours == 0 ? 12 : hours;

        minutes = (minutes < 10 ? "0" : "") + minutes;

        var timeString = hours + ":" + minutes + " " + am_pm;

        document.getElementById("time").textContent = timeString;

        setTimeout(displayTime, 1000);
      }
      window.onload = displayTime;

      // Script for button to toggle home/away status
      var isHome = false;
      function toggleStatus() {
        isHome = !isHome;

        var button = document.getElementById("toggleButton");
        if (isHome) {
          button.textContent = "Home";
          button.className = "home";
        } else {
          button.textContent = "Away";
          button.className = "away";
        }
      }
      
      function updateStatus() {
            var xhr = new XMLHttpRequest();
            xhr.onreadystatechange = function() {
                if (xhr.readyState == 4 && xhr.status == 200) {
                    var data = JSON.parse(xhr.responseText);
                  
                    
                    var motion_status_color = data.motion_status === "DETECTED!" ? "#30E513" : "red";
                    document.getElementById("motion_status").innerHTML = data.motion_status;
                    document.getElementById("motion_status").style.color = motion_status_color;


                    
                    var system_status_color = data.system_status === "Home" ? "#30E513" : "red";
                    document.getElementById("system_status").innerHTML = data.system_status;
                    document.getElementById("system_status").style.color = system_status_color;

                    
                    var light_status_color = data.light_status === "ON" ? "#30E513" : "red";
                    document.getElementById("light_status").innerHTML = data.light_status;
                    document.getElementById("light_status").style.color = light_status_color;


                    //var temp_status_color = data.data.temp_status === "On" ? "#30E513" : "red";
                    document.getElementById("temp_status").innerHTML = data.temp_status;
                    //document.getElementById("temp_status").style.color = temp_status_color;

                }
            };
            xhr.open("GET", "/status", true);
            xhr.send();
        }
        setInterval(updateStatus, 1000); // Refresh every 1 second
    </script>
    <style>
      body {
        background-color: #111;
        color: #fff;
      }

      p {
        left: 25px;
        top: 225px;
        font-family: "Verdana";
      }

      h1 {
        font-family: "Verdana";
      }

      h3 {
        font-family: "Verdana";
        top: 100px;
      }

      h4 {
        font-family: "Verdana";
        display: flex;
        align-items: center;
      }

      /* Slider buttons for motion detection and lights */
      .switch {
        position: relative;
        display: inline-block;
        width: 75px;
        height: 34px;
      }

      .switch input {
        opacity: 0;
        width: 0;
        height: 0;
      }

      .slider {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        border-radius: 34px;
        cursor: pointer;
        background-color: #ff0000;
        -webkit-transition: 0.4s;
        transition: 0.4s;
      }

      .slider.wide {
        width: 120px;
        height: 40px;
      }

      .slider.wide:before {
        position: absolute;
        height: 32px;
        width: 32px;
        left: 4px;
        bottom: 4px;
        content: "";
        border-radius: 50%;
        background-color: white;
        -webkit-transition: 0.4s;
        transition: 0.4s;
      }

      .slider:before {
        position: absolute;
        height: 26px;
        width: 26px;
        left: 4px;
        bottom: 4px;
        content: "";
        border-radius: 50%;
        background-color: white;
        -webkit-transition: 0.4s;
        transition: 0.4s;
      }

      .on-text,
      .off-text {
        position: absolute;
        display: block;
        top: 50%;
        transform: translateY(-50%);
        width: 100%;
        text-align: center;
        color: white;
      }

      .on-text {
        right: 12px;
      }

      .off-text {
        left: 12px;
      }

      .wide .on-text {
        right: 14px;
      }

      .wide .off-text {
        left: 14px;
      }

      input:checked + .slider {
        background-color: #00ff00;
      }

      input:checked + .slider:before {
        -webkit-transform: translateX(42px);
        -ms-transform: translateX(42px);
        transform: translateX(42px);
      }

      input:checked + .slider.wide:before {
        -webkit-transform: translateX(80px);
        -ms-transform: translateX(80px);
        transform: translateX(80px);
      }

      input:checked + .slider .off-text {
        display: none;
      }

      input:not(:checked) + .slider .on-text {
        display: none;
      }

      /* Button for Home/Away status */
      #status {
        text-align: left;
      }

      #toggleButton {
        font-size: 20px;
        cursor: pointer;
        color: #fff;
        background-color: #111;
        border: none;
      }

      #toggleButton.home {
        color: #00ff00;
      }

      #toggleButton.away {
        color: #ff0000;
      }
    </style>
  </head>

  <body>
    <h1><i>Smart Home Helper</i></h1>
    <!-- Displays current time -->
    <h3><u>Current time:&nbsp<span id="time"></span></u></h3>
      <h4>
        You are currently:&nbsp <p id="system_status">system_status</p>
      </h4>
    </div>
    <!-- Temperature sensor section -->
    <h4>
      Interior temperature:&nbsp;
      <p id="temp_status">temp_status</p>
    </h4>
    <!-- Light sensor section -->
    <h4>
      Lights:&nbsp;
      <p id="light_status">light_status</p>
    </h4>
    <!-- Motion sensor section -->
    <h4>
      Motion detection:&nbsp;
        <p id="motion_status">motion_status</p>
    </h4>
  </body>
  </html>"""
    return html
# --------------------------------------------------------------------
# This section could be tweaked to return status of multiple sensors or actuators.




# Define a function to get the status of the red LED.
# The function retuns status. 
def get_status():
    global current_temp
    status = {
        "motion_status": get_motion_GUI_status(),
        "system_status": get_system_GUI_status(),
        "light_status":  get_light_GUI_status(),
        "temp_status": str(current_temp),
        # You will add lines of code if status of more sensors is needed.
    }
    return json.dumps(status)
# ------------------------------------------------------------------------

# -------------------------------------------------------------------------
# This portion of the code remains as it is.

# Start the ADC monitoring function in a separate thread
_thread.start_new_thread(update_system, ())
"""
def cleanup():
  global server
  if server:
    server.close()
"""

# This section of the code will have minimum changes. 


# Create a socket server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('', 80))
server.listen(5)
try:
    while True:
        conn, addr = server.accept()
        #print('Got a connection from %s' % str(addr))
        request = conn.recv(1024)
        if request:
          request = str(request)
          #print('Content = %s' % request)

        # this part of the code remains as it is. 
        if request.find("/status") == 6:
          response = get_status()
          conn.send("HTTP/1.1 200 OK\n")
          conn.send("Content-Type: application/json\n")
          conn.send("Connection: close\n\n")
          conn.sendall(response)
        else:
          response = web_page()
          conn.send("HTTP/1.1 200 OK\n")
          conn.send("Content-Type: text/html\n")
          conn.send("Connection: close\n\n")
          conn.sendall(response)
        conn.close()
finally:
    is_system_terminated = True
    print("////////////////////System hard-rebooting, please wait until a connection is restablished before running again...////////////////////")
    time.sleep(0.1)
    machine.reset()

# --------------------------------------------------------------------------

# --------------------------------------------------------------------------

