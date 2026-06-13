

MLworkX Cognitive Analytics Workbench (GigE Infrastructure Edition)
An industrial-grade, multi-threaded computer vision pipeline and edge-analytics console engineered for real-time automated anomaly detection and Operational Technology (OT) hardware integration. Version 1.5 transitions the core imaging architecture from consumer USB multimedia layers to the deterministic GigE Vision protocol, ensuring bit-perfect, uncompressed frame processing directly paired with an optimized YOLOv8 deep learning engine.

The dashboard relies on a highly responsive, high-contrast 4-Quadrant architecture that decouples computational processing (camera polling, AI inference, SQL serialization, and PLC telemetry writes) from the primary Tkinter UI rendering loop to guarantee zero frame dropping and complete fluid control under heavy factory line speeds.

1. Core System Architecture & Features
Deterministic GigE Vision Subsystem: Powered by the native Basler pypylon SDK wrapper to fetch uncompressed BGR8packed frames over UDP network packets. Features physical sensor parameter hard-locking (e.g., fixed microsecond exposure times to eliminate motion blur on fast conveyors).

Real-Time AI Inference Core: Integrated with Ultralytics YOLOv8. Automatically targets native CUDA environments and transitions model tensor weights to half-precision floating-point format (FP16), reducing inference processing overhead to single-digit milliseconds.

Industrial OT Synchronization: Utilizes an asynchronous, low-latency Siemens S7 PLC driver (snap7). Automatically executes microsecond-level binary register writes to a designated memory block (Data Block 10, Byte 0) to actuate physical reject relays instantly upon fault identification.

Enterprise Storage Layer: Multi-threaded database transactional link (mysql-connector-python) that serializes bounding box predictions, object class names, temporal stamps, and model confidence tracking without introducing pipeline stalls.

4-Quadrant Executive Dashboard: Built using custom Tkinter themes with native Matplotlib canvas widgets mapping real-time analytical throughput metrics (items/s) and historical defect distributions directly onto a unified screen.

2. Hardware Topology & Network Specifications
A typical smart-factory cell deployment utilizes the following standard physical layout:

[Target on Conveyor] ---> [Basler GigE Camera (Global Shutter)]
                                       |
                               (Shielded Cat6 Cable)
                                       |
                                       v
[Siemens S7 PLC] <---- TCP/IP ----> [PoE Network Switch] <---- TCP/IP ----> [Industrial GPU Server / IPC]
                                                                             (Running MLworkX Codebase)
Factory Network Allocation Parameters (Defaults)
Industrial PLC IP Target: 192.168.0.10 (Rack 0, Slot 1)

PLC Automation Data Block: DB10 (Offset Byte 0)

0x00 (Bit Low) = Pass/Compliant Component

0x01 (Bit High) = Fail/Defective Component (Triggers Pneumatic Kicker/Reject Arm)

Camera Configuration: Managed via GenICam transport layers. Exposure time hard-locked at 2000.0 µs, digital gain clamped at 0.0 dB to completely negate motion blur and pixel quantization noise.

3. Deployment & Prerequisites
The workbench is optimized for Windows 10/11 Workstations or Industrial Linux Edge Terminals running Python 3.8 to 3.11.

⚠️ Critical Dependencies (Low-Level System Drivers)
Before configuring the Python environment, the underlying native C++ binaries must be compiled and accessible within your system path:

Basler Pylon Camera Software Suite: You must download and install the official Basler Pylon runtime package matching your operating system. This installs the specific low-level GenTL producers needed by pypylon to scan subnets and bind network cameras.

Snap7 Compiled Library Binary: The snap7 library requires its precompiled system driver file (snap7.dll on Windows, or libsnap7.so on Linux architectures). Place this binary directly inside your system PATH directory (e.g., C:\Windows\System32 or /usr/lib).

3.1 Environment Initialization
Isolate the deployment environment using standard virtual environments:

Bash
# Clone the repository assets
git clone (https://github.com/Abdulvaris98/MLWorkX_MachineVision.git)
cd mlworkx-workbench

# Instantiate virtual environment structure
python -m venv venv

# Activate the virtual context
# On Windows Workstations:
.\venv\Scripts\activate
# On Linux Terminal Nodes:
source venv/bin/activate
3.2 Library Installation
Install all upstream package dependencies through the Python pip module manager:

Bash
pip install opencv-python ultralytics python-snap7 mysql-connector-python matplotlib pillow torch torchvision pypylon
4. Database Schema Configuration
Ensure a relational MySQL server instance is online and running within the network grid. Execute the database script below to construct the default system architecture:

SQL
CREATE DATABASE IF NOT EXISTS MLworkX_DB;
USE MLworkX_DB;

CREATE TABLE IF NOT EXISTS Inspection_Logs (
    part_id INT AUTO_INCREMENT PRIMARY KEY,
    log_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    object_class VARCHAR(50) NOT NULL,
    confidence_score FLOAT NOT NULL,
    result_status VARCHAR(10) NOT NULL,
    image_path VARCHAR(255) DEFAULT ''
);
Note: If your local database development node uses custom administrative access parameters, modify the instantiation variables within the DatabaseManager call inside the python file accordingly (host, user, password).

5. Execution and Operational Manual
To initialize the cognitive system console interface, run the main entry point file through your activated command line shell terminal:

Bash
python main.py
Interface Control Protocol
The console relies on high-contrast, touch-friendly graphical controls designed for edge station operators:

▶ START ENGINE: Fires the background threads, hooks into the primary network GigE Vision interface device stream, clears the system caching registers, and initiates real-time YOLOv8 inferencing loops.

■ HALT LINE: Instantly pauses frame processing, disengages live background evaluation threads, safely sends a logical low state to the connected PLC register to avoid hardware locking, and appends a critical emergency stop line directly into the telemetry logging window.

Visual Color-Coded Feeds: * Quadrant 1: Continuously outputs the auto-scaled computer vision feed overlaying the real-time AI bounding box results.

Quadrant 2: Displays chronological relational records mapped directly to the active MySQL server database ledger.

Quadrant 3: An active text console logging hardware status anomalies. Uses clear high-contrast warning indications (Crimson for critical errors/halts, Orange for product failures).

Quadrant 4: Automatically updates operational trend graphics, plotting instantaneous items-per-second processing performance metrics next to historical pass/fail distribution matrices.

6. Codebase Architecture Map
DatabaseManager: Encapsulates connection protocols and manages multi-threaded, asynchronous serialization queries to the relational database.

PLCInterface: Wraps the native client sockets of the Snap7 network framework. Handles discrete byte manipulations and asynchronous data transmission directly to the Siemens CPU.

InferenceEngine: Loads the neural network architectures, checks system resources for CUDA capabilities, maps tensor layers to FP16 format, and performs algorithmic smoothing pre-processing via low-pass Gaussian Blurs.

VisionController: Handles UI geometry initialization, styles treeviews, runs asynchronous loops inside isolated secondary daemon threads, and applies live plot updates on the Matplotlib canvas layers.

7. License
This project documentation and the underlying industrial software framework code are distributed under the open-source MIT License. Operations facilities, manufacturing networks, and automation systems integrators are completely free to modify, duplicate, fork, or combine these assets inside commercial or private production floor ecosystems.
