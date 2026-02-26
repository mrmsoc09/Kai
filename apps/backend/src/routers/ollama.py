"""
Kaison K1 - Ollama API Router
Local AI model management and inference
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging
import json
import asyncio

from ..integrations.ollama_manager import get_ollama_manager, HardwareSpec, ModelRecommendation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ollama", tags=["ollama"])


# Pydantic Models
class HardwareResponse(BaseModel):
    vram: int
    cpu_threads: int
    ram: int
    gpu_type: str
    gpu_name: str


class ModelRecommendationResponse(BaseModel):
    name: str
    description: str
    priority: int
    size_gb: float
    min_vram_gb: int
    performance_tier: str


class InstallModelRequest(BaseModel):
    model_name: str


class ChatRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False


class EmbeddingsRequest(BaseModel):
    model: str
    text: str


class InstalledModel(BaseModel):
    name: str
    size: int
    modified_at: Optional[str]
    digest: str


# Endpoints

@router.get("/hardware", response_model=HardwareResponse)
async def detect_hardware():
    """Detect hardware specifications"""
    try:
        manager = get_ollama_manager()

        async with manager:
            hardware = await manager.detect_hardware()

        return HardwareResponse(
            vram=hardware.vram,
            cpu_threads=hardware.cpu_threads,
            ram=hardware.ram,
            gpu_type=hardware.gpu_type.value,
            gpu_name=hardware.gpu_name
        )

    except Exception as e:
        logger.error(f"Error detecting hardware: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/recommended", response_model=List[ModelRecommendationResponse])
async def get_recommended_models():
    """Get AI model recommendations based on hardware"""
    try:
        manager = get_ollama_manager()

        async with manager:
            # Detect hardware
            hardware = await manager.detect_hardware()

            # Get recommendations
            recommendations = manager.recommend_models(hardware)

        return [
            ModelRecommendationResponse(
                name=rec.name,
                description=rec.description,
                priority=rec.priority,
                size_gb=rec.size_gb,
                min_vram_gb=rec.min_vram_gb,
                performance_tier=rec.performance_tier
            )
            for rec in recommendations
        ]

    except Exception as e:
        logger.error(f"Error getting model recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/installed", response_model=List[InstalledModel])
async def get_installed_models():
    """Get list of installed Ollama models"""
    try:
        manager = get_ollama_manager()

        async with manager:
            models = await manager.get_installed_models()

        return [
            InstalledModel(
                name=model['name'],
                size=model['size'],
                modified_at=model.get('modified_at'),
                digest=model['digest']
            )
            for model in models
        ]

    except Exception as e:
        logger.error(f"Error getting installed models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/install")
async def install_model(request: InstallModelRequest):
    """Install Ollama model (non-streaming)"""
    try:
        manager = get_ollama_manager()

        async with manager:
            await manager.install_model(request.model_name)

        return {
            'status': 'success',
            'message': f'Model {request.model_name} installed successfully'
        }

    except Exception as e:
        logger.error(f"Error installing model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/models/install/ws")
async def install_model_stream(websocket: WebSocket, model_name: str = Query(...)):
    """Install Ollama model with real-time progress updates via WebSocket"""
    await websocket.accept()

    try:
        manager = get_ollama_manager()

        # Progress callback
        async def progress_callback(progress: Dict[str, Any]):
            try:
                await websocket.send_json(progress)
            except Exception as e:
                logger.error(f"Error sending progress: {e}")

        async with manager:
            # Check if Ollama is running
            if not await manager.check_ollama_running():
                await websocket.send_json({
                    'status': 'error',
                    'message': 'Ollama is not running. Please start Ollama first.'
                })
                await websocket.close()
                return

            # Start installation
            await websocket.send_json({
                'status': 'starting',
                'message': f'Starting installation of {model_name}...'
            })

            await manager.install_model(model_name, progress_callback=progress_callback)

            # Send completion
            await websocket.send_json({
                'status': 'completed',
                'message': f'Model {model_name} installed successfully!'
            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during model installation")

    except Exception as e:
        logger.error(f"Error during model installation: {e}")
        try:
            await websocket.send_json({
                'status': 'error',
                'message': str(e)
            })
        except Exception:
            pass

    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.post("/chat")
async def chat_with_ollama(request: ChatRequest):
    """Chat with local Ollama model"""
    try:
        manager = get_ollama_manager()

        async with manager:
            # Check if Ollama is running
            if not await manager.check_ollama_running():
                raise HTTPException(
                    status_code=503,
                    detail="Ollama is not running. Please start Ollama first."
                )

            response = await manager.chat(
                model=request.model,
                prompt=request.prompt,
                stream=request.stream
            )

        return {
            'model': request.model,
            'prompt': request.prompt,
            'response': response
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error chatting with Ollama: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embeddings")
async def get_embeddings(request: EmbeddingsRequest):
    """Get embeddings from Ollama model"""
    try:
        manager = get_ollama_manager()

        async with manager:
            # Check if Ollama is running
            if not await manager.check_ollama_running():
                raise HTTPException(
                    status_code=503,
                    detail="Ollama is not running. Please start Ollama first."
                )

            embeddings = await manager.get_embeddings(
                model=request.model,
                text=request.text
            )

        return {
            'model': request.model,
            'embeddings': embeddings,
            'dimension': len(embeddings)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_ollama_status():
    """Check Ollama service status"""
    try:
        manager = get_ollama_manager()

        async with manager:
            is_running = await manager.check_ollama_running()
            models = await manager.get_installed_models() if is_running else []

        return {
            'ollama_running': is_running,
            'ollama_url': manager.ollama_url,
            'installed_models_count': len(models),
            'status': 'operational' if is_running else 'offline'
        }

    except Exception as e:
        logger.error(f"Error getting Ollama status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
