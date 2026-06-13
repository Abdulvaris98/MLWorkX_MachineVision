import cv2
import torch
import snap7
import threading
import datetime
import mysql.connector
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk  # Used for the modern database table grid
from PIL import Image, ImageTk
from ultralytics import YOLO

# Native SDK wrapper for industrial GigE Vision Cameras
from pypylon import pylon  

# Matplotlib integration for live charts
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


BG_MAIN = "#0D0B14"         # Deepest obsidian violet for outer frame
BG_PANEL = "#161224"        # Dark violet for quadrant panels
BG_INPUT = "#1E1A30"        # Contrast color for console/tables
ACCENT_VIOLET = "#7B2CBF"   # Electric violet for primary headers and borders
ACCENT_GREEN = "#00F5D4"    # Neon teal/light green for active data and status
TEXT_MAIN = "#E0AAFF"       # Lavender off-white for high readability
TEXT_MUTED = "#7D7495"      # Muted gray-violet for gridlines/secondary labels
BTN_DANGER = "#FF5A5F"      # Soft bright crimson for stops and errors

FONT_TITLE = ("Segoe UI", 12, "bold")
FONT_DATA = ("Segoe UI", 10)
FONT_LOG = ("Consolas", 9)

# ---------------------------------------------------------
# 1. Database Manager
# ---------------------------------------------------------
class DatabaseManager:
    def __init__(self, host="localhost", user="root", password="password", database="MLworkX_DB"):
        try:
            self.db = mysql.connector.connect(
                host=host, user=user, password=password, database=database
            )
            self.cursor = self.db.cursor()
            print("Database connected successfully.")
        except mysql.connector.Error as err:
            print(f"Error: {err}")
            self.db = None

    def execute_insert(self, object_class, confidence, status, image_path=""):
        if self.db:
            try:
                query = """INSERT INTO Inspection_Logs 
                           (object_class, confidence_score, result_status, image_path) 
                           VALUES (%s, %s, %s, %s)"""
                values = (object_class, float(confidence), status, image_path)
                self.cursor.execute(query, values)
                self.db.commit()
            except Exception as e:
                print(f"Database insertion failed: {e}")

# ---------------------------------------------------------
# 2. PLC Interface (Siemens S7)
# ---------------------------------------------------------
class PLCInterface:
    def __init__(self, ip_address='192.168.0.10', rack=0, slot=1):
        self.client = snap7.client.Client()
        try:
            self.client.connect(ip_address, rack, slot)
            self.connected = True
        except Exception as e:
            print(f"PLC Connection Failed: {e}")
            self.connected = False

    def write_trigger(self, status):
        if self.connected:
            try:
                data = bytearray([status])
                self.client.db_write(10, 0, data)
            except Exception as e:
                print(f"Failed to write to PLC: {e}")

# ---------------------------------------------------------
# 3. Inference Engine
# ---------------------------------------------------------
class InferenceEngine:
    def __init__(self, model_path='yolov8n.pt'):
        self.model = YOLO(model_path)
        if torch.cuda.is_available():
            self.model.model.half()
            
    def preprocess(self, frame):
        return cv2.GaussianBlur(frame, (5, 5), 0)

    def infer(self, frame):
        processed_frame = self.preprocess(frame)
        return self.model(processed_frame, conf=0.75, verbose=False)

# ---------------------------------------------------------
# 4. Vision Controller (4-Quadrant Split Dashboard)
# ---------------------------------------------------------
class VisionController:
    def __init__(self, root):
        self.root = root
        self.root.title("MLworkX Integrated GigE Inspection Console")
        self.root.geometry("1440x850")
        self.root.configure(bg=BG_MAIN)

        # Subsystems
        self.db_manager = DatabaseManager()
        self.plc_interface = PLCInterface()
        self.inference_engine = InferenceEngine()
        
        # Telemetry Data Storage
        self.total_count = 0
        self.passed_count = 0
        self.failed_count = 0
        self.history_timestamps = []
        self.history_yields = []

        # Industrial GigE Camera Initialization Subsystem
        self.camera = None
        self.converter = None
        self.init_gige_camera()
        
        self.is_running = False

        # Apply Modern Styling to ttk Treeview components (Database Tables)
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview", background=BG_INPUT, fieldbackground=BG_INPUT, foreground=TEXT_MAIN, rowheight=24, borderwidth=0, font=FONT_DATA)
        self.style.configure("Treeview.Heading", background=BG_PANEL, foreground=ACCENT_GREEN, borderwidth=1, font=FONT_TITLE)
        self.style.map("Treeview", background=[('selected', ACCENT_VIOLET)], foreground=[('selected', '#FFFFFF')])

        self.setup_4_quadrant_ui()

    def init_gige_camera(self):
        """Discovers, initializes, and locks operational parameters of the network GigE camera."""
        try:
            tl_factory = pylon.TlFactory.GetInstance()
            devices = tl_factory.EnumerateDevices()
            
            if not devices:
                print("GigE Hardware Error: No GenICam compliance devices discovered on local subnets.")
                self.camera = None
                return

            # Instantiate and open the first identified network camera link
            self.camera = pylon.InstantCamera(tl_factory.CreateFirstDevice(devices[0]))
            self.camera.Open()
            
            # --- Hard-locking Physical Sensors Grabbing Attributes ---
            self.camera.ExposureAuto.SetValue("Off")
            self.camera.ExposureTime.SetValue(2000.0)  # Microseconds - Low setting freezes conveyor motion blur
            self.camera.GainAuto.SetValue("Off")
            self.camera.Gain.SetValue(0.0)             # Zero decibel digital gain minimizes noise artifacts
            
            # Use specific industrial acquisition strategy tracking latest bit-perfect frames
            self.camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            
            # Optimize real-time array conversion matrix backends
            self.converter = pylon.ImageFormatConverter()
            self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            print(f"GigE Subsystem Operational: Connected to model [{self.camera.GetDeviceInfo().GetModelName()}]")
            
        except Exception as e:
            print(f"Critical error mapping industrial GigE camera framework: {e}")
            self.camera = None

    def setup_4_quadrant_ui(self):
        # ---------------------------------------------------------
        # TOP HEADER BANNER CONTROL SECTION
        # ---------------------------------------------------------
        header_frame = tk.Frame(self.root, bg=BG_PANEL, height=55, highlightthickness=1, highlightbackground=ACCENT_VIOLET)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="MLworkX COGNITIVE ANALYTICS WORKBENCH (GigE INFRASTRUCTURE)", font=("Segoe UI", 13, "bold"), bg=BG_PANEL, fg=TEXT_MAIN).pack(side=tk.LEFT, padx=15)
        
        # Action Buttons
        self.start_btn = tk.Button(header_frame, text="▶ START ENGINE", font=FONT_TITLE, bg=ACCENT_GREEN, fg=BG_MAIN, relief=tk.FLAT, command=self.start_inspection, cursor="hand2", padx=10)
        self.start_btn.pack(side=tk.LEFT, padx=20, pady=10)

        self.stop_btn = tk.Button(header_frame, text="■ HALT LINE", font=FONT_TITLE, bg=BTN_DANGER, fg="#FFFFFF", relief=tk.FLAT, command=self.stop_inspection, cursor="hand2", padx=10)
        self.stop_btn.pack(side=tk.LEFT, padx=5, pady=10)

        # Status Indicators
        camera_online = self.camera is not None and self.camera.IsGrabbing()
        self.lbl_cam_stat = tk.Label(header_frame, text="● GigE CAM: ONLINE" if camera_online else "● GigE CAM: OFFLINE", font=FONT_TITLE, fg=ACCENT_GREEN if camera_online else BTN_DANGER, bg=BG_PANEL)
        self.lbl_cam_stat.pack(side=tk.RIGHT, padx=15)

        self.lbl_plc_stat = tk.Label(header_frame, text="● PLC: ONLINE" if self.plc_interface.connected else "● PLC: OFFLINE", font=FONT_TITLE, fg=ACCENT_GREEN if self.plc_interface.connected else BTN_DANGER, bg=BG_PANEL)
        self.lbl_plc_stat.pack(side=tk.RIGHT, padx=15)
        
        self.lbl_db_stat = tk.Label(header_frame, text="● DATABASE: ONLINE" if self.db_manager.db else "● DATABASE: OFFLINE", font=FONT_TITLE, fg=ACCENT_GREEN if self.db_manager.db else BTN_DANGER, bg=BG_PANEL)
        self.lbl_db_stat.pack(side=tk.RIGHT, padx=15)

        # ---------------------------------------------------------
        # MAIN 4-QUADRANT GRID AREA
        # ---------------------------------------------------------
        grid_container = tk.Frame(self.root, bg=BG_MAIN)
        grid_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        grid_container.rowconfigure(0, weight=1)
        grid_container.rowconfigure(1, weight=1)
        grid_container.columnconfigure(0, weight=1)
        grid_container.columnconfigure(1, weight=1)

        # --- QUADRANT 1 (Top-Left): Real-Time Vision Feed ---
        q1_frame = tk.LabelFrame(grid_container, text="[QUADRANT 01] - REAL-TIME VISION INFERENCE FEED", font=FONT_TITLE, bg=BG_PANEL, fg=ACCENT_VIOLET, labelanchor="nw", highlightthickness=1, highlightbackground="#251D3A")
        q1_frame.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        self.video_label = tk.Label(q1_frame, bg="#05040A")
        self.video_label.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # --- QUADRANT 2 (Top-Right): Running SQL Telemetry Table ---
        q2_frame = tk.LabelFrame(grid_container, text="[QUADRANT 02] - RUNNING DB TELEMETRY LOG (SQL ENGINE)", font=FONT_TITLE, bg=BG_PANEL, fg=ACCENT_VIOLET, labelanchor="nw", highlightthickness=1, highlightbackground="#251D3A")
        q2_frame.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        
        scroll_y = tk.Scrollbar(q2_frame, orient=tk.VERTICAL)
        scroll_x = tk.Scrollbar(q2_frame, orient=tk.HORIZONTAL)
        
        self.tree = ttk.Treeview(q2_frame, columns=("id", "timestamp", "class", "confidence", "status"), show="headings", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.tree.heading("id", text="part_id")
        self.tree.heading("timestamp", text="log_timestamp")
        self.tree.heading("class", text="object_class")
        self.tree.heading("confidence", text="confidence_score")
        self.tree.heading("status", text="result_status")
        
        self.tree.column("id", width=60, anchor="center")
        self.tree.column("timestamp", width=140, anchor="center")
        self.tree.column("class", width=100, anchor="center")
        self.tree.column("confidence", width=110, anchor="center")
        self.tree.column("status", width=90, anchor="center")

        # --- QUADRANT 3 (Bottom-Left): Text Terminal System State Logs ---
        q3_frame = tk.LabelFrame(grid_container, text="[QUADRANT 03] - ACTIVE TELEMETRY & EXCEPTION LOGS", font=FONT_TITLE, bg=BG_PANEL, fg=ACCENT_VIOLET, labelanchor="nw", highlightthickness=1, highlightbackground="#251D3A")
        q3_frame.grid(row=1, column=0, padx=6, pady=6, sticky="nsew")
        
        self.log_text = tk.Text(q3_frame, bg=BG_INPUT, fg=TEXT_MAIN, font=FONT_LOG, relief=tk.FLAT, padx=8, pady=8, selectbackground=ACCENT_VIOLET)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        
        self.log_defect("Starting mlworkx database and communication services...", type="SYS")
        self.log_defect("GigE Camera stack interface mapped inside pipeline framework.", type="SYS")
        self.log_defect("Client [Operator_Station_v1.5_GigE] fully connected.", type="SYS")

        # --- QUADRANT 4 (Bottom-Right): Embedded Analytics Charts ---
        q4_frame = tk.LabelFrame(grid_container, text="[QUADRANT 04] - PRODUCTION METRICS & YIELD ANOMALIES", font=FONT_TITLE, bg=BG_PANEL, fg=ACCENT_VIOLET, labelanchor="nw", highlightthickness=1, highlightbackground="#251D3A")
        q4_frame.grid(row=1, column=1, padx=6, pady=6, sticky="nsew")
        
        self.chart_container = tk.Frame(q4_frame, bg=BG_MAIN)
        self.chart_container.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.setup_dashboard_plots()

    def setup_dashboard_plots(self):
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(7, 2.5), dpi=100)
        self.fig.patch.set_facecolor(BG_PANEL)
        
        for ax in [self.ax1, self.ax2]:
            ax.set_facecolor(BG_MAIN)
            ax.grid(True, color="#251D3A", linestyle="--", linewidth=0.5)
            for spine in ax.spines.values():
                spine.set_color("#3C304F")
            ax.tick_params(colors=TEXT_MUTED, labelsize=7)

        self.ax1.set_title("Line Throughput Analytics (items/s)", color=TEXT_MAIN, fontname="Segoe UI", fontsize=9, weight="bold")
        self.ax2.set_title("Defect Frequency Profile over Time", color=TEXT_MAIN, fontname="Segoe UI", fontsize=9, weight="bold")
        
        self.chart_canvas = FigureCanvasTkAgg(self.fig, master=self.chart_container)
        self.chart_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def start_inspection(self):
        if not self.is_running:
            if self.camera is None or not self.camera.IsGrabbing():
                # Attempt hot-reconnection to the physical interface before booting
                self.init_gige_camera()
                if self.camera is None:
                    messagebox.showerror("Hardware Connection Error", "Execution halted: Unable to claim industrial GigE camera interface.")
                    return

            self.is_running = True
            self.start_btn.config(bg="#251D3A", fg=TEXT_MUTED, text="⚙ ENGINE ACTIVE")
            
            # Refresh UI Indicators
            self.lbl_cam_stat.config(text="● GigE CAM: ONLINE", fg=ACCENT_GREEN)
            
            self.inspection_thread = threading.Thread(target=self.run_pipeline)
            self.inspection_thread.daemon = True
            self.inspection_thread.start()

    def stop_inspection(self):
        self.is_running = False
        self.start_btn.config(bg=ACCENT_GREEN, fg=BG_MAIN, text="▶ START ENGINE")
        self.log_defect("CRITICAL STOP: Inspection process paused by operator command.", type="ERR")

    def log_defect(self, msg, type="INFO"):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        prefix = f"[{timestamp}] [{type}] "
        self.log_text.insert(tk.END, f"{prefix}{msg}\n")
        
        if type == "ERR":
            self.log_text.tag_add("danger", "end - 2 lines", "end")
            self.log_text.tag_config("danger", foreground=BTN_DANGER)
        elif type == "FAIL":
            self.log_text.tag_add("reject", "end - 2 lines", "end")
            self.log_text.tag_config("reject", foreground="#FFA500")
        
        self.log_text.see(tk.END)

    def update_split_screen_data(self, obj_class, conf, status):
        self.total_count += 1
        if status == "FAIL":
            self.failed_count += 1
        else:
            self.passed_count += 1
            
        now_time = datetime.datetime.now().strftime('%H:%M:%S')
        
        # Insert directly into Treeview Table
        row_id = 1000 + self.total_count
        self.tree.insert("", 0, values=(f"{row_id}", f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f"{obj_class}", f"{conf:.4f}", f"{status}"))
        
        if len(self.tree.get_children()) > 40:
            self.tree.delete(self.tree.get_children()[-1])

        # Update History Array for Plot Repainting
        current_yield = (self.passed_count / self.total_count) * 100
        self.history_timestamps.append(now_time)
        self.history_yields.append(current_yield)
        if len(self.history_timestamps) > 12:
            self.history_timestamps.pop(0)
            self.history_yields.pop(0)

        self.ax1.clear()
        self.ax2.clear()
        
        for ax in [self.ax1, self.ax2]:
            ax.grid(True, color="#251D3A", linestyle="--", linewidth=0.5)
            ax.tick_params(colors=TEXT_MUTED, labelsize=7)
            
        self.ax1.set_title("Line Throughput Analytics (items/s)", color=TEXT_MAIN, fontname="Segoe UI", fontsize=9, weight="bold")
        self.ax2.set_title("Defect Frequency Profile over Time", color=TEXT_MAIN, fontname="Segoe UI", fontsize=9, weight="bold")
        
        self.ax1.plot(self.history_timestamps, self.history_yields, color=ACCENT_GREEN, marker='o', linewidth=1.5, markersize=3)
        self.ax1.set_ylim(-5, 105)
        
        categories = ['Passed', 'Failed']
        quantities = [self.passed_count, self.failed_count]
        self.ax2.bar(categories, quantities, color=[ACCENT_VIOLET, BTN_DANGER], width=0.4)
        
        self.fig.autofmt_xdate(bottom=0.25, rotation=25, ha='right')
        self.chart_canvas.draw()

    def run_pipeline(self):
        """Asynchronous execution context parsing bit-perfect frames directly out of the GigE buffer."""
        while self.is_running and self.camera is not None and self.camera.IsGrabbing():
            try:
                # Retrieve uncompressed image packets directly out of network interface buffers
                # Throws clear runtime timeout exception if communication hardware cuts out
                grab_result = self.camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                
                if grab_result.GrabSucceeded():
                    # Parse image metadata bytes and unpack into standard OpenCV ndarray arrays
                    converted_image = self.converter.Convert(grab_result)
                    frame = converted_image.GetArray()
                    grab_result.Release()  # Release frame pointer buffer instantly back to GenICam layer
                else:
                    grab_result.Release()
                    continue

                # Run frame through YOLOv8 Inference Pipeline
                results = self.inference_engine.infer(frame)
                annotated_frame = results[0].plot()
                defect_detected = False

                for r in results:
                    if len(r.boxes) > 0 and int(r.boxes.cls[0]) == 1: 
                        defect_detected = True
                        confidence = float(r.boxes.conf[0])
                        class_name = results[0].names[int(r.boxes.cls[0])]
                        
                        self.plc_interface.write_trigger(1)
                        self.db_manager.execute_insert(class_name, confidence, "FAIL")
                        
                        self.root.after(0, self.log_defect, f"REJECT EVENT LOGGED: {class_name.upper()} detected.", "FAIL")
                        self.root.after(0, self.update_split_screen_data, class_name, confidence, "FAIL")
                        break 

                if not defect_detected:
                    self.plc_interface.write_trigger(0)
                    self.root.after(0, self.update_split_screen_data, "Normal_Part", 0.9842, "PASS")

                self.update_video_feed(annotated_frame)
                
            except Exception as network_exc:
                self.root.after(0, self.log_defect, f"NETWORK GRAB FAULT: Intermittent packet drop or camera link lost. {network_exc}", "ERR")
                self.is_running = False
                self.root.after(0, lambda: self.start_btn.config(bg=ACCENT_GREEN, fg=BG_MAIN, text="▶ START ENGINE"))
                self.root.after(0, lambda: self.lbl_cam_stat.config(text="● GigE CAM: OFFLINE", fg=BTN_DANGER))
                break

    def update_video_feed(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb_frame)
        img = img.resize((680, 360), Image.Resampling.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.imgtk = imgtk
        self.video_label.configure(image=imgtk)

    def on_closing(self):
        self.is_running = False
        
        # Safe breakdown of industrial camera structures
        if self.camera is not None:
            try:
                if self.camera.IsGrabbing():
                    self.camera.StopGrabbing()
                self.camera.Close()
            except Exception as e:
                print(f"Exception cleaning GigE structures: {e}")
                
        if self.plc_interface.connected:
            self.plc_interface.client.disconnect()
        if self.db_manager.db:
            self.db_manager.db.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = VisionController(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()