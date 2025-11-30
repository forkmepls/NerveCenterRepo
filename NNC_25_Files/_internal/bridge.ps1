# Path to DLLs
# In PyInstaller bundle, files are in the same directory as the script
$DllPath = Join-Path $PSScriptRoot "LibreHardwareMonitorLib.dll"
$HidPath = Join-Path $PSScriptRoot "HidSharp.dll"

# Fallback to lib folder if not found (dev environment)
if (-not (Test-Path $DllPath)) {
    $DllPath = Join-Path $PSScriptRoot "lib\LibreHardwareMonitorLib.dll"
    $HidPath = Join-Path $PSScriptRoot "lib\HidSharp.dll"
}

# Load DLLs
try {
    # Load HidSharp first as it might be a dependency
    if (Test-Path $HidPath) {
        [Reflection.Assembly]::LoadFile($HidPath) | Out-Null
    }
    [Reflection.Assembly]::LoadFile($DllPath) | Out-Null
}
catch {
    Write-Error "Failed to load DLLs. Checked '$PSScriptRoot' and '$PSScriptRoot\lib'. Error: $_"
    exit 1
}

# Create Computer Object
$Computer = New-Object LibreHardwareMonitor.Hardware.Computer
$Computer.IsCpuEnabled = $true
$Computer.IsGpuEnabled = $true
$Computer.IsMemoryEnabled = $true
$Computer.IsMotherboardEnabled = $true
$Computer.IsControllerEnabled = $true
$Computer.IsNetworkEnabled = $true
$Computer.IsStorageEnabled = $true

try {
    $Computer.Open()
}
catch {
    Write-Error "Failed to open Computer object. Run as Administrator."
    exit 1
}

# Update and Collect Data
# Run in a loop to stream data continuously
while ($true) {
    try {
        $Output = @()

        foreach ($Hardware in $Computer.Hardware) {
            $Hardware.Update()
            
            $HwData = @{
                Name    = $Hardware.Name
                Type    = "$($Hardware.HardwareType)"
                Sensors = @()
            }

            foreach ($Sensor in $Hardware.Sensors) {
                $HwData.Sensors += @{
                    Name  = $Sensor.Name
                    Type  = "$($Sensor.SensorType)"
                    Value = $Sensor.Value
                    Min   = $Sensor.Min
                    Max   = $Sensor.Max
                }
            }

            # SubHardware (e.g. Cores)
            foreach ($SubHardware in $Hardware.SubHardware) {
                $SubHardware.Update()
                foreach ($Sensor in $SubHardware.Sensors) {
                    $HwData.Sensors += @{
                        Name  = "$($SubHardware.Name) - $($Sensor.Name)"
                        Type  = "$($Sensor.SensorType)"
                        Value = $Sensor.Value
                        Min   = $Sensor.Min
                        Max   = $Sensor.Max
                    }
                }
            }

            $Output += $HwData
        }

        $json = $Output | ConvertTo-Json -Depth 5 -Compress
        [Console]::WriteLine($json)
        [Console]::Out.Flush()
        
        # Sleep to reduce CPU usage
        Start-Sleep -Seconds 1
    }
    catch {
        [Console]::Error.WriteLine("Error getting data: $_")
        [Console]::Error.Flush()
        Start-Sleep -Seconds 1
    }
}

$Computer.Close()
