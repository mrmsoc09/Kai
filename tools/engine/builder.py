"""
Build and Packaging Module
Handles dependency installation, virtual environment creation, and binary compilation.
"""

import subprocess
import sys
import os
import shutil
import venv
from pathlib import Path
from typing import Dict, Any, List, Optional


class Builder:
    """
    Handles compilation and packaging of generated security tools.
    Supports both Python package installation and standalone binary creation.
    """
    
    def __init__(self):
        self.pyinstaller_options = [
            "--onefile",           # Single executable
            "--clean",             # Clean cache
            "--noconfirm",         # Replace output without confirmation
            "--log-level=WARN"     # Reduce noise
        ]
    
    def install_dependencies(self, project_path: Path, 
                            venv_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Install project dependencies.
        
        Args:
            project_path: Path to project directory
            venv_path: Optional virtual environment path (creates if None)
            
        Returns:
            Dict with installation results
        """
        result = {
            "success": False,
            "venv_path": None,
            "installed_packages": []
        }
        
        try:
            # Create virtual environment if needed
            if venv_path is None:
                venv_path = project_path / "venv"
            
            if not venv_path.exists():
                venv.create(venv_path, with_pip=True)
                result["venv_path"] = str(venv_path)
            
            # Determine pip path
            pip_cmd = venv_path / "bin" / "pip"
            if not pip_cmd.exists():
                pip_cmd = venv_path / "Scripts" / "pip.exe"  # Windows
            
            # Install requirements
            req_file = project_path / "requirements.txt"
            if req_file.exists():
                subprocess.run(
                    [str(pip_cmd), "install", "-r", str(req_file)],
                    check=True,
                    capture_output=True,
                    text=True
                )
                
                # Get installed packages list
                installed = subprocess.run(
                    [str(pip_cmd), "freeze"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                result["installed_packages"] = installed.stdout.strip().split('\n')
            
            result["success"] = True
            
        except subprocess.CalledProcessError as e:
            result["error"] = f"Installation failed: {e.stderr}"
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def compile(self, project_path: Path, 
                project_name: str,
                entry_point: str = "main.py",
                icon: Optional[str] = None,
                hidden_imports: List[str] = None) -> Dict[str, Any]:
        """
        Compile project to standalone binary using PyInstaller.
        
        Args:
            project_path: Path to project directory
            project_name: Name of output binary
            entry_point: Main Python file
            icon: Path to icon file (optional)
            hidden_imports: Additional imports for PyInstaller
            
        Returns:
            Dict with build results and artifact paths
        """
        result = {
            "success": False,
            "artifacts": [],
            "dist_path": None
        }
        
        try:
            # Ensure PyInstaller is available
            venv_result = self.install_dependencies(project_path)
            if not venv_result["success"]:
                raise Exception(f"Dependency installation failed: {venv_result.get('error')}")
            
            venv_path = Path(venv_result["venv_path"])
            python_cmd = venv_path / "bin" / "python"
            if not python_cmd.exists():
                python_cmd = venv_path / "Scripts" / "python.exe"
            
            # Build PyInstaller command
            src_path = project_path / "src" / entry_point
            dist_path = project_path / "dist"
            build_path = project_path / "build"
            
            cmd = [
                str(python_cmd), "-m", "PyInstaller",
                *self.pyinstaller_options,
                "--name", project_name,
                "--distpath", str(dist_path),
                "--workpath", str(build_path),
                "--specpath", str(project_path),
                str(src_path)
            ]
            
            # Add hidden imports
            if hidden_imports:
                for imp in hidden_imports:
                    cmd.extend(["--hidden-import", imp])
            
            # Add icon if provided
            if icon and Path(icon).exists():
                cmd.extend(["--icon", icon])
            
            # Add data files (primitives)
            primitives_src = Path(__file__).parent / "primitives"
            if primitives_src.exists():
                cmd.extend([
                    "--add-data", 
                    f"{primitives_src}:primitives"
                ])
            
            # Execute build
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(project_path)
            )
            
            if process.returncode != 0:
                raise Exception(f"PyInstaller failed: {process.stderr}")
            
            # Locate output binary
            binary_name = project_name
            if sys.platform == "win32":
                binary_name += ".exe"
            
            binary_path = dist_path / binary_name
            if binary_path.exists():
                result["artifacts"].append(str(binary_path))
                result["dist_path"] = str(dist_path)
                result["success"] = True
                
                # Make executable on Unix
                if sys.platform != "win32":
                    os.chmod(binary_path, 0o755)
            else:
                raise Exception("Binary not found after build")
                
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def create_installer(self, project_path: Path, 
                        project_name: str,
                        version: str = "1.0.0") -> Dict[str, Any]:
        """
        Create platform-specific installer/package.
        (Placeholder for advanced packaging)
        """
        result = {"success": False}
        
        if sys.platform == "win32":
            # Could use NSIS or WiX here
            result["message"] = "Windows installer creation not implemented"
        elif sys.platform == "darwin":
            # Could create .dmg or .pkg
            result["message"] = "macOS package creation not implemented"
        else:
            # Could create .deb or .rpm
            result["message"] = "Linux package creation not implemented"
            
        return result
    
    def validate_build(self, binary_path: Path) -> Dict[str, Any]:
        """
        Validate the compiled binary runs correctly.
        """
        result = {
            "success": False,
            "valid": False,
            "output": ""
        }
        
        try:
            # Test --help flag
            test_run = subprocess.run(
                [str(binary_path), "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            result["returncode"] = test_run.returncode
            result["output"] = test_run.stdout + test_run.stderr
            
            if test_run.returncode == 0 and ("usage" in test_run.stdout.lower() or 
                                              "help" in test_run.stdout.lower()):
                result["valid"] = True
                result["success"] = True
            else:
                result["error"] = "Binary validation failed - unexpected output"
                
        except subprocess.TimeoutExpired:
            result["error"] = "Binary validation timed out"
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def clean_build_artifacts(self, project_path: Path):
        """Clean up build directories."""
        dirs_to_clean = ["build", "__pycache__", "*.spec"]
        for pattern in dirs_to_clean:
            for path in project_path.glob(pattern):
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
