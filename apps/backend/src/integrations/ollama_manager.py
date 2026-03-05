"""
Kaison K1 - Ollama Integration Manager
Hardware detection, model recommendations, and local AI management
"""

import os
import asyncio
import logging
import subprocess
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum

import psutil
import httpx

logger = logging.getLogger(__name__)


class GPUType(str, Enum):
    """GPU types"""
    NVIDIA = "nvidia"
    AMD = "amd"
    APPLE = "apple"
    CPU = "cpu"


@dataclass
class HardwareSpec:
    """Hardware specifications"""
    vram: int  # VRAM in GB
    cpu_threads: int
    ram: int  # RAM in GB
    gpu_type: GPUType
    gpu_name: str


@dataclass
class ModelRecommendation:
    """AI model recommendation"""
    name: str
    description: str
    priority: int
    size_gb: float
    min_vram_gb: int
    performance_tier: str  # 'best', 'balanced', 'fast'


class OllamaManager:
    """Manager for Ollama local AI integration"""

    # Model catalog with requirements
    MODEL_CATALOG = {
        'llama3:70b': {
            'size_gb': 40,
            'min_vram_gb': 24,
            'description': 'Best for complex reasoning and code analysis',
            'tier': 'best'
        },
        'mixtral:8x7b': {
            'size_gb': 26,
            'min_vram_gb': 24,
            'description': 'Best for code generation and mixed tasks',
            'tier': 'best'
        },
        'codestral:22b': {
            'size_gb': 13,
            'min_vram_gb': 16,
            'description': 'Best for vulnerability analysis',
            'tier': 'best'
        },
        'llama3:13b': {
            'size_gb': 7.5,
            'min_vram_gb': 12,
            'description': 'Balanced performance for general tasks',
            'tier': 'balanced'
        },
        'codellama:13b': {
            'size_gb': 7.5,
            'min_vram_gb': 12,
            'description': 'Code-focused model for security work',
            'tier': 'balanced'
        },
        'llama3:8b': {
            'size_gb': 4.5,
            'min_vram_gb': 8,
            'description': 'Recommended for 8GB VRAM systems',
            'tier': 'balanced'
        },
        'mistral:7b': {
            'size_gb': 4,
            'min_vram_gb': 8,
            'description': 'Fast and efficient general model',
            'tier': 'fast'
        },
        'phi3:mini': {
            'size_gb': 2.3,
            'min_vram_gb': 4,
            'description': 'Lightweight option for constrained systems',
            'tier': 'fast'
        },
        'tinyllama:1.1b': {
            'size_gb': 0.6,
            'min_vram_gb': 2,
            'description': 'Ultra-lightweight CPU-friendly model',
            'tier': 'fast'
        }
    }

    def __init__(self, ollama_url: str = ""):
        self.ollama_url = ollama_url or os.getenv("OLLAMA_HOST", os.getenv("OLLAMA_API_URL", "http://localhost:11434"))
        self.http_client = httpx.AsyncClient(timeout=120.0)

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.http_client.aclose()

    async def detect_hardware(self) -> HardwareSpec:
        """Detect GPU VRAM, CPU threads, RAM"""
        logger.info("Detecting hardware specifications...")

        # Detect CPU and RAM
        cpu_threads = os.cpu_count() or 1
        ram_bytes = psutil.virtual_memory().total
        ram_gb = ram_bytes / (1024**3)

        # Detect GPU
        vram_gb = 0
        gpu_type = GPUType.CPU
        gpu_name = "CPU Only"

        # Try NVIDIA first
        nvidia_vram = await self._detect_nvidia_gpu()
        if nvidia_vram > 0:
            vram_gb = nvidia_vram
            gpu_type = GPUType.NVIDIA
            gpu_name = await self._get_nvidia_gpu_name()

        # Try AMD if NVIDIA not found
        elif await self._detect_amd_gpu():
            vram_gb = await self._get_amd_vram()
            gpu_type = GPUType.AMD
            gpu_name = "AMD GPU"

        # Check for Apple Silicon
        elif await self._detect_apple_silicon():
            vram_gb = int(ram_gb * 0.7)  # Apple Silicon shares memory
            gpu_type = GPUType.APPLE
            gpu_name = "Apple Silicon GPU"

        hardware = HardwareSpec(
            vram=int(vram_gb),
            cpu_threads=cpu_threads,
            ram=int(ram_gb),
            gpu_type=gpu_type,
            gpu_name=gpu_name
        )

        logger.info(f"Hardware detected: {hardware}")
        return hardware

    async def _detect_nvidia_gpu(self) -> float:
        """Detect NVIDIA GPU VRAM"""
        try:
            # Try nvidia-smi
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                vram_mb = float(result.stdout.strip().split('\n')[0])
                return vram_mb / 1024  # Convert MB to GB

        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass

        # Try py3nvml
        try:
            import py3nvml.py3nvml as nvml
            nvml.nvmlInit()
            handle = nvml.nvmlDeviceGetHandleByIndex(0)
            info = nvml.nvmlDeviceGetMemoryInfo(handle)
            nvml.nvmlShutdown()
            return info.total / (1024**3)  # Convert bytes to GB
        except Exception:
            pass

        return 0

    async def _get_nvidia_gpu_name(self) -> str:
        """Get NVIDIA GPU name"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass
        return "NVIDIA GPU"

    async def _detect_amd_gpu(self) -> bool:
        """Detect AMD GPU"""
        try:
            result = subprocess.run(
                ['rocm-smi', '--showproductname'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def _get_amd_vram(self) -> float:
        """Get AMD GPU VRAM"""
        try:
            result = subprocess.run(
                ['rocm-smi', '--showmeminfo', 'vram'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Parse output (format varies)
                # Return estimated value
                return 8.0  # Default estimate
        except Exception:
            pass
        return 0

    async def _detect_apple_silicon(self) -> bool:
        """Detect Apple Silicon"""
        try:
            result = subprocess.run(
                ['sysctl', '-n', 'machdep.cpu.brand_string'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return 'Apple' in result.stdout
        except Exception:
            return False

    def recommend_models(self, hardware: HardwareSpec) -> List[ModelRecommendation]:
        """Recommend models based on hardware"""
        recommendations = []

        vram = hardware.vram
        ram = hardware.ram

        # Use RAM for Apple Silicon and CPU-only
        if hardware.gpu_type in [GPUType.APPLE, GPUType.CPU]:
            effective_vram = int(ram * 0.5)  # Use 50% of RAM
        else:
            effective_vram = vram

        logger.info(f"Recommending models for {effective_vram}GB effective VRAM")

        # Filter and sort models
        for model_name, model_info in self.MODEL_CATALOG.items():
            if model_info['min_vram_gb'] <= effective_vram:
                recommendations.append(ModelRecommendation(
                    name=model_name,
                    description=model_info['description'],
                    priority=1 if model_info['tier'] == 'best' else 2 if model_info['tier'] == 'balanced' else 3,
                    size_gb=model_info['size_gb'],
                    min_vram_gb=model_info['min_vram_gb'],
                    performance_tier=model_info['tier']
                ))

        # Sort by priority and size
        recommendations.sort(key=lambda x: (x.priority, -x.size_gb))

        # Limit to top 5
        recommendations = recommendations[:5]

        logger.info(f"Recommended {len(recommendations)} models")
        return recommendations

    async def check_ollama_running(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = await self.http_client.get(f"{self.ollama_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def get_installed_models(self) -> List[Dict[str, Any]]:
        """Get list of installed Ollama models"""
        try:
            response = await self.http_client.get(f"{self.ollama_url}/api/tags")

            if response.status_code == 200:
                data = response.json()
                models = data.get('models', [])

                return [
                    {
                        'name': model.get('name'),
                        'size': model.get('size', 0),
                        'modified_at': model.get('modified_at'),
                        'digest': model.get('digest', '')[:12]
                    }
                    for model in models
                ]
            else:
                logger.error(f"Failed to get installed models: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Error getting installed models: {e}")
            return []

    async def install_model(self, model_name: str, progress_callback=None):
        """Pull Ollama model with progress tracking"""
        logger.info(f"Installing Ollama model: {model_name}")

        try:
            # Use streaming API
            async with self.http_client.stream(
                'POST',
                f"{self.ollama_url}/api/pull",
                json={"name": model_name},
                timeout=3600  # 1 hour timeout
            ) as response:
                if response.status_code != 200:
                    raise Exception(f"Failed to start model pull: {response.status_code}")

                async for line in response.aiter_lines():
                    if line:
                        try:
                            progress = json.loads(line)

                            if progress_callback:
                                await progress_callback(progress)

                            # Log progress
                            status = progress.get('status', '')
                            if 'total' in progress and 'completed' in progress:
                                percent = (progress['completed'] / progress['total']) * 100
                                logger.info(f"Downloading {model_name}: {percent:.1f}%")

                        except json.JSONDecodeError:
                            pass

            logger.info(f"Successfully installed model: {model_name}")
            return True

        except Exception as e:
            logger.error(f"Error installing model {model_name}: {e}")
            raise

    async def chat(self, model: str, prompt: str, stream: bool = False):
        """Chat with local Ollama model"""
        try:
            response = await self.http_client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": stream
                }
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('response', '')
            else:
                raise Exception(f"Chat request failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Error chatting with Ollama: {e}")
            raise

    async def get_embeddings(self, model: str, text: str):
        """Get embeddings for RAG"""
        try:
            response = await self.http_client.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": model,
                    "prompt": text
                }
            )

            if response.status_code == 200:
                data = response.json()
                return data.get('embedding', [])
            else:
                raise Exception(f"Embeddings request failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Error getting embeddings: {e}")
            raise


# Singleton pattern
_ollama_manager_instance: Optional[OllamaManager] = None


def get_ollama_manager() -> OllamaManager:
    """Get or create Ollama manager instance"""
    global _ollama_manager_instance
    if _ollama_manager_instance is None:
        _ollama_manager_instance = OllamaManager()
    return _ollama_manager_instance
