#!/bin/env python
"""
Jakob Janzen
jakob.janzen80@gmail.com
2026-02-22

Linux Mint setup script.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.request


class Logger:
    RED = "\033[1;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[1;34m"
    CYAN = "\033[1;36m"
    WHITE = "\033[1;37m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    def section(self, message):
        print(f"\n\n{self.BLUE}[[ {message.upper()} ]]{self.RESET}")

    def subsection(self, message):
        print(f"\n{self.CYAN}[ {message} ]{self.RESET}")

    def step(self, message):
        print(f"  {self.WHITE}{self.BOLD}->{self.RESET} {message}...")

    def info(self, message):
        print(f"{self.GREEN}INFO:{self.RESET} {message}.")

    def success(self, message):
        print(f"{self.GREEN}{self.BOLD}* SUCCESS:{self.RESET} {message}.")

    def warning(self, message):
        print(f"{self.YELLOW}WARNING:{self.RESET} {message}?", file=sys.stderr)

    def error(self, message):
        print(f"{self.RED}{self.BOLD}ERROR:{self.RESET} {message}!", file=sys.stderr)


class Setup(object):
    def __init__(self, logger):
        self.parser = argparse.ArgumentParser(
            description=f"Usage: {os.path.basename(sys.argv[0])} [OPTIONS]",
            formatter_class=argparse.RawTextHelpFormatter,
            add_help=False,
        )
        self.options = [
            ["u", "update", "store_true", "Update only system."],
            ["r", "remove", "store_true", "Remove only packages."],
            ["i", "install", "store_true", "Install only packages."],
            [None, "vscode", "store_true", "Add repository and install VS Code."],
            ["c", "clean", "store_true", "Clean only packages."],
            ["s", "system", "store_true", "Setup system settings."],
            ["h", "help", "help", "Show this help and quit."],
        ]
        self.logger = logger

    def _add_argument(self, short, long, action, help_text):
        flags = [f"-{short}" if short else None, f"--{long}"]
        flags = [f for f in flags if f]
        self.parser.add_argument(*flags, action=action, help=help_text)

    def elevate_privileges(self):
        """Elevate privileges using sudo if not running as root."""
        self.logger.info(f"Current UID: {os.getuid()}")
        if os.getuid() != 0:
            self.logger.subsection("Elevating privileges to ROOT")
            cmd = ("sudo", sys.executable, *sys.argv)
            try:
                os.execvp("sudo", cmd)
            except Exception as e:
                self.logger.error(f"Failed to elevate privileges: {e}")
                sys.exit(1)

    def run_as_user(self, cmd, check=True):
        """
        Runs any command as the original logged-in user.
        If not running under sudo, it runs as the current user.
        """
        original_user = os.environ.get("SUDO_USER")
        if original_user and os.getuid() == 0:
            self.logger.info(f"Running '{cmd[0]}' as user: {original_user}")
            full_cmd = ["sudo", "-u", original_user] + cmd
        else:
            full_cmd = cmd
        try:
            return subprocess.run(full_cmd, check=check)
        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"Execution failed for '{cmd[0]}'. Exit code: {e.returncode}"
            )
            return None

    def cli_options(self):
        for option in self.options:
            self._add_argument(*option)
        return self.parser.parse_args()

    def check_argv(self, argv):
        self.logger.step("Checking if CLI options were given")
        if len(argv) == 1:
            self.parser.print_help()
            sys.exit(1)
        self.logger.success(f"{len(argv)-1} given")

    def update(self):
        self.logger.subsection("System Refresh")
        self.logger.step("Updating APT cache")
        subprocess.run(["apt", "update"])
        self.logger.step("Ensuring Nala is installed")
        subprocess.run(["apt", "install", "nala"])
        self.logger.step("Syncing Nala with repositories")
        subprocess.run(["nala", "update"])
        self.logger.success("System repositories are up to date")

    def upgrade(self):
        self.update()
        self.logger.subsection("Full System Upgrade")
        self.logger.step("Running Nala upgrade")
        subprocess.run(["nala", "upgrade"])
        self.logger.success("All system packages are current")

    def flatpak(self):
        self.logger.subsection("Flatpak Update")
        self.logger.step("Flatpak: checking configured remotes")
        self.run_as_user(["flatpak", "remotes"])
        self.logger.step("Flatpak: listing installed")
        self.run_as_user(["flatpak", "list"])
        self.logger.step("Flatpak: checking for updates and runtimes")
        self.run_as_user(["flatpak", "update"])

    def remove(self, categories=None):
        if categories:
            for key, packages in categories.items():
                self.logger.subsection(f"Removing Category: {key}")
                self.logger.step(f"Purging {len(packages)} packages")
                subprocess.run(["nala", "purge"] + packages)
                self.logger.success(f"Removed all packages in {key}")

    def install(self, categories=None):
        if categories:
            for key, packages in categories.items():
                self.logger.subsection(f"Installing Category: {key}")
                self.logger.step(f"Installing {len(packages)} packages from {key}")
                subprocess.run(["nala", "install"] + packages)
                self.logger.success(f"Category {key} installed successfully")

    def clean(self):
        self.logger.step("Autoremoving")
        subprocess.run(["nala", "autoremove"])
        self.logger.step("Autopurging")
        subprocess.run(["nala", "autopurge"])
        self.logger.step("Cleaning")
        subprocess.run(["nala", "clean"])

    def install_vscode(self):
        self.logger.subsection("VS Code Repository & Key Setup")
        keyring_dir = "/etc/apt/keyrings"
        keyring_path = f"{keyring_dir}/packages.microsoft.gpg"
        repo_path = "/etc/apt/sources.list.d/vscode.list"
        self.logger.step("Purging old Microsoft repository and key files")
        conflicting_files = [
            repo_path,
            "/etc/apt/sources.list.d/vscode.list.save",
            "/etc/apt/sources.list.d/vscode.sources",
            "/usr/share/keyrings/microsoft.gpg",
            "/usr/share/keyrings/gpgsecurity.microsoft.com.gpg",
            "/etc/apt/trusted.gpg.d/microsoft.gpg",
            keyring_path,
        ]
        for f in conflicting_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                    self.logger.info(f"Removed conflicting file: {f}")
                except Exception as e:
                    self.logger.error(f"Could not remove {f}: {e}")
        try:
            os.makedirs(keyring_dir, exist_ok=True)
            self.logger.step("Downloading fresh GPG key from Microsoft")
            url = "https://packages.microsoft.com/keys/microsoft.asc"
            with urllib.request.urlopen(url) as response:
                asc_data = response.read()
            gpg_result = subprocess.run(
                ["gpg", "--dearmor"], input=asc_data, capture_output=True, check=True
            )
            with open(keyring_path, "wb") as f:
                f.write(gpg_result.stdout)
            os.chmod(keyring_path, 0o644)
            self.logger.info(f"GPG key successfully installed to {keyring_path}")
            self.logger.step("Creating clean repository list")
            repo_entry = (
                f"deb [arch=amd64 signed-by={keyring_path}] "
                "https://packages.microsoft.com/repos/code stable main\n"
            )
            with open(repo_path, "w") as f:
                f.write(repo_entry)
            self.logger.step("Clearing local APT lists for fresh sync")
            subprocess.run(["rm", "-rf", "/var/lib/apt/lists/*"], check=True)
            self.logger.step("Running Nala update and installing 'code'")
            subprocess.run(["nala", "update"], check=True)
            subprocess.run(["nala", "install", "-y", "code"], check=True)
            self.logger.success("VS Code installed successfully")
        except Exception as e:
            self.logger.error(f"Installation failed: {e}")

    def apply_sysctl_optimizations(self):
        """Applies kernel and virtual memory optimizations for laptop stability."""
        self.logger.subsection("Kernel & VM Optimizations")
        target_file = "/etc/sysctl.d/99-zzz-sysctl.conf"
        sysctl_content = (
            "# Optimized sysctl settings for TUXEDO Laptop\n"
            "\n"
            "net.ipv4.tcp_fastopen = 3\n"
            "net.core.netdev_max_backlog = 5000\n"
            "\n"
            "kernel.printk = 3 4 1 3\n"
            "kernel.sysrq = 0\n"
            "\n"
            "vm.dirty_background_ratio = 10\n"
            "vm.dirty_ratio = 40\n"
            "vm.nr_hugepages = 0\n"
            "vm.swappiness = 10\n"
            "vm.vfs_cache_pressure = 50\n"
        )
        try:
            self.logger.step(f"Writing optimizations to {target_file}")
            with open(target_file, "w") as f:
                f.write(sysctl_content)
            os.chmod(target_file, 0o644)
            self.logger.step("Reloading sysctl configuration")
            subprocess.run(["sysctl", "--system"], check=True, capture_output=True)
            self.logger.success("Kernel and VM parameters applied successfully")
        except Exception as e:
            self.logger.error(f"Failed to apply sysctl settings: {e}")

    def set_journald_property(self, key, value):
        config_file = "/etc/systemd/journald.conf"
        backup_file = f"{config_file}.bak"
        val_regex = r"(^[0-9]+[KMGTPsmhday]?$)|(^(persistent|auto|volatile|yes|no)$)"
        if not re.match(val_regex, str(value)):
            self.logger.error(f"Invalid value '{value}' for key '{key}'")
            return False
        try:
            if not os.path.exists(backup_file):
                shutil.copy2(config_file, backup_file)
                self.logger.info(f"Backup created: {backup_file}")
            with open(config_file, "r") as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if not (
                    stripped.startswith(f"{key}=") or stripped.startswith(f"#{key}=")
                ):
                    new_lines.append(line)
            final_lines = []
            found_section = False
            for line in new_lines:
                final_lines.append(line)
                if "[Journal]" in line:
                    final_lines.append(f"{key}={value}\n")
                    found_section = True
            if not found_section:
                final_lines.insert(0, f"[Journal]\n{key}={value}\n")
            with open(config_file, "w") as f:
                f.writelines(final_lines)
            self.logger.step(f"Journald: {key} set to {value}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to modify journald.conf: {e}")
            return False

    def activate_service(self, service_name):
        """Enable, start, and restart a systemd service, then show status."""
        self.logger.step(f"Activating service: {service_name}")
        try:
            subprocess.run(["systemctl", "enable", "--now", service_name], check=True)
            subprocess.run(["systemctl", "restart", service_name], check=True)
            self.logger.info(f"Verifying status for {service_name}")
            status = subprocess.run(
                ["systemctl", "--no-pager", "status", service_name, "-n", "0"],
                capture_output=True,
                text=True,
            )
            if status.returncode == 0:
                self.logger.success(f"Service {service_name} is active and enabled")
            else:
                self.logger.warning(
                    f"Service {service_name} started but status reported issues"
                )
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to activate service {service_name}: {e}")


def main():
    logger = Logger()
    setup = Setup(logger=logger)
    args = setup.cli_options()
    setup.check_argv(sys.argv)
    setup.elevate_privileges()

    if args.update:
        logger.section("UPDATE")
        setup.upgrade()
        setup.flatpak()

        logger.success("System is up to date")

    if args.remove:
        logger.section("PURGE & CLEANUP")
        setup.update()

        categories = {
            "VIM": [
                "vim*",
            ],
            "UNWANTED": [
                "gcolor3",
                "thunderbird*",
                "thermald",
                "preload",
                "haveged",
                "unattended-upgrades",
                "smartmontools",
                "htop",
                "nmon",
                "iotop",
                "dconf-editor",  # Graphical settings editor
                "tree",  # Directory tree visualizer
                "synaptic",  # GUI management tool
                "needrestart",  # Service restart prompter
                "ppa-purge",  # Safely remove unstable repositories
                "software-properties-common",
                "aspell",  # Classic CLI engine
                "aspell-de",  # CLI German dict
                "aspell-en",  # CLI English dict
                "myspell-dictionary-de",  # Legacy German support
                "libreoffice",  # Full office suite
                "libreoffice-base",
                "libreoffice-base-core",
                "libreoffice-base-drivers",
                "vlc-plugin-fluidsynth",  # MIDI synth support
                "vlc-plugin-jack",  # JACK audio support
                "vlc-plugin-svg",  # SVG icon support
                "vlc-plugin-visualization",  # Audio visualizers
                "python3-autopep8",  # PEP 8 style guide formatter
            ],
        }
        setup.remove(categories)

        logger.success("Cleaned up unwanted packages from the system")

    if args.install:
        logger.section("INSTALL")
        setup.update()

        categories = {
            "REPOSITORY": [
                "ubuntu-standard",  # Core system utilities
                "ubuntu-restricted-extras",  # Media codecs and MS fonts
            ],
            "PACKAGE_TOOLS": [
                "nala",  # Efficient terminal interface
                "aptitude",
                "deborphan",  # Find unused libraries
                "apt-transport-https",  # Support for secure repos
                "apt-file",  # Track package ownership
            ],
            "REQUIRED": [
                "tmux",  # Terminal multiplexer
                "neovim",  # Editor
            ],
            "UTILITY": [
                "bash-completion",  # Productivity
                "fzf",
                "zoxide",
                "eza",  # Navigation
                "mc",
                "ripgrep",
                "bat",
                "jq",  # Processing
                "duf",
                "ncdu",
                "gdisk",  # Disk Management
                "dconf-cli",  # Settings
                "cpufrequtils",  # Thermal Control
            ],
            "ANALYZE": [
                "btop",  # Resource monitoring
                "powertop",  # Power/Thermal tuning
                "fatrace",  # Disk wake-up hunting
                "inxi",  # Hardware auditing
                "hwinfo",  # Hardware auditing
                # --- TUXEDO Specific (Commented for now) ---
                # "intel-gpu-tools",
                # "intel_gpu_top",
            ],
            "NETWORK": [
                "ca-certificates",  # SSL/TLS validation (Critical)
                "net-tools",  # Classic tools (Manual use only)
                "curl",  # Manual use
                "wget",  # Manual use
                "speedtest-cli",
                "openssh-client",  # Needed to connect OUT
                "openssh-server",  # Now MASKED (Zero process impact)
                "openssh-sftp-server",  # Now MASKED
                "sshfs",  # High utility, zero idle cost
            ],
            "SPELLING": [
                "libenchant-2-2",  # App-to-dictionary bridge
                "hunspell",  # Modern standard engine
                "hunspell-de-de-frami",  # Primary German dict
                "mythes-de",  # German Thesaurus
                "hyphen-de",  # German Hyphenation
                "hunspell-en-us",  # Primary English dict
                "mythes-en-us",  # English Thesaurus
                "hyphen-en-us",  # English Hyphenation
            ],
            "ACCESSORY": [
                "adwaita-qt",  # Qt5 theme matching
                "adwaita-qt6",  # Qt6 theme matching
                "qt5ct",  # Qt5 config utility
                "qt6ct",  # Qt6 config utility
                "meld",  # Visual diff/merge tool
                "cheese",  # Webcam tester
                "transmission-gtk",  # Lightweight Torrent client
                "sqlite3",  # Command line interface for SQLite 3
            ],
            "OFFICE": [
                "libreoffice-writer",  # (Word processing)
                "libreoffice-calc",  # (Spreadsheets)
                "libreoffice-impress",  # (Presentations)
                "libreoffice-math",  # (Formula editor)
                "libreoffice-draw",  # (Graphics/PDF editing)
                "libreoffice-gtk3",  # XFCE UI integration
                "libreoffice-style-sifr",  # Flat icon theme
                "libreoffice-l10n-de",  # German UI translation
                "pandoc",  # Document converter
                "texlive-full",  # Comprehensive LaTeX (~5GB)
            ],
            "GRAPHIC": [
                "gimp",  # GNU Image Manipulation Program
                "gimp-data-extras",  # Brushes and patterns
                "gimp-plugin-registry",  # Essential plugin bundle
                "gimp-help-de",  # German GIMP manuals
                "inkscape",  # Vector graphics editor
                "libwacom-common",  # Wacom/Tablet support
            ],
            "MULTIMEDIA": [
                "mpv",  # Fast, GPU-accelerated player
                "yt-dlp",  # YouTube/Video downloader
                "vlc",  # Universal media player
                "vlc-l10n",  # German UI for VLC
                "vlc-plugin-pipewire",  # Native PipeWire audio
                "audacity",  # Waveform audio editor
                "pavucontrol",  # PipeWire/Pulse Mixer
            ],
            "CODEC": [
                "ffmpeg",  # The Swiss-army knife for media
                "libavif-bin",  # AVIF image support
                "libwebm-tools",  # WebM processing
                "libwebm1",  # WebM runtime library
                "dav1d",  # Ultra-fast AV1 decoder
                "davs2",  # AVS2 support
                "rav1e",  # Rust-based AV1 encoder
                "svt-av1",  # Intel-optimized AV1 (Best for you)
                "x264",  # H.264/AVC standard
                "x265",  # H.265/HEVC standard
                "aften",  # AC3 toolset
                "faac",  # AAC encoder
                "fdkaac",  # FDK-AAC CLI
                "libfdk-aac2",  # FDK-AAC library
                "lame",  # MP3 encoder
                "speex",  # Speech-specific codec
                "mkvtoolnix",  # MKV editor (mkvmerge)
                "ogmtools",  # OGG/OGM stream tools
            ],
            "COMPRESSION": [
                "tar",  # Standard Unix archiver
                "gzip",  # Standard compression
                "bzip2",  # High compression legacy
                "zip",  # Universal Windows compatibility
                "unzip",  # Standard extractor
                "pigz",  # Multi-core GZIP (Fast!)
                "pbzip2",  # Multi-core BZIP2
                "lbzip2",  # Fast multi-core BZIP2
                "pixz",  # Parallel XZ with indexing
                "zstd",  # Modern Facebook-speed standard
                "lz4",  # Fastest real-time compression
                "lrzip",  # For very large archives
                "7zip",  # 7-Zip (Modern p7zip)
                "zpaq",  # Maximum data density
                "lzip",  # Error-resilient LZMA
                "plzip",  # Multi-core LZIP
                "tarlz",  # Tar with LZIP support
                "lzop",  # Low-CPU overhead LZO
                "unar",  # Universal extractor (Best for XFCE)
                "unrar",  # RAR extraction support
                "rar",  # RAR creation support
                "cabextract",  # Microsoft .cab support
                "lhasa",  # LZH/LHA support
                "unace",  # ACE support
                "dar",  # Disk Archive (Backups)
                "par2",  # Data repair/redundancy
            ],
            "DEVELOPMENT_COMPILER": [
                "build-essential",  # Standard C/C++ toolchain (make, gcc)
                "cmake",  # Cross-platform build automation
                "cmake-format",  # Formatter for CMake scripts
                "ninja-build",  # Fast alternative to 'make'
                "clang",  # LLVM-based C/C++ compiler
                "clang-format",  # Standard C++ code formatter
                "clang-tidy",  # Static analyzer for C++
                "clang-tools",  # Extra LLVM development utilities
                "lldb",  # High-performance debugger
                "libmagic-dev",  # Development files for file-type detection
                "libmagickwand-dev",  # ImageMagick C-API library
                "libssl-dev",  # Header files for SSL/TLS
                "valgrind",  # Memory leak and profiling tool
            ],
            "DEVELOPMENT_PYTHON": [
                "pipx",  # Isolated CLI tool installer (Safe for Mint)
                "python-is-python3",  # Maps 'python' command to python3
                "python3-gpg",  # GPG library for your script's logic
                "python3-pip",  # Standard package installer
                "python3-venv",  # Native virtual environment support
                "pipenv",  # Deterministic dependency management
                "python3-poetry",  # Modern project/package manager
                "black",  # Uncompromising code formatter
                "python3-autopep8",  # PEP 8 style guide formatter
                "python3-flake8",  # Code linter for syntax/style
                "python3-pytest",  # Advanced testing framework
            ],
            "DEVELOPMENT_SHELL": [
                "expect",  # Automation for interactive CLI prompts
                "shellcheck",  # Static analysis/linter for scripts
                "shfmt",  # Shell script formatter
            ],
            "DEVELOPMENT_DOCS": [
                "bash-doc",  # Local documentation for Bash
                "glibc-doc",
                "linux-doc",  # Deep Linux kernel manuals
                "manpages-dev",
                "manpages-posix-dev",
                "python3-doc",  # Local Python 3 reference
                "zeal",  # Offline API documentation browser
            ],
            "DEVELOPMENT_JAVA": [
                "default-jdk",  # Standard OpenJDK for Java dev
            ],
        }
        setup.install(categories)

        logger.section("FLATPAK MANAGEMENT")

        logger.success("All required packages (APT & Flatpak) have been processed")

    if args.vscode:
        logger.section("VISUAL STUDIO CODE")
        setup.update()
        setup.install_vscode()
        logger.success("VS Code installation and repository setup complete")

    if args.clean:
        logger.section("CLEAN")
        setup.update()
        setup.clean()
        logger.success("Cleaned up packages in System")

    if args.system:
        logger.section("SYSCTL")
        setup.apply_sysctl_optimizations()

        logger.section("JOURNALD")
        setup.logger.subsection("Configuring System Journal")
        setup.set_journald_property("Storage", "persistent")
        setup.set_journald_property("SystemMaxUse", "100M")
        setup.set_journald_property("SystemMaxFileSize", "50M")
        setup.set_journald_property("SyncIntervalSec", "5m")
        logger.success("Journald configuration updated")

        logger.section("SERVICES")
        services = [
            "systemd-sysctl",
            "systemd-journald",
            "preload",
            "haveged",
            "ssh",
        ]
        for service in services:
            setup.activate_service(service)
        logger.success("All system services are optimized and running")

    print()


if __name__ == "__main__":
    main()
