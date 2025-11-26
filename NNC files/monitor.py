import subprocess
import os
import sys
import logging
import json
import threading
import time

# Setup logging
log_file = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__), 'hwmonitor_debug.log')
logging.basicConfig(filename=log_file, level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

class HardwareMonitor:
    def __init__(self):
        self.process = None
        self.current_data = []
        self.running = False
        self.thread = None
        self.bus_correction_factor = None
        
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
            
        self.script_path = os.path.join(base_path, 'bridge.ps1')
        
        if not os.path.exists(self.script_path):
            # Fallback
            self.script_path = os.path.join(base_path, 'hwmonitor-clone', 'bridge.ps1')
            
        logging.info(f"Bridge script path: {self.script_path}")
        self.start_process()

    def start_process(self):
        try:
            # Start persistent PowerShell process
            # Use CREATE_NO_WINDOW to hide the console window
            creationflags = subprocess.CREATE_NO_WINDOW
            
            self.process = subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Redirect stderr to stdout to capture errors
                text=True,
                bufsize=1, # Line buffered
                creationflags=creationflags
            )
            logging.info("PowerShell process started")
            
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            
        except Exception as e:
            logging.error(f"Failed to start PowerShell process: {e}")
            self.process = None

    def _read_loop(self):
        while self.running and self.process:
            try:
                line = self.process.stdout.readline()
                if not line:
                    logging.info("Process output ended (EOF)")
                    break
                
                try:
                    data = json.loads(line)
                    self.current_data = self._sanitize_data(data)
                except json.JSONDecodeError:
                    # Only log if it's not a known debug message (optional)
                    if line.strip():
                        logging.warning(f"Failed to decode JSON: {line.strip()}")
                    
            except Exception as e:
                logging.error(f"Error reading from process: {e}")
                break
        
        logging.info("Read loop ended")

    def get_data(self):
        # Return the latest cached data
        return self.current_data

    def _sanitize_data(self, data):
        """
        Fixes known issues with LibreHardwareMonitor data.
        - Corrects inflated CPU clock speeds caused by incorrect Bus Speed readings (e.g. Ryzen 9600X reporting 486MHz bus).
        - Uses a dynamic correction factor derived from the first reading to preserve sensor fluctuations.
        """
        if not data:
            return []
            
        for hw in data:
            if hw.get('Type') == 'Cpu':
                # Find Bus Speed sensor
                bus_speed_sensor = None
                for sensor in hw.get('Sensors', []):
                    if sensor.get('Name') == 'Bus Speed' and sensor.get('Type') == 'Clock':
                        bus_speed_sensor = sensor
                        break
                
                # Check if Bus Speed is unreasonable (e.g. > 150 MHz)
                # Standard is 100 MHz (99.8 - 100.2)
                if bus_speed_sensor and bus_speed_sensor.get('Value') and bus_speed_sensor['Value'] > 150:
                    
                    # Calculate correction factor if not already set
                    # We assume the first bad reading is "representative" of the error scale
                    # and use it to normalize to ~100 MHz.
                    if self.bus_correction_factor is None:
                        self.bus_correction_factor = bus_speed_sensor['Value'] / 100.0
                        logging.info(f"Detected unreasonable Bus Speed ({bus_speed_sensor['Value']} MHz). Applied correction factor: {self.bus_correction_factor}")
                    
                    # Apply correction
                    # Fix Bus Speed
                    bus_speed_sensor['Value'] /= self.bus_correction_factor
                    if bus_speed_sensor.get('Min'): bus_speed_sensor['Min'] /= self.bus_correction_factor
                    if bus_speed_sensor.get('Max'): bus_speed_sensor['Max'] /= self.bus_correction_factor
                    
                    # Fix all other Clock sensors in this CPU
                    for sensor in hw.get('Sensors', []):
                        if sensor.get('Type') == 'Clock' and sensor.get('Name') != 'Bus Speed':
                            if sensor.get('Value'): sensor['Value'] /= self.bus_correction_factor
                            if sensor.get('Min'): sensor['Min'] /= self.bus_correction_factor
                            if sensor.get('Max'): sensor['Max'] /= self.bus_correction_factor

        return data

    def close(self):
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1)
            except:
                self.process.kill()
                self.process.wait()
            
            # Give OS a moment to release file locks on DLLs
            time.sleep(0.5)
            self.process = None

if __name__ == "__main__":
    monitor = HardwareMonitor()
    print("Fetching data...")
    time.sleep(2)
    data = monitor.get_data()
    print(json.dumps(data, indent=2))
    monitor.close()
