"""Fresh GPU calls and exact prompt-keyed replay; no ordinary gold-label backend."""

from __future__ import annotations
import gc
import importlib.metadata
import os
import signal
import subprocess
import time
from typing import Protocol
from .budget import GPUBudget, Journal
from .util import digest


class Backend(Protocol):
    metadata: dict

    def generate(self, prompt: str, seed: int, max_new_tokens: int, temperature: float) -> dict: ...


def gpu_probe() -> dict:
    import torch

    return {
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "architecture_support": torch.cuda.get_arch_list(),
        "gpu_status": subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version",
                "--format=csv,noheader",
            ],
            text=True,
        ).strip(),
        "gpu_processes": subprocess.check_output(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name,used_memory",
                "--format=csv,noheader",
            ],
            text=True,
        ).strip(),
    }


class TransformersGPU:
    def __init__(self, model_path: str, identifier: str, revision: str, budget: GPUBudget):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available():
            raise RuntimeError("GPU inference required; CUDA unavailable")
        self.budget = budget
        self.metadata = {
            "identifier": identifier,
            "revision": revision,
            "tokenizer": identifier,
            "tokenizer_revision": revision,
            "backend": "transformers",
            "precision": "bfloat16",
            "quantization": None,
            "transformers": importlib.metadata.version("transformers"),
            "torch": torch.__version__,
            "same_translation_judgment_model": True,
        }
        self.before = gpu_probe()
        budget.start()
        # SIGALRM bounds loading and inference, including a stuck generation. Run the
        # CLI under the documented timeout wrapper for an additional process watchdog.
        signal.signal(signal.SIGALRM, self._expired)
        signal.setitimer(signal.ITIMER_REAL, max(0.001, budget.remaining()))
        start = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, local_files_only=True, trust_remote_code=False
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            local_files_only=True,
            trust_remote_code=False,
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa",
        ).to("cuda:0")
        self.model.eval()
        if {p.device.type for p in self.model.parameters()} != {"cuda"}:
            raise RuntimeError("Model not entirely on GPU")
        torch.cuda.synchronize()
        self.loaded = {
            "loading_seconds": time.perf_counter() - start,
            "probe": gpu_probe(),
            "parameter_devices": sorted({str(p.device) for p in self.model.parameters()}),
            "pid": os.getpid(),
        }

    @staticmethod
    def _expired(*args):
        raise TimeoutError("Stage 1 GPU wall-time ceiling reached")

    def generate(self, prompt: str, seed: int, max_new_tokens: int, temperature: float) -> dict:
        import torch
        from transformers import set_seed

        self.budget.request()
        set_seed(seed)
        start = time.perf_counter()
        # Every call has a fresh chat context. No history or candidate preference reaches judge.
        text = self.tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt").to("cuda:0")
        input_tokens = inputs.input_ids.shape[1]
        if input_tokens + max_new_tokens > 16384:
            raise ValueError("Prompt exceeds declared 16384-token smoke context budget")
        settings = {
            "max_new_tokens": max_new_tokens,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
            "max_time": max(0.001, min(120, self.budget.remaining())),
        }
        if temperature > 0:
            settings.update(temperature=temperature, top_p=0.95)
        with torch.inference_mode():
            output = self.model.generate(**inputs, **settings)
        torch.cuda.synchronize()
        generated = output[0, input_tokens:]
        return {
            "text": self.tokenizer.decode(generated, skip_special_tokens=True),
            "input_tokens": input_tokens,
            "output_tokens": len(generated),
            "latency_seconds": time.perf_counter() - start,
            "peak_memory_bytes": torch.cuda.max_memory_allocated(),
            "output_device": str(output.device),
            "truncated": len(generated) >= max_new_tokens,
        }

    def close(self):
        import torch

        del self.model
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        self.budget.close()
        signal.setitimer(signal.ITIMER_REAL, 0)


class ModelCalls:
    def __init__(self, journal: Journal, model_metadata: dict, backend: Backend | None = None):
        self.journal, self.metadata, self.backend = journal, model_metadata, backend
        self.cache = {
            e["key"]: e["response"] for e in journal.read() if e["event"] == "generation_success"
        }
        self.logical = []

    def call(
        self,
        prompt: str,
        seed: int,
        max_new_tokens: int,
        temperature: float,
        purpose: str,
        owner: str,
    ) -> str:
        key = digest(
            {
                "prompt": prompt,
                "seed": seed,
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": 0.95,
                "model": self.metadata,
            }
        )
        cached = key in self.cache
        if not cached:
            if self.backend is None:
                raise KeyError(f"Replay has no saved generation for {key}")
            self.journal.append(
                {
                    "event": "generation_start",
                    "key": key,
                    "prompt": prompt,
                    "prompt_hash": digest(prompt),
                    "seed": seed,
                    "max_new_tokens": max_new_tokens,
                    "temperature": temperature,
                    "purpose": purpose,
                    "owner": owner,
                    "model": self.metadata,
                }
            )
            try:
                response = self.backend.generate(prompt, seed, max_new_tokens, temperature)
            except Exception as error:
                self.journal.append(
                    {
                        "event": "generation_error",
                        "key": key,
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                )
                self.logical.append(
                    {
                        "key": key,
                        "purpose": purpose,
                        "owner": owner,
                        "cached": False,
                        "failed": True,
                        "input_tokens": None,
                        "output_tokens": None,
                    }
                )
                raise
            self.journal.append({"event": "generation_success", "key": key, "response": response})
            self.cache[key] = response
        response = self.cache[key]
        attribution = {
            "key": key,
            "purpose": purpose,
            "owner": owner,
            "cached": cached,
            "input_tokens": response["input_tokens"],
            "output_tokens": response["output_tokens"],
            "latency_seconds": response["latency_seconds"],
        }
        self.logical.append(attribution)
        self.journal.append({"event": "logical_call", **attribution})
        return response["text"]
