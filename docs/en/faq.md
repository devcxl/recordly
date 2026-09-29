# Frequently Asked Questions (FAQ)

Answers to common questions from new Recordly users. If your question is not listed here, feel free to use the menu **Help -> Feedback** or open an issue on [GitHub Issues](https://github.com/devcxl/recordly/issues).

---

### Is Recordly really free? Are there any watermarks or recording limits?
**100% free, no watermarks, and no duration limits.**  
Recordly is open-source software licensed under the MIT license. Whether you are using it for personal study, company presentations, or commercial course creation, you may use it completely free of charge. Recordly will never add watermarks to your exported videos, and there is no limit on recording duration (constrained only by your local disk space).

---

### Where are recordings saved? Are they uploaded to any cloud service?
**Everything is saved strictly on your local computer; nothing is uploaded.**  
Projects are stored in your home directory at `~/Recordly/projects/` (or `C:\Users\Username\Recordly\projects\` on Windows). The software operates completely offline without user accounts, keeping proprietary code and confidential presentations safe.

---

### If I make a verbal slip during recording, how do I re-record just that line?
**Use the in-place Voiceover Re-recording feature on the microphone track:**
1. After recording, locate the green "Microphone" track in the timeline editor;
2. Right-click the audio clip where you made the verbal slip;
3. Select **"Re-record Audio"** from the context menu;
4. Click "Start Recording" in the dialog, speak the corrected sentence, and click "Stop Recording";
5. The new take replaces the selected segment, and the original audio is automatically muted. If you are not satisfied, press `Ctrl+Z` to undo and try again.

---

### Where did the window go after clicking Start Recording? How do I stop?
**The window automatically minimizes to your system tray to avoid blocking your screen:**
- **Windows / Linux**: Look for the red Recordly circular icon in your taskbar system tray (bottom-right corner);
- **macOS**: Look in the top-right menu bar;
- **Right-click the tray icon** and select **"Stop Recording"**. The editor will automatically open with your recorded footage.

---

### Why doesn't Recordly exit when I close the main window?
**This prevents accidental interruptions during an active recording or editing session.**  
Clicking the close button simply tucks Recordly into the system tray. To terminate the application entirely, right-click the system tray icon and select **"Quit"**.

---

### How can I reduce the file size of exported MP4 videos or GIFs?
- **MP4 Videos**:
  - In the export dialog, switch Quality from "Original (100%)" to "Good (75%)". Visual fidelity remains virtually indistinguishable while file size drops by up to 60%.
  - For slides and web demos, 1080p or 720p resolution is generally more than sufficient.
- **GIFs**:
  - The GIF format is sensitive to palette size and frame count. Set your GIF frame rate to 10 or 15 FPS, and crop the canvas to remove irrelevant background space.

---

### Can I record only a portion of the screen or a single window?
The recorder currently captures your primary display in its entirety to ensure maximum fidelity.  
To isolate a specific window or area, enter the editor after recording and use **Crop Mode** in the toolbar or choose **Center Crop** in the export dialog.

---

### Why is "GPU Hardware Encoding (NVENC)" grayed out during export?
This option requires an NVIDIA GPU with NVENC encoder support. If your machine runs on an AMD graphics card, Intel integrated graphics, or an Apple Mac, this option is disabled automatically and Recordly uses high-quality CPU encoding instead.

---

### What happens if Recordly or my computer crashes during recording?
**Your footage can be recovered.**  
Recordly writes frames to disk in real-time. If power is lost or an unexpected shutdown occurs, relaunching Recordly will automatically detect the interrupted project and display a prompt stating that footage was preserved. You can reopen the project from the home gallery and resume editing.

---

### How do I report bugs or suggest new features?
You can submit feedback directly to our GitHub repository:
- Select **Help -> Feedback** in the app menu, or visit [GitHub Issues](https://github.com/devcxl/recordly/issues).
- When reporting issues, please share your operating system version, reproduction steps, and the `project.json` file from your project folder.
