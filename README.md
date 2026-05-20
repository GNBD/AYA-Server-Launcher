# Server LAUNCHER

> **A simple and lightweight tool designed to make your Minecraft server management easier.**
> (It might not be the "world's best," but it's definitely useful!)

[AIO](https://github.com/GNBD/NENE-Helper/releases/tag/nenemanager)

## 🚀 Project Overview

**server launcher** is a tool designed to help you set up and manage a Minecraft Java Edition server quickly and easily.
It automatically fetches the latest server core through the PaperMC API (or custom API), and provides a user-friendly Web GUI built with Python and HTML/CSS.

### 🚧 Work In Progress
> **This project is still under active development.**
> If you encounter any bugs or have suggestions, please feel free to open an issue on the **[GitHub Issues]** tab at any time. Your feedback makes this tool better!

![스크린샷 2025-11-23 193858](https://github.com/user-attachments/assets/7ffcff58-54e5-4114-921c-e6a18e035c66)

👉 **Official Website:** [https://nenehelper.netlify.app/](https://nenehelper.netlify.app/)

---

## ✨ Key Features

### ⚡ **Server Management**
* **One-click Creation:** Download the latest PaperMC core and set up a server in seconds.
* **Easy Java Switching:** Automatically detects all installed Java versions on your PC. You can switch between versions (e.g., Java 8 ↔ Java 21) with a single click.
* **Per-Server Settings:** Apply different Java versions to different servers effortlessly.
* **Manual Path Support:** You can also manually specify a custom Java path if needed.
* **Custom API Support:** You can change the server core download URL (API) if needed.

### 📊 **Dashboard & Monitoring**
* **Real-time Monitoring:** Check server status, CPU, and RAM usage at a glance.
* **Web-based UI:** Clean and responsive interface using HTML/CSS.

### 🛠 **Essential Admin Tools**
* **One-Click Commands:** Execute essential commands instantly without typing:
    * 🌦️ **Weather & Time:** Clear weather, Day/Night toggle.
    * ⚙️ **Game Settings:** Change Difficulty, Gamemode.
    * 📢 **Broadcasting:** Simple Announcement feature / Whisper.
    * 🛡️ **Player Management:** OP/Deop, Kick, Ban users easily.

### 🧩 **Add-ons & Localization**
* **Plugin Manager:** Easily manage your server plugins (Enable/Disable/Delete).

---

## 🛠️ Tech Stack

* **Backend:** Python (Main logic), Eel (Python ↔ HTML bridge)
* **Frontend:** HTML, CSS, JavaScript (User Interface)

---

## 📦 Libraries & Resources

Special thanks to the open-source libraries and services that made this project possible:

### **Backend (Python)**
* **[Eel](https://github.com/python-eel/Eel):** A little library for making simple Electron-like HTML/JS GUI apps.
* **[psutil](https://github.com/giampaolo/psutil):** Cross-platform library for retrieving information on running processes and system utilization (CPU/RAM).
* **[requests](https://requests.readthedocs.io/):** A simple, yet elegant HTTP library for API communication & file downloads.

### **Frontend (Web)**
* **[Pretendard](https://github.com/orioncactus/pretendard):** A multi-platform system UI font that helps the interface look clean and modern (served via jsDelivr).
* **[Phosphor Icons](https://phosphoricons.com/):** A flexible icon family for interfaces, diagrams, presentations, and more (served via unpkg).

### **APIs & Services**
* **[PaperMC API](https://papermc.io/):** Used to fetch the latest Minecraft server builds and download the core jar files.
* **[Minotar API](https://minotar.net/):** Provides the player skin headers (avatars) used in the player management list.

> **And a sincere thank you to all other open-source developers whose work helped build this project, even if not explicitly listed here.**

---

## ⚠️ Disclaimer & License

* **AI Assistance:** Some features and code structures were created with the assistance of AI technology.
* **Responsibility:** If any critical problems arise from this program, the repository may be taken down without prior notice.
* **Legal:** This app is in **no way affiliated with Mojang AB or Microsoft Corporation**.
* This software is distributed under the MIT License. The copyright holder disclaims any liability for any claims, damages, or other liabilities arising from the use of this software.

❤️ **Created with love by JIN**
