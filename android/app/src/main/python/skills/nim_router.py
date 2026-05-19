"""
NIM Image Router — NVIDIA NIM Image Generation
Supports FLUX.1-schnell, FLUX.1-dev, SD 3.5 Large, visual-changenet.
Pure API — no model downloads.
"""

import os
import json
import base64
import time
import requests
from pathlib import Path
from datetime import datetime

NIM_BASE = "https://integrate.api.nvidia.com/v1"

NIM_MODELS = [
    {
        "slug": "flux.1-schnell",
        "nim_model_id": "black-forest-labs/flux.1-schnell",
        "endpoint_type": "text-to-image",
        "source": "Black Forest Labs",
        "notes": "Fastest FLUX — distilled, 4-step, great for iteration",
        "free_endpoint": False,
    },
    {
        "slug": "flux.1-dev",
        "nim_model_id": "black-forest-labs/flux.1-dev",
        "endpoint_type": "text-to-image",
        "source": "Black Forest Labs",
        "notes": "Full FLUX dev — higher quality, more steps",
        "free_endpoint": False,
    },
    {
        "slug": "flux.2-klein-4b",
        "nim_model_id": "black-forest-labs/flux.2-klein-4b",
        "endpoint_type": "text-to-image",
        "source": "Black Forest Labs",
        "notes": "Distilled edit+gen — 4B params, lightning fast",
        "free_endpoint": False,
    },
    {
        "slug": "stable-diffusion-3.5-large",
        "nim_model_id": "stabilityai/stable-diffusion-3.5-large",
        "endpoint_type": "text-to-image",
        "source": "Stability AI",
        "notes": "SD 3.5 Large — popular, well-supported",
        "free_endpoint": False,
    },
    {
        "slug": "stable-diffusion-3-medium",
        "nim_model_id": "stabilityai/stable-diffusion-3-medium",
        "endpoint_type": "text-to-image",
        "source": "Stability AI",
        "notes": "SD 3 Medium — free endpoint on NIM",
        "free_endpoint": True,
    },
    {
        "slug": "visual-changenet",
        "nim_model_id": "nvidia/visual-changenet",
        "endpoint_type": "segmentation",
        "source": "NVIDIA",
        "notes": "Pixel-level change detection between two images",
        "free_endpoint": True,
    },
]

MODEL_MAP = {m["slug"]: m for m in NIM_MODELS}


class NIMImageRouter:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("NIM_API_KEY", "")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def generate(
        self,
        model_slug: str,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg_scale: float = 7.0,
        seed: int = -1,
        save_path: str = "",
        reference_image_b64: str = "",
    ) -> dict:
        model = MODEL_MAP.get(model_slug)
        if not model:
            return {"success": False, "error": f"Unknown model: {model_slug}"}
        if model["endpoint_type"] == "segmentation":
            return {"success": False, "error": "Use .segment() for segmentation models"}
        return self._call_text_to_image(
            model, prompt, negative_prompt,
            width, height, steps, cfg_scale, seed,
            save_path, reference_image_b64
        )

    def segment(self, image1_b64: str, image2_b64: str, save_path: str = "") -> dict:
        model = MODEL_MAP["visual-changenet"]
        url = f"{NIM_BASE}/infer"
        payload = {
            "model": model["nim_model_id"],
            "input": {"image_t1": image1_b64, "image_t2": image2_b64}
        }
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=60)
            return self._handle_response(resp, model, save_path, is_segmentation=True)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def probe_all(self, test_prompt: str = "a glowing crystal fox in snow") -> list[dict]:
        results = []
        for model in NIM_MODELS:
            if model["endpoint_type"] == "segmentation":
                results.append({"slug": model["slug"], "status": "SKIPPED", "reason": "segmentation"})
                continue
            t0 = time.time()
            try:
                out = self._call_text_to_image(
                    model, test_prompt, "",
                    width=512, height=512, steps=4, cfg_scale=1.0, seed=42
                )
                latency = int((time.time() - t0) * 1000)
                results.append({
                    "slug": model["slug"],
                    "status": "OK" if out["success"] else "ERROR",
                    "latency_ms": latency,
                    "error": out.get("error"),
                })
            except Exception as e:
                results.append({"slug": model["slug"], "status": "EXCEPTION", "error": str(e)})
            time.sleep(0.5)
        return results

    def list_models(self) -> list[dict]:
        return NIM_MODELS

    def _call_text_to_image(
        self, model, prompt, negative_prompt,
        width, height, steps, cfg_scale, seed,
        save_path="", reference_image_b64=""
    ) -> dict:
        if not self.api_key:
            return {"success": False, "error": "No NIM_API_KEY set"}
        url = f"{NIM_BASE}/images/generations"
        payload = {
            "model": model["nim_model_id"],
            "prompt": prompt,
            "n": 1,
            "size": f"{width}x{height}",
            "response_format": "b64_json",
            "steps": steps,
            "cfg_scale": cfg_scale,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if seed >= 0:
            payload["seed"] = seed
        if reference_image_b64 and model["slug"] == "flux.1-kontext-dev":
            payload["image"] = reference_image_b64
        try:
            resp = requests.post(url, headers=self.headers, json=payload, timeout=120)
            return self._handle_response(resp, model, save_path)
        except requests.Timeout:
            return {"success": False, "model": model["slug"], "error": "Timeout (120s)"}
        except Exception as e:
            return {"success": False, "model": model["slug"], "error": str(e)}

    def _handle_response(self, resp, model, save_path="", is_segmentation=False) -> dict:
        slug = model["slug"]
        if resp.status_code != 200:
            try:
                err = resp.json()
            except Exception:
                err = resp.text
            return {"success": False, "model": slug, "status_code": resp.status_code, "error": str(err)}
        data = resp.json()
        if is_segmentation:
            if save_path:
                Path(save_path).write_text(json.dumps(data, indent=2))
            return {"success": True, "model": slug, "data": data}
        items = data.get("data", [])
        if not items:
            return {"success": False, "model": slug, "error": "No image in response"}
        image_b64 = items[0].get("b64_json", "")
        if save_path and image_b64:
            Path(save_path).write_bytes(base64.b64decode(image_b64))
        return {
            "success": True,
            "model": slug,
            "image_b64": image_b64,
            "size": f"{len(image_b64)} chars",
        }


_router: NIMImageRouter = None  # type: ignore


def get_router() -> NIMImageRouter:
    global _router
    if _router is None:
        _router = NIMImageRouter()
    return _router
