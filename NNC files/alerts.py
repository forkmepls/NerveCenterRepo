import winsound
import threading
import time
from win10toast import ToastNotifier

class AlertManager:
    def __init__(self):
        self.alerts = {} # Key: Sensor Name, Value: {'min': val, 'max': val, 'sound': bool, 'notify': bool}
        self.toaster = ToastNotifier()
        self.last_alert_time = {} # Key: Sensor Name, Value: timestamp

    def set_alert(self, sensor_name, min_val=None, max_val=None, sound=True, notify=True):
        self.alerts[sensor_name] = {
            'min': min_val,
            'max': max_val,
            'sound': sound,
            'notify': notify
        }

    def remove_alert(self, sensor_name):
        if sensor_name in self.alerts:
            del self.alerts[sensor_name]

    def check_alerts(self, data):
        # Flatten data to find sensors
        sensors = self._flatten_data(data)
        
        for sensor in sensors:
            name = sensor['Name']
            if name in self.alerts:
                val = sensor['Value']
                alert_config = self.alerts[name]
                
                triggered = False
                msg = ""
                
                if alert_config['max'] is not None and val > alert_config['max']:
                    triggered = True
                    msg = f"{name} is High: {val}"
                elif alert_config['min'] is not None and val < alert_config['min']:
                    triggered = True
                    msg = f"{name} is Low: {val}"
                
                if triggered:
                    self._trigger_alert(name, msg, alert_config)

    def _trigger_alert(self, name, msg, config):
        # Debounce alerts (e.g., once every 10 seconds)
        now = time.time()
        if name in self.last_alert_time:
            if now - self.last_alert_time[name] < 10:
                return
        
        self.last_alert_time[name] = now
        
        if config['sound']:
            # Play system sound in a thread to not block
            threading.Thread(target=winsound.MessageBeep, args=(winsound.MB_ICONWARNING,), daemon=True).start()
            
        if config['notify']:
            # Show notification
            threading.Thread(target=self.toaster.show_toast, args=("HWMonitor Alert", msg), kwargs={'duration': 5, 'threaded': True}, daemon=True).start()

    def _flatten_data(self, data):
        sensors = []
        for hw in data:
            sensors.extend(hw['Sensors'])
            # If we had nested subhardware, we'd recurse here
        return sensors
